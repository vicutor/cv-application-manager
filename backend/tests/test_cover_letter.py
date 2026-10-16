"""Cover-letter tests. The fact-citation validation and the AI-check
digit-preservation guard are pure functions tested directly (no API calls,
per spec section 20). The end-to-end generation test monkeypatches the two
LLM-calling functions so it never touches the real Claude API either --
mirroring how test_bulk_import.py monkeypatches fetch_url.
"""

from pathlib import Path

from app.models.job_analysis import JobAnalysis
from app.services.candidate_profile.validation import load_and_validate_yaml
from app.services.cover_letter import generation as cover_letter_generation
from app.services.cover_letter.ai_check import CoverLetterAiCheckResult, apply_ai_check
from app.services.cover_letter.drafting import CoverLetterDraft, CoverLetterParagraph
from app.services.cover_letter.validation import validate_cover_letter_draft
from app.services.ingestion.text_import import import_from_text
from app.schemas.job import JobImportTextRequest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURE_PROFILE_PATH = REPO_ROOT / "fixtures" / "candidate.example.yaml"


def _profile():
    result = load_and_validate_yaml(FIXTURE_PROFILE_PATH)
    assert result.is_valid, result.errors
    return result.profile


def test_draft_with_real_fact_ids_is_valid():
    profile = _profile()
    draft = CoverLetterDraft(
        paragraphs=[
            CoverLetterParagraph(
                text="You're hiring for a Kubernetes platform role -- I've spent the last few years doing exactly that at scale.",
                source_fact_ids=["resp_examplecorp_001"],
            ),
            CoverLetterParagraph(
                text="I cut median deployment time by 40% by automating manual release steps.",
                source_fact_ids=["ach_examplecorp_001"],
            ),
            CoverLetterParagraph(
                text="Happy to walk through how I'd apply the same approach here.",
                source_fact_ids=["summary_devops_years"],
            ),
        ],
        stack_gap_bridged=False,
    )
    text, valid = validate_cover_letter_draft(profile, draft)
    assert valid is True
    assert "40%" in text


def test_draft_citing_unknown_fact_id_is_invalid():
    profile = _profile()
    draft = CoverLetterDraft(
        paragraphs=[
            CoverLetterParagraph(text="Real claim.", source_fact_ids=["resp_examplecorp_001"]),
            CoverLetterParagraph(text="Fabricated claim.", source_fact_ids=["resp_does_not_exist"]),
        ],
        stack_gap_bridged=False,
    )
    _text, valid = validate_cover_letter_draft(profile, draft)
    assert valid is False


def test_draft_with_no_paragraphs_is_invalid():
    profile = _profile()
    draft = CoverLetterDraft(paragraphs=[], stack_gap_bridged=False)
    _text, valid = validate_cover_letter_draft(profile, draft)
    assert valid is False


def test_ai_check_applies_rewrite_when_flagged():
    result = CoverLetterAiCheckResult(
        sounds_ai_generated=True,
        reasoning="Generic uplifting close, rule-of-three in paragraph two.",
        revised_text="Rewritten text with the same 40% figure intact.",
    )
    final_text, rejected = apply_ai_check("Original text with the same 40% figure intact.", result)
    assert final_text == "Rewritten text with the same 40% figure intact."
    assert rejected is False


def test_ai_check_rejects_rewrite_that_invents_a_number():
    result = CoverLetterAiCheckResult(
        sounds_ai_generated=True,
        reasoning="...",
        revised_text="Rewritten text now claiming 99% instead.",
    )
    final_text, rejected = apply_ai_check("Original text with 40% figure.", result)
    assert final_text == "Original text with 40% figure."
    assert rejected is True


def test_ai_check_leaves_text_untouched_when_not_flagged():
    result = CoverLetterAiCheckResult(sounds_ai_generated=False, reasoning="Reads naturally.", revised_text="ignored")
    final_text, rejected = apply_ai_check("Original text.", result)
    assert final_text == "Original text."
    assert rejected is False


def _make_job(db_session, suffix=""):
    outcome = import_from_text(
        db_session,
        JobImportTextRequest(
            company_name=f"CoverLetter Test Co{suffix}",
            position_title="Platform Engineer",
            raw_text=f"We need a Platform Engineer with strong Kubernetes and CI/CD experience.{suffix}" + "B" * 30,
        ),
    )
    return outcome.job_posting


def test_generate_cover_letter_end_to_end(monkeypatch, db_session, settings, active_profile_version):
    job = _make_job(db_session)

    def fake_analysis(db, settings, job, cv_generation_id=None):
        from app.services.cv_generation.analysis import JobAnalysisResult

        return (
            JobAnalysisResult(
                must_have=["Kubernetes"],
                nice_to_have=["Terraform"],
                responsibilities=["Operate a platform"],
                ats_keywords=["Kubernetes", "CI/CD"],
                domain_signals=[],
                seniority_signals=[],
                screening_risks=[],
            ),
            0.0,
        )

    def fake_matching(db, settings, profile, requirements, job_posting_id, cv_generation_id=None):
        from app.services.cv_generation.evidence_matching import EvidenceMatchItem, EvidenceMatchResult

        req_id = requirements[0]["id"]
        return (
            EvidenceMatchResult(
                matches=[
                    EvidenceMatchItem(
                        requirement_id=req_id,
                        candidate_fact_ids=["resp_examplecorp_001"],
                        match_type="direct",
                        confidence=0.9,
                        reason="Direct Kubernetes experience.",
                        must_not_claim=False,
                    )
                ]
            ),
            0.0,
        )

    def fake_draft(db, settings, *, job, profile, requirements, evidence_matches, cover_letter_id=None):
        return (
            CoverLetterDraft(
                paragraphs=[
                    CoverLetterParagraph(
                        text="Hook paragraph.", source_fact_ids=["resp_examplecorp_001"]
                    ),
                    CoverLetterParagraph(
                        text="Proof paragraph with 40%.", source_fact_ids=["ach_examplecorp_001"]
                    ),
                    CoverLetterParagraph(
                        text="Close paragraph.", source_fact_ids=["summary_devops_years"]
                    ),
                ],
                stack_gap_bridged=False,
            ),
            0.01,
        )

    def fake_ai_check(db, settings, *, text, job_posting_id=None, cover_letter_id=None):
        return (
            CoverLetterAiCheckResult(sounds_ai_generated=False, reasoning="Reads naturally.", revised_text=text),
            0.005,
        )

    monkeypatch.setattr(cover_letter_generation, "run_job_analysis", fake_analysis)
    monkeypatch.setattr(cover_letter_generation, "run_evidence_matching", fake_matching)
    monkeypatch.setattr(cover_letter_generation, "run_cover_letter_draft", fake_draft)
    monkeypatch.setattr(cover_letter_generation, "run_cover_letter_ai_check", fake_ai_check)
    monkeypatch.setattr(type(settings), "llm_enabled", property(lambda self: True))

    cover_letter = cover_letter_generation.generate_cover_letter(db_session, settings, job)

    assert cover_letter.status == "succeeded"
    assert cover_letter.version_number == 1
    assert "Hook paragraph." in cover_letter.content_text
    assert cover_letter.sounds_ai_flagged is False

    # Re-running for the same job must reuse the cached JobAnalysis/EvidenceMatch
    # (not call run_job_analysis/run_evidence_matching again) and create a new version.
    def fail_if_called(*args, **kwargs):
        raise AssertionError("should have reused the cached analysis/evidence, not re-run it")

    monkeypatch.setattr(cover_letter_generation, "run_job_analysis", fail_if_called)
    monkeypatch.setattr(cover_letter_generation, "run_evidence_matching", fail_if_called)

    second = cover_letter_generation.generate_cover_letter(db_session, settings, job)
    assert second.version_number == 2
    assert second.status == "succeeded"

    analyses = db_session.query(JobAnalysis).filter(JobAnalysis.job_posting_id == job.id).all()
    assert len(analyses) == 1


def test_generate_cover_letter_fails_cleanly_on_bad_citation(monkeypatch, db_session, settings, active_profile_version):
    job = _make_job(db_session, suffix=" (bad citation test)")

    def fake_analysis(db, settings, job, cv_generation_id=None):
        from app.services.cv_generation.analysis import JobAnalysisResult

        return (
            JobAnalysisResult(
                must_have=["Kubernetes"],
                nice_to_have=[],
                responsibilities=[],
                ats_keywords=[],
                domain_signals=[],
                seniority_signals=[],
                screening_risks=[],
            ),
            0.0,
        )

    def fake_matching(db, settings, profile, requirements, job_posting_id, cv_generation_id=None):
        from app.services.cv_generation.evidence_matching import EvidenceMatchResult

        return EvidenceMatchResult(matches=[]), 0.0

    def fake_draft(db, settings, *, job, profile, requirements, evidence_matches, cover_letter_id=None):
        return (
            CoverLetterDraft(
                paragraphs=[
                    CoverLetterParagraph(text="Fabricated.", source_fact_ids=["not_a_real_fact_id"]),
                ],
                stack_gap_bridged=False,
            ),
            0.01,
        )

    monkeypatch.setattr(cover_letter_generation, "run_job_analysis", fake_analysis)
    monkeypatch.setattr(cover_letter_generation, "run_evidence_matching", fake_matching)
    monkeypatch.setattr(cover_letter_generation, "run_cover_letter_draft", fake_draft)
    monkeypatch.setattr(type(settings), "llm_enabled", property(lambda self: True))

    cover_letter = cover_letter_generation.generate_cover_letter(db_session, settings, job)

    assert cover_letter.status == "failed"
    assert cover_letter.error_stage == "drafting"
    assert cover_letter.content_text is None
