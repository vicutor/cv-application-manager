"""Orchestrates a cover-letter generation: reuse-or-run job analysis and
evidence matching (Etap A/B, identical caching to CV generation -- a job that
already got a CV generated for it doesn't pay for those stages again, and
vice versa), draft (Etap CL-1), deterministic fact-citation validation, and
the AI-detection self-check (Etap CL-2).

Runs synchronously: two short structured LLM calls on a few hundred words of
input/output, unlike CV generation's LaTeX compile loop, so there's no need
for the queued/background-task machinery pipeline.py uses.
"""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.cover_letter import CoverLetter
from app.models.job_analysis import EvidenceMatch, JobAnalysis
from app.models.job_posting import JobPosting
from app.services.artifacts.paths import cover_letter_dir, relative_to_data, write_atomic
from app.services.candidate_profile.schema import CandidateProfile
from app.services.candidate_profile.service import get_active_profile_version
from app.services.candidate_profile.validation import collect_fact_ids, load_and_validate_yaml
from app.services.cover_letter.ai_check import apply_ai_check, run_cover_letter_ai_check
from app.services.cover_letter.drafting import run_cover_letter_draft
from app.services.cover_letter.validation import validate_cover_letter_draft
from app.services.cv_generation.analysis import all_requirements, persist_job_analysis, run_job_analysis
from app.services.cv_generation.evidence_matching import persist_evidence_matches, run_evidence_matching
from app.services.cv_generation.llm_client import LlmCallError
from app.services.latex.compiler import compile_latex
from app.services.latex.cover_letter_render import CoverLetterLetter, render_cover_letter_tex
from app.services.latex.safety import UnsafeLatexError, validate_latex_source


class NoActiveProfileError(Exception):
    pass


def _next_version_number(db: Session, job_posting_id: str) -> int:
    current_max = db.scalar(
        select(func.max(CoverLetter.version_number)).where(CoverLetter.job_posting_id == job_posting_id)
    )
    return (current_max or 0) + 1


def _get_or_create_job_analysis(db: Session, settings: Settings, job: JobPosting) -> JobAnalysis:
    job_analysis = db.scalars(
        select(JobAnalysis).where(JobAnalysis.job_posting_id == job.id).order_by(JobAnalysis.created_at.desc())
    ).first()
    if job_analysis is not None:
        return job_analysis
    analysis_result, _cost = run_job_analysis(db, settings, job)
    return persist_job_analysis(db, job, analysis_result, settings)


def _get_or_create_evidence_matches(
    db: Session, settings: Settings, job: JobPosting, profile, job_analysis: JobAnalysis
) -> list[EvidenceMatch]:
    evidence_rows = list(
        db.scalars(select(EvidenceMatch).where(EvidenceMatch.job_analysis_id == job_analysis.id))
    )
    if evidence_rows:
        return evidence_rows
    requirements = all_requirements(job_analysis)
    known_fact_ids = collect_fact_ids(profile)
    match_result, _cost = run_evidence_matching(db, settings, profile, requirements, job.id)
    return persist_evidence_matches(db, job_analysis, match_result, known_fact_ids)


def generate_cover_letter(db: Session, settings: Settings, job: JobPosting) -> CoverLetter:
    if not settings.llm_enabled:
        raise NoActiveProfileError("cover letter generation requires an LLM provider to be configured")

    profile_version = get_active_profile_version(db)
    if profile_version is None:
        raise NoActiveProfileError("no active candidate profile version")
    profile_result = load_and_validate_yaml(settings.data_dir / profile_version.yaml_path)
    if not profile_result.is_valid or profile_result.profile is None:
        raise NoActiveProfileError(f"active candidate profile is invalid: {profile_result.errors}")
    profile = profile_result.profile

    job_analysis = _get_or_create_job_analysis(db, settings, job)
    evidence_rows = _get_or_create_evidence_matches(db, settings, job, profile, job_analysis)
    requirements = all_requirements(job_analysis)

    cover_letter = CoverLetter(
        job_posting_id=job.id,
        candidate_profile_version_id=profile_version.id,
        job_analysis_id=job_analysis.id,
        version_number=_next_version_number(db, job.id),
        language=profile.preferences.default_cv_language,
        status="drafting",
        model_provider="anthropic",
        model_name=settings.llm_model_drafting,
        prompt_version="cover-letter-v1",
    )
    db.add(cover_letter)
    db.commit()
    db.refresh(cover_letter)

    try:
        draft, _cost = run_cover_letter_draft(
            db,
            settings,
            job=job,
            profile=profile,
            requirements=requirements,
            evidence_matches=evidence_rows,
            cover_letter_id=cover_letter.id,
        )
    except LlmCallError as exc:
        cover_letter.status = "failed"
        cover_letter.error_stage = "drafting"
        cover_letter.error_message = str(exc)
        db.commit()
        db.refresh(cover_letter)
        return cover_letter

    text, valid = validate_cover_letter_draft(profile, draft)
    if not valid:
        cover_letter.status = "failed"
        cover_letter.error_stage = "drafting"
        cover_letter.error_message = (
            "the draft cited a fact id that isn't in the candidate's own profile -- rather than ship a "
            "letter with an unverifiable claim, this generation failed; try again"
        )
        db.commit()
        db.refresh(cover_letter)
        return cover_letter

    cover_letter.status = "ai_check"
    db.commit()

    try:
        ai_check_result, _cost = run_cover_letter_ai_check(
            db, settings, text=text, job_posting_id=job.id, cover_letter_id=cover_letter.id
        )
    except LlmCallError as exc:
        cover_letter.status = "failed"
        cover_letter.error_stage = "ai_check"
        cover_letter.error_message = str(exc)
        db.commit()
        db.refresh(cover_letter)
        return cover_letter

    body_text, rewrite_rejected = apply_ai_check(text, ai_check_result)
    body_paragraphs = body_text.split("\n\n")

    notes = ai_check_result.reasoning
    if rewrite_rejected:
        notes += " (rewrite discarded: it introduced a number not present in the original, so the pre-rewrite text was kept.)"

    greeting = f"Hi {job.company_name} team,"
    signoff = "Best,"
    full_text = "\n\n".join([greeting, *body_paragraphs, f"{signoff}\n{profile.person.full_name}"])

    cover_letter.content_text = full_text
    cover_letter.word_count = len(body_text.split())
    cover_letter.sounds_ai_flagged = ai_check_result.sounds_ai_generated
    cover_letter.ai_check_notes = notes
    cover_letter.status = "succeeded"
    cover_letter.completed_at = datetime.now(timezone.utc)
    db.commit()

    _render_and_compile_pdf(settings, job, profile, cover_letter, greeting, body_paragraphs, signoff)
    db.commit()
    db.refresh(cover_letter)
    return cover_letter


def _render_and_compile_pdf(
    settings: Settings,
    job: JobPosting,
    profile: CandidateProfile,
    cover_letter: CoverLetter,
    greeting: str,
    body_paragraphs: list[str],
    signoff: str,
) -> None:
    """PDF/tex are a nice-to-have on top of the already-saved text -- a
    compile failure here doesn't fail the generation, it just leaves
    pdf_path/latex_path unset (has_pdf/has_tex read false in the API)."""
    letter = CoverLetterLetter(
        full_name=profile.person.full_name,
        email=profile.person.email or "",
        phone=profile.person.phone or "",
        location=profile.person.location or "",
        date_str=datetime.now(timezone.utc).strftime("%B %-d, %Y"),
        greeting=greeting,
        paragraphs=body_paragraphs,
        signoff=signoff,
    )
    tex_source = render_cover_letter_tex(letter)

    try:
        validate_latex_source(tex_source)
    except UnsafeLatexError:
        return

    gen_dir = cover_letter_dir(settings, job.id, cover_letter.version_number)
    tex_path = gen_dir / "cv.tex"
    write_atomic(tex_path, tex_source)
    cover_letter.latex_path = relative_to_data(settings, tex_path)

    result = compile_latex(
        tex_source, work_dir=gen_dir, compiler=settings.latex_compiler,
        timeout_seconds=settings.latex_timeout_seconds, max_pages=1,
    )
    if result.success and result.pdf_path is not None:
        cover_letter.pdf_path = relative_to_data(settings, result.pdf_path)
