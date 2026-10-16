"""Etap D aggregation tests -- no real API calls. The key property under test is
that evaluate_fact_audit() enforces evidence_level="unverified" as a hard fail
independent of what the LLM audit says, and that per-bullet findings are paired
back to the correct experience entry positionally.
"""

from pathlib import Path

from app.services.candidate_profile.validation import load_and_validate_yaml
from app.services.cv_generation.fact_audit import (
    AggregatedFactAuditReport,
    BulletFactCheck,
    ExperienceFactCheck,
    FactAuditIssue,
    FactAuditResult,
    apply_fact_audit_corrections,
    evaluate_fact_audit,
)
from app.services.latex.render import CvBullet, CvExperienceEntry, StructuredCv

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURE_PROFILE_PATH = REPO_ROOT / "fixtures" / "candidate.example.yaml"


def _profile():
    result = load_and_validate_yaml(FIXTURE_PROFILE_PATH)
    assert result.is_valid, result.errors
    return result.profile


def _structured_from_profile(profile, bullets_by_experience_index):
    entries = []
    for i, exp in enumerate(profile.experience):
        bullets = bullets_by_experience_index.get(i, [])
        entries.append(
            CvExperienceEntry(
                company=exp.company,
                position=exp.position,
                date_range=f"{exp.start_date} - {exp.end_date or 'present'}",
                location=exp.location or "",
                bullets=bullets,
            )
        )
    return StructuredCv(
        full_name=profile.person.full_name,
        headline="Platform Engineer",
        location=profile.person.location or "",
        email=profile.person.email or "",
        phone=profile.person.phone or "",
        links=profile.person.links,
        summary=profile.summary_facts[0].statement,
        experience=entries,
        skills=[],
        language="en",
    )


def test_all_pass_when_llm_and_evidence_level_are_clean():
    profile = _profile()
    structured = _structured_from_profile(
        profile,
        {0: [CvBullet(text="Operated Kubernetes.", source_fact_ids=["resp_examplecorp_001"])]},
    )
    audit = FactAuditResult(
        summary_passed=True,
        summary_issues=[],
        experience=[
            ExperienceFactCheck(
                experience_id="exp_examplecorp_platform_engineer",
                bullets=[BulletFactCheck(bullet_index=0, passed=True, issues=[])],
            )
        ],
    )
    report = evaluate_fact_audit(structured, profile, audit)
    assert report.passed is True
    assert report.findings == []


def test_llm_flagged_bullet_produces_finding():
    profile = _profile()
    structured = _structured_from_profile(
        profile,
        {0: [CvBullet(text="Operated Kubernetes at massive scale for millions of users.", source_fact_ids=["resp_examplecorp_001"])]},
    )
    audit = FactAuditResult(
        summary_passed=True,
        summary_issues=[],
        experience=[
            ExperienceFactCheck(
                experience_id="exp_examplecorp_platform_engineer",
                bullets=[
                    BulletFactCheck(
                        bullet_index=0,
                        passed=False,
                        issues=["scope overstated: source doesn't mention 'millions of users'"],
                    )
                ],
            )
        ],
    )
    report = evaluate_fact_audit(structured, profile, audit)
    assert report.passed is False
    assert len(report.findings) == 1
    assert "scope overstated" in report.findings[0].issues[0]
    assert report.findings[0].location == "exp_examplecorp_platform_engineer#0"


def test_unverified_evidence_fails_even_if_llm_passed_it():
    """The candidate profile fixture has no unverified facts, so we build one
    in-memory to prove the deterministic override actually fires."""
    profile = _profile()
    profile.experience[0].responsibilities[0].evidence_level = "unverified"

    structured = _structured_from_profile(
        profile,
        {0: [CvBullet(text="Operated Kubernetes.", source_fact_ids=["resp_examplecorp_001"])]},
    )
    # LLM says it's fine -- must not matter.
    audit = FactAuditResult(
        summary_passed=True,
        summary_issues=[],
        experience=[
            ExperienceFactCheck(
                experience_id="exp_examplecorp_platform_engineer",
                bullets=[BulletFactCheck(bullet_index=0, passed=True, issues=[])],
            )
        ],
    )
    report = evaluate_fact_audit(structured, profile, audit)
    assert report.passed is False
    assert "unverified_evidence" in report.findings[0].issues[0]


def test_missing_experience_id_in_llm_response_does_not_crash_and_still_checks_evidence_level():
    profile = _profile()
    structured = _structured_from_profile(
        profile,
        {0: [CvBullet(text="Operated Kubernetes.", source_fact_ids=["resp_examplecorp_001"])]},
    )
    audit = FactAuditResult(summary_passed=True, summary_issues=[], experience=[])
    report = evaluate_fact_audit(structured, profile, audit)
    assert report.passed is True


def test_summary_failure_is_recorded():
    profile = _profile()
    structured = _structured_from_profile(profile, {})
    audit = FactAuditResult(
        summary_passed=False,
        summary_issues=["claims 10 years but profile facts say 5"],
        experience=[],
    )
    report = evaluate_fact_audit(structured, profile, audit)
    assert report.passed is False
    assert report.findings[0].location == "summary"


def test_apply_corrections_does_nothing_when_audit_passed():
    profile = _profile()
    structured = _structured_from_profile(
        profile, {0: [CvBullet(text="Original text.", source_fact_ids=["resp_examplecorp_001"])]}
    )
    corrected = apply_fact_audit_corrections(structured, profile, AggregatedFactAuditReport(passed=True))
    assert corrected == []
    assert structured.experience[0].bullets[0].text == "Original text."


def test_apply_corrections_reverts_flagged_bullet_to_verbatim_source_text():
    profile = _profile()
    embellished = "Operated a massive, industry-leading Kubernetes platform at unprecedented scale."
    structured = _structured_from_profile(
        profile, {0: [CvBullet(text=embellished, source_fact_ids=["resp_examplecorp_001"])]}
    )
    aggregated = AggregatedFactAuditReport(
        passed=False,
        findings=[
            FactAuditIssue(
                location="exp_examplecorp_platform_engineer#0",
                text=embellished,
                issues=["overstates scale"],
            )
        ],
    )

    corrected = apply_fact_audit_corrections(structured, profile, aggregated)

    assert corrected == ["exp_examplecorp_platform_engineer#0"]
    source_statement = next(
        r.statement for exp in profile.experience for r in exp.responsibilities if r.id == "resp_examplecorp_001"
    )
    assert structured.experience[0].bullets[0].text == source_statement
    assert structured.experience[0].bullets[0].text != embellished


def test_apply_corrections_combines_multiple_cited_facts_verbatim():
    profile = _profile()
    structured = _structured_from_profile(
        profile,
        {
            0: [
                CvBullet(
                    text="Embellished combined claim.",
                    source_fact_ids=["resp_examplecorp_001", "resp_examplecorp_002"],
                )
            ]
        },
    )
    aggregated = AggregatedFactAuditReport(
        passed=False,
        findings=[FactAuditIssue("exp_examplecorp_platform_engineer#0", "x", ["issue"])],
    )

    apply_fact_audit_corrections(structured, profile, aggregated)

    statements = {
        r.id: r.statement for exp in profile.experience for r in exp.responsibilities
    }
    expected = f"{statements['resp_examplecorp_001']} {statements['resp_examplecorp_002']}"
    assert structured.experience[0].bullets[0].text == expected


def test_apply_corrections_reverts_summary_to_first_summary_fact():
    profile = _profile()
    structured = _structured_from_profile(profile, {})
    structured.summary = "An embellished summary claiming things not in evidence."
    aggregated = AggregatedFactAuditReport(
        passed=False, findings=[FactAuditIssue("summary", structured.summary, ["overclaim"])]
    )

    corrected = apply_fact_audit_corrections(structured, profile, aggregated)

    assert "summary" in corrected
    assert structured.summary == profile.summary_facts[0].statement


def test_apply_corrections_only_touches_flagged_locations():
    profile = _profile()
    structured = _structured_from_profile(
        profile,
        {
            0: [
                CvBullet(text="Flagged bullet.", source_fact_ids=["resp_examplecorp_001"]),
                CvBullet(text="Untouched bullet.", source_fact_ids=["resp_examplecorp_002"]),
            ]
        },
    )
    aggregated = AggregatedFactAuditReport(
        passed=False,
        findings=[FactAuditIssue("exp_examplecorp_platform_engineer#0", "x", ["issue"])],
    )

    corrected = apply_fact_audit_corrections(structured, profile, aggregated)

    assert corrected == ["exp_examplecorp_platform_engineer#0"]
    assert structured.experience[0].bullets[1].text == "Untouched bullet."
