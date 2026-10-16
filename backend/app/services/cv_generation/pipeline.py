import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.session import SessionLocal
from app.models.cv_generation import CvGeneration
from app.models.generation_event import GenerationEvent
from app.models.job_analysis import EvidenceMatch, JobAnalysis
from app.models.job_posting import JobPosting
from app.services.artifacts.paths import generation_dir, relative_to_data, write_atomic
from app.services.candidate_profile.schema import CandidateProfile
from app.services.candidate_profile.service import get_active_profile_version
from app.services.candidate_profile.validation import collect_fact_ids, load_and_validate_yaml
from app.services.cv_generation.analysis import all_requirements, persist_job_analysis, run_job_analysis
from app.services.cv_generation.ats_audit import run_ats_audit
from app.services.cv_generation.ats_audit_llm import run_ats_llm_audit
from app.services.cv_generation.drafting import build_verified_structured_cv, run_drafting
from app.services.cv_generation.evidence_matching import persist_evidence_matches, run_evidence_matching
from app.services.cv_generation.events import finish_event, latest_llm_run, llm_run_message, start_event
from app.services.cv_generation.fact_audit import apply_fact_audit_corrections, evaluate_fact_audit, run_fact_audit
from app.services.cv_generation.fact_check import run_fact_check
from app.services.cv_generation.structured_cv import build_structured_cv, structured_cv_to_dict
from app.services.cv_generation.style_pass import apply_style_pass, run_style_pass
from app.services.latex.compiler import compile_latex
from app.services.latex.render import StructuredCv, render_cv_tex
from app.services.latex.safety import UnsafeLatexError, validate_latex_source

MOCK_PROMPT_VERSION = "mock-deterministic-v1"
REAL_PROMPT_VERSION = "real-pipeline-v1"


class NoActiveProfileError(Exception):
    pass


def _next_version_number(db: Session, job_posting_id: str) -> int:
    current_max = db.scalar(
        select(func.max(CvGeneration.version_number)).where(
            CvGeneration.job_posting_id == job_posting_id
        )
    )
    return (current_max or 0) + 1


def create_queued_generation(
    db: Session, settings: Settings, job: JobPosting, language: str = "en", target_pages: int | None = None
) -> CvGeneration:
    """Validate preconditions and insert the CvGeneration row synchronously, so the
    API request fails fast (e.g. no active profile) instead of only failing inside
    a background task the caller can't directly observe. The actual generation work
    (LLM stages when wired up, LaTeX rendering, compilation) runs afterwards via
    run_generation, so a slow compile never blocks the HTTP response.
    """
    profile_version = get_active_profile_version(db)
    if profile_version is None:
        raise NoActiveProfileError("no active candidate profile version")

    version_number = _next_version_number(db, job.id)
    resolved_target_pages = target_pages or settings.latex_max_pages

    if settings.llm_enabled:
        model_provider, model_name, prompt_version = "anthropic", settings.llm_model_drafting, REAL_PROMPT_VERSION
    else:
        model_provider, model_name, prompt_version = "mock", "deterministic", MOCK_PROMPT_VERSION

    generation = CvGeneration(
        job_posting_id=job.id,
        candidate_profile_version_id=profile_version.id,
        version_number=version_number,
        language=language,
        target_pages=resolved_target_pages,
        status="queued",
        model_provider=model_provider,
        model_name=model_name,
        prompt_version=prompt_version,
        generation_config={"target_pages": resolved_target_pages, "language": language},
        fact_check_status="pending",
    )
    db.add(generation)
    db.commit()
    db.refresh(generation)
    return generation


def run_generation(generation_id: str, settings: Settings) -> None:
    """Runs in a background task with its own DB session (the request-scoped
    session is long gone by the time this executes). Every exit path commits a
    terminal status ("succeeded" or "failed") so polling clients never hang.
    """
    db = SessionLocal()
    try:
        generation = db.get(CvGeneration, generation_id)
        if generation is None:
            return
        job = db.get(JobPosting, generation.job_posting_id)
        if job is None:
            generation.status = "failed"
            generation.error_stage = "storage_failed"
            generation.error_message = "job posting no longer exists"
            generation.completed_at = datetime.now(timezone.utc)
            db.commit()
            return

        _run_pipeline(db, settings, generation, job)
    finally:
        db.close()


def _fail(
    db: Session, generation: CvGeneration, stage: str, message: str, event: GenerationEvent | None = None
) -> None:
    if event is not None:
        finish_event(db, event, "failed", message=message)
    generation.status = "failed"
    generation.error_stage = stage
    generation.error_message = message
    generation.completed_at = datetime.now(timezone.utc)
    db.commit()


def _resolve_photo_path(structured: StructuredCv, settings: Settings) -> None:
    """StructuredCv.photo_path (from Person.photo_path) is stored data-relative
    (e.g. "profile/assets/photo.jpg") so the same profile YAML works whether
    the app is running on the host or in Docker -- LaTeX needs an absolute
    path at compile time, so resolve it here where settings.data_dir (which
    differs per environment) is available. Silently omits the photo if the
    file doesn't actually exist, rather than failing the whole generation."""
    if not structured.photo_path:
        return
    resolved = (settings.data_dir / structured.photo_path).resolve()
    structured.photo_path = str(resolved) if resolved.exists() else ""


def _run_pipeline(db: Session, settings: Settings, generation: CvGeneration, job: JobPosting) -> None:
    profile_version = get_active_profile_version(db)
    if profile_version is None or profile_version.id != generation.candidate_profile_version_id:
        _fail(db, generation, "profile_invalid", "active candidate profile version changed or is missing")
        return

    profile_result = load_and_validate_yaml(settings.data_dir / profile_version.yaml_path)
    if not profile_result.is_valid or profile_result.profile is None:
        _fail(db, generation, "profile_invalid", f"active candidate profile is invalid: {profile_result.errors}")
        return
    profile = profile_result.profile

    gen_dir = generation_dir(settings, job.id, generation.version_number)
    gen_dir.mkdir(parents=True, exist_ok=True)

    if settings.llm_enabled:
        _run_real_pipeline(db, settings, generation, job, profile, gen_dir)
    else:
        _run_mock_pipeline(db, settings, generation, job, profile, gen_dir)


def _run_mock_pipeline(
    db: Session,
    settings: Settings,
    generation: CvGeneration,
    job: JobPosting,
    profile: CandidateProfile,
    gen_dir: Path,
) -> None:
    event = start_event(db, generation, "drafting")
    generation.status = "drafting"
    db.commit()

    structured = build_structured_cv(profile, job)
    _resolve_photo_path(structured, settings)
    structured_cv_path = gen_dir / "structured_cv.json"
    write_atomic(structured_cv_path, json.dumps(structured_cv_to_dict(structured), indent=2))
    generation.structured_cv_path = relative_to_data(settings, structured_cv_path)
    finish_event(db, event, "succeeded", message="built deterministically from the full profile (no LLM)")

    event = start_event(db, generation, "fact_checking")
    generation.status = "fact_checking"
    db.commit()
    fact_report = run_fact_check(structured.experience, collect_fact_ids(profile))
    write_atomic(gen_dir / "fact_check.json", json.dumps(fact_report.to_dict(), indent=2))
    if not fact_report.passed:
        generation.fact_check_status = "failed"
        _fail(db, generation, "fact_check_failed", "one or more CV bullets cite unknown fact ids", event)
        return
    generation.fact_check_status = "passed"
    finish_event(db, event, "succeeded", message=f"{fact_report.checked_bullets} bullets checked, all sourced")

    event = start_event(db, generation, "ats_checking")
    generation.status = "ats_checking"
    db.commit()
    ats_report = run_ats_audit(
        job.technologies, [s for group in structured.skills for s in group.items], structured.summary
    )
    write_atomic(gen_dir / "ats_report.json", json.dumps(ats_report.to_dict(), indent=2))
    generation.ats_score = ats_report.score
    finish_event(db, event, "succeeded", message=f"keyword coverage score {ats_report.score:.2f}")

    _render_and_compile(db, settings, generation, job, structured, gen_dir, MOCK_PROMPT_VERSION, structured_cv_path)


def _run_real_pipeline(
    db: Session,
    settings: Settings,
    generation: CvGeneration,
    job: JobPosting,
    profile: CandidateProfile,
    gen_dir: Path,
) -> None:
    """Etap A-G. A + B (analysis, evidence matching) are cached per job posting
    -- they don't depend on generation-specific settings like target_pages, so
    re-running "Generate CV" for the same job reuses them instead of paying for
    those calls again. C-F run fresh on every generation."""
    job_analysis = db.scalars(
        select(JobAnalysis).where(JobAnalysis.job_posting_id == job.id).order_by(JobAnalysis.created_at.desc())
    ).first()

    event = start_event(db, generation, "analyzing")
    if job_analysis is None:
        generation.status = "analyzing"
        db.commit()
        analysis_result, _cost = run_job_analysis(db, settings, job, cv_generation_id=generation.id)
        job_analysis = persist_job_analysis(db, job, analysis_result, settings)
        llm_run = latest_llm_run(db, generation.id, "analysis")
        finish_event(db, event, "succeeded", message=llm_run_message(llm_run), llm_run_id=llm_run.id if llm_run else None)
    else:
        finish_event(db, event, "skipped", message="reused analysis from an earlier generation of this posting")

    generation.job_analysis_id = job_analysis.id
    db.commit()

    requirements = all_requirements(job_analysis)
    evidence_rows = list(
        db.scalars(select(EvidenceMatch).where(EvidenceMatch.job_analysis_id == job_analysis.id))
    )
    event = start_event(db, generation, "matching")
    if not evidence_rows:
        generation.status = "matching"
        db.commit()
        known_fact_ids = collect_fact_ids(profile)
        match_result, _cost = run_evidence_matching(
            db, settings, profile, requirements, job.id, cv_generation_id=generation.id
        )
        evidence_rows = persist_evidence_matches(db, job_analysis, match_result, known_fact_ids)
        llm_run = latest_llm_run(db, generation.id, "matching")
        finish_event(db, event, "succeeded", message=llm_run_message(llm_run), llm_run_id=llm_run.id if llm_run else None)
    else:
        finish_event(db, event, "skipped", message="reused evidence matches from an earlier generation of this posting")

    write_atomic(
        gen_dir / "job_analysis.json",
        json.dumps(
            {
                "job_analysis_id": job_analysis.id,
                "must_have": job_analysis.must_have,
                "nice_to_have": job_analysis.nice_to_have,
                "responsibilities": job_analysis.responsibilities,
                "ats_keywords": job_analysis.ats_keywords,
                "domain_signals": job_analysis.domain_signals,
                "seniority_signals": job_analysis.seniority_signals,
                "screening_risks": job_analysis.screening_risks,
                "evidence_matches": [
                    {
                        "requirement_id": r.requirement_id,
                        "candidate_fact_id": r.candidate_fact_id,
                        "match_type": r.match_type,
                        "confidence": r.confidence,
                        "must_not_claim": r.must_not_claim,
                        "reason": r.reason,
                    }
                    for r in evidence_rows
                ],
            },
            indent=2,
        ),
    )

    event = start_event(db, generation, "drafting")
    generation.status = "drafting"
    db.commit()
    draft, _cost = run_drafting(
        db,
        settings,
        job=job,
        profile=profile,
        requirements=requirements,
        evidence_matches=evidence_rows,
        target_pages=generation.target_pages,
        ats_keywords=job_analysis.ats_keywords,
        cv_generation_id=generation.id,
    )
    known_req_ids = {r["id"] for r in requirements}
    structured, draft_report = build_verified_structured_cv(profile, job, draft, known_req_ids)
    _resolve_photo_path(structured, settings)
    write_atomic(
        gen_dir / "draft_validation.json",
        json.dumps(
            {
                "dropped_bullets": draft_report.dropped_bullets,
                "dropped_summary": draft_report.dropped_summary,
                "backfilled_experience_ids": draft_report.backfilled_experience_ids,
            },
            indent=2,
        ),
    )
    structured_cv_path = gen_dir / "structured_cv.json"
    write_atomic(structured_cv_path, json.dumps(structured_cv_to_dict(structured), indent=2))
    generation.structured_cv_path = relative_to_data(settings, structured_cv_path)
    llm_run = latest_llm_run(db, generation.id, "drafting")
    bullet_count = sum(len(e.bullets) for e in structured.experience)
    draft_message = f"{llm_run_message(llm_run)}, {bullet_count} bullets drafted" if llm_run else None
    if draft_report.dropped_bullets:
        draft_message = f"{draft_message}; dropped {len(draft_report.dropped_bullets)} unsupported bullet(s)"
    if draft_report.backfilled_experience_ids:
        draft_message = (
            f"{draft_message}; backfilled {len(draft_report.backfilled_experience_ids)} role(s) "
            "the model left empty"
        )
    finish_event(db, event, "succeeded", message=draft_message, llm_run_id=llm_run.id if llm_run else None)

    # Etap D: cheap deterministic id-membership check first (already enforced by
    # build_verified_structured_cv, kept here as a real, independent guard), then
    # the LLM semantic audit.
    event = start_event(db, generation, "fact_checking")
    generation.status = "fact_checking"
    db.commit()
    fact_report = run_fact_check(structured.experience, collect_fact_ids(profile))
    if not fact_report.passed:
        generation.fact_check_status = "failed"
        _fail(db, generation, "fact_check_failed", "one or more CV bullets cite unknown fact ids", event)
        return

    audit_result, _cost = run_fact_audit(db, settings, structured, profile, job.id, cv_generation_id=generation.id)
    aggregated = evaluate_fact_audit(structured, profile, audit_result)
    write_atomic(gen_dir / "fact_audit.json", json.dumps(aggregated.to_dict(), indent=2))
    llm_run = latest_llm_run(db, generation.id, "fact_check")
    corrected = apply_fact_audit_corrections(structured, profile, aggregated)
    generation.fact_check_status = "corrected" if corrected else "passed"
    fact_message = llm_run_message(llm_run)
    if corrected:
        fact_message = f"{fact_message}; reverted {len(corrected)} location(s) to verbatim source text: {', '.join(corrected)}"
    finish_event(db, event, "succeeded", message=fact_message, llm_run_id=llm_run.id if llm_run else None)

    # Etap E: deterministic keyword-coverage score is the score of record; the
    # LLM audit is advisory (naturalness, title alignment, stuffing) and never
    # feeds back into ats_score.
    event = start_event(db, generation, "ats_checking")
    generation.status = "ats_checking"
    db.commit()
    ats_report = run_ats_audit(
        job.technologies, [s for group in structured.skills for s in group.items], structured.summary
    )
    generation.ats_score = ats_report.score
    llm_ats, _cost = run_ats_llm_audit(db, settings, structured, job, job_analysis, cv_generation_id=generation.id)
    write_atomic(
        gen_dir / "ats_report.json",
        json.dumps({"deterministic": ats_report.to_dict(), "llm_advisory": llm_ats.model_dump()}, indent=2),
    )
    llm_run = latest_llm_run(db, generation.id, "ats")
    finish_event(
        db,
        event,
        "succeeded",
        message=f"score {ats_report.score:.2f}; {llm_run_message(llm_run)}",
        llm_run_id=llm_run.id if llm_run else None,
    )

    # Etap F: style pass, then re-run the fact audit per spec. If the styled
    # version introduces a new issue, fall back to the pre-style (already
    # fact-checked) content rather than failing generation over a style pass.
    event = start_event(db, generation, "style")
    generation.status = "style"
    db.commit()
    style_result, _cost = run_style_pass(db, settings, structured, profile, job.id, cv_generation_id=generation.id)
    styled, style_report = apply_style_pass(structured, profile, style_result)
    write_atomic(
        gen_dir / "style_pass.json",
        json.dumps(
            {"rejected_summary": style_report.rejected_summary, "rejected_bullets": style_report.rejected_bullets},
            indent=2,
        ),
    )
    llm_run = latest_llm_run(db, generation.id, "style")
    finish_event(db, event, "succeeded", message=llm_run_message(llm_run), llm_run_id=llm_run.id if llm_run else None)

    event = start_event(db, generation, "fact_checking_recheck")
    post_style_audit, _cost = run_fact_audit(db, settings, styled, profile, job.id, cv_generation_id=generation.id)
    post_style_aggregated = evaluate_fact_audit(styled, profile, post_style_audit)
    final_structured = styled
    llm_run = latest_llm_run(db, generation.id, "fact_check")
    if not post_style_aggregated.passed:
        final_structured = structured
        write_atomic(gen_dir / "style_pass_rejected.json", json.dumps(post_style_aggregated.to_dict(), indent=2))
        finish_event(
            db,
            event,
            "succeeded",
            message="style pass introduced an issue -- reverted to the pre-style content",
            llm_run_id=llm_run.id if llm_run else None,
        )
    else:
        finish_event(db, event, "succeeded", message=llm_run_message(llm_run), llm_run_id=llm_run.id if llm_run else None)

    final_cv_path = gen_dir / "structured_cv_final.json"
    write_atomic(final_cv_path, json.dumps(structured_cv_to_dict(final_structured), indent=2))
    generation.structured_cv_path = relative_to_data(settings, final_cv_path)

    _render_and_compile(db, settings, generation, job, final_structured, gen_dir, REAL_PROMPT_VERSION, final_cv_path)


def _trim_lowest_priority_bullets(structured: StructuredCv, count: int) -> int:
    """Removes up to `count` of the least-important bullets (highest .priority
    number first, across all experience entries) one at a time, recomputing
    the worst remaining bullet after each removal. Returns how many were
    actually removed (fewer than requested once bullets run out). Per spec:
    if the PDF is too long, go back to content selection and shorten it --
    never solve overflow by shrinking to an unreadable font.

    Every experience entry should stay visible on the CV, so an entry's last
    remaining bullet is only removed once no entry has a spare one left --
    i.e. this protects "every role shows something" as long as there's any
    other way to make the content fit."""
    removed = 0
    for _ in range(count):
        candidates = [
            (entry_idx, bullet_idx, bullet.priority)
            for entry_idx, entry in enumerate(structured.experience)
            for bullet_idx, bullet in enumerate(entry.bullets)
        ]
        if not candidates:
            break
        non_last = [c for c in candidates if len(structured.experience[c[0]].bullets) > 1]
        pool = non_last or candidates
        entry_idx, bullet_idx, _ = max(pool, key=lambda c: (c[2], c[0], c[1]))
        del structured.experience[entry_idx].bullets[bullet_idx]
        removed += 1
    return removed


def _bullets_to_trim_for_overflow(structured: StructuredCv, current_pages: int, target_pages: int) -> int:
    """Removing one bullet per retry converges far too slowly when a rich
    profile drafts 2-3x the target length (a real case: 5 pages against a
    2-page target took more retries than the attempt budget allows). Cut a
    fraction of what's left, proportional to how far over budget the current
    draft is, so a handful of retries converges regardless of how much
    trimming is actually needed."""
    total = sum(len(e.bullets) for e in structured.experience)
    if total == 0 or current_pages <= target_pages:
        return 0
    overflow_ratio = (current_pages - target_pages) / current_pages
    # 1.3x the raw ratio so this converges within the attempt budget instead
    # of asymptotically creeping toward the target.
    return min(total, max(1, round(total * overflow_ratio * 1.3)))


def _render_and_compile(
    db: Session,
    settings: Settings,
    generation: CvGeneration,
    job: JobPosting,
    structured: StructuredCv,
    gen_dir: Path,
    prompt_version: str,
    structured_cv_path: Path,
) -> None:
    event = start_event(db, generation, "rendering")
    tex_path = gen_dir / "cv.tex"
    max_attempts = settings.latex_max_repair_attempts + 1  # 1 initial render + N page-fit trims
    trimmed = False
    attempts_used = 0
    result = None

    for attempt in range(max_attempts):
        attempts_used += 1
        generation.status = "writing_latex"
        db.commit()
        tex_source = render_cv_tex(structured)

        try:
            validate_latex_source(tex_source)
        except UnsafeLatexError as exc:
            write_atomic(tex_path, tex_source)
            generation.latex_path = relative_to_data(settings, tex_path)
            _fail(db, generation, "latex_rejected", str(exc), event)
            return

        generation.status = "compiling"
        db.commit()
        result = compile_latex(
            tex_source,
            work_dir=gen_dir,
            compiler=settings.latex_compiler,
            timeout_seconds=settings.latex_timeout_seconds,
            max_pages=generation.target_pages,
        )
        generation.latex_path = relative_to_data(settings, tex_path)
        write_atomic(gen_dir / "compile.log", result.log)

        page_overflow = (
            not result.success
            and result.has_selectable_text
            and result.page_count is not None
            and result.page_count > generation.target_pages
        )
        if not page_overflow or attempt == max_attempts - 1:
            break
        cut = _bullets_to_trim_for_overflow(structured, result.page_count, generation.target_pages)
        if _trim_lowest_priority_bullets(structured, cut) == 0:
            break
        trimmed = True

    if trimmed:
        write_atomic(structured_cv_path, json.dumps(structured_cv_to_dict(structured), indent=2))

    generation.status = "validating"
    db.commit()

    if not result.success or result.pdf_path is None:
        stage = "latex_compile_failed" if not result.has_selectable_text else "pdf_validation_failed"
        generation.pdf_page_count = result.page_count
        _fail(db, generation, stage, _tail(result.log), event)
        return

    generation.pdf_path = relative_to_data(settings, result.pdf_path)
    generation.pdf_page_count = result.page_count
    generation.status = "succeeded"
    generation.completed_at = datetime.now(timezone.utc)

    render_message = f"{result.page_count} page(s) in {attempts_used} attempt(s)"
    if trimmed:
        render_message += " (trimmed content to fit the page limit)"
    finish_event(db, event, "succeeded", message=render_message)

    write_atomic(
        gen_dir / "generation.json",
        json.dumps(
            {
                "job_posting_id": job.id,
                "version_number": generation.version_number,
                "prompt_version": prompt_version,
                "status": generation.status,
                "pdf_page_count": generation.pdf_page_count,
                "ats_score": generation.ats_score,
                "trimmed_for_page_fit": trimmed,
            },
            indent=2,
        ),
    )
    db.commit()


def _tail(log: str, max_chars: int = 2000) -> str:
    return log[-max_chars:] if len(log) > max_chars else log
