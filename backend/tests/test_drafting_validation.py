"""Etap C validation tests -- no real API calls. build_verified_structured_cv is
the safety net between the model's draft and what actually gets rendered into
the PDF, so its bullet-dropping/cross-experience-smuggling rejection and its
guaranteed-coverage backfill (every experience entry shows something) are the
behaviors under test.
"""

from pathlib import Path

from app.services.candidate_profile.validation import load_and_validate_yaml
from app.services.cv_generation.drafting import (
    DraftBullet,
    DraftCv,
    DraftExperienceSection,
    build_verified_structured_cv,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURE_PROFILE_PATH = REPO_ROOT / "fixtures" / "candidate.example.yaml"


def _profile():
    result = load_and_validate_yaml(FIXTURE_PROFILE_PATH)
    assert result.is_valid, result.errors
    return result.profile


class _FakeJob:
    position_title = "Platform Engineer"
    company_name = "Target Co"


def test_bullet_with_valid_own_experience_ids_is_kept():
    profile = _profile()
    draft = DraftCv(
        summary="5 years operating cloud infrastructure with a Kubernetes focus.",
        summary_source_fact_ids=["summary_devops_years"],
        experience=[
            DraftExperienceSection(
                experience_id="exp_examplecorp_platform_engineer",
                bullets=[
                    DraftBullet(
                        text="Operated and scaled a multi-tenant Kubernetes platform.",
                        source_fact_ids=["resp_examplecorp_001"],
                        matched_requirement_ids=["must_1"],
                        priority=1,
                        keywords=["Kubernetes"],
                        has_metric=False,
                    )
                ],
            )
        ],
    )

    structured, report = build_verified_structured_cv(profile, _FakeJob(), draft, {"must_1"})

    assert not report.dropped_bullets
    assert not report.dropped_summary
    entry = next(e for e in structured.experience if e.company == "ExampleCorp")
    assert len(entry.bullets) == 1
    assert entry.bullets[0].text == "Operated and scaled a multi-tenant Kubernetes platform."


def test_bullet_citing_another_experiences_fact_id_is_dropped_entirely():
    profile = _profile()
    # resp_priorco_001 belongs to exp_priorco_devops_engineer, not
    # exp_examplecorp_platform_engineer -- this is the cross-experience
    # smuggling case that must never survive into the rendered CV.
    draft = DraftCv(
        summary="Summary.",
        summary_source_fact_ids=["summary_devops_years"],
        experience=[
            DraftExperienceSection(
                experience_id="exp_examplecorp_platform_engineer",
                bullets=[
                    DraftBullet(
                        text="Fabricated cross-job claim.",
                        source_fact_ids=["resp_priorco_001"],
                        priority=1,
                        has_metric=False,
                    ),
                    DraftBullet(
                        text="Mixed: one real, one fake id.",
                        source_fact_ids=["resp_examplecorp_001", "resp_priorco_001"],
                        priority=2,
                        has_metric=False,
                    ),
                ],
            )
        ],
    )

    structured, report = build_verified_structured_cv(profile, _FakeJob(), draft, set())

    entry = next(e for e in structured.experience if e.company == "ExampleCorp")
    # Both drafted bullets were rejected, so this entry falls back to a
    # verbatim profile bullet rather than showing nothing.
    assert len(entry.bullets) == 1
    assert entry.bullets[0].source_fact_ids[0] in {"resp_examplecorp_001", "ach_examplecorp_001"}
    assert len(report.dropped_bullets) == 2
    assert "exp_examplecorp_platform_engineer" in report.backfilled_experience_ids


def test_bullet_with_no_source_fact_ids_is_dropped_and_backfilled():
    profile = _profile()
    draft = DraftCv(
        summary="Summary.",
        summary_source_fact_ids=["summary_devops_years"],
        experience=[
            DraftExperienceSection(
                experience_id="exp_examplecorp_platform_engineer",
                bullets=[
                    DraftBullet(
                        text="Unsourced claim.",
                        source_fact_ids=[],
                        priority=1,
                        has_metric=False,
                    )
                ],
            )
        ],
    )

    structured, report = build_verified_structured_cv(profile, _FakeJob(), draft, set())
    entry = next(e for e in structured.experience if e.company == "ExampleCorp")
    assert report.dropped_bullets == ["Unsourced claim."]
    # ExampleCorp has real facts in the profile, so it gets backfilled rather
    # than left blank -- the candidate wants every role visible.
    assert len(entry.bullets) == 1
    assert "exp_examplecorp_platform_engineer" in report.backfilled_experience_ids


def test_summary_with_invalid_fact_id_falls_back_to_first_summary_fact():
    profile = _profile()
    draft = DraftCv(
        summary="A summary citing a fabricated fact id.",
        summary_source_fact_ids=["made_up_summary_fact"],
        experience=[],
    )

    structured, report = build_verified_structured_cv(profile, _FakeJob(), draft, set())
    assert report.dropped_summary is True
    assert structured.summary == profile.summary_facts[0].statement


def test_skills_are_always_shown_in_full_grouped_by_category():
    """Skills are no longer model-selected -- build_verified_structured_cv
    always shows every profile skill, regardless of what the draft says
    (DraftCv no longer even has a skills field)."""
    profile = _profile()
    draft = DraftCv(
        summary="Summary.",
        summary_source_fact_ids=["summary_devops_years"],
        experience=[],
    )

    structured, _ = build_verified_structured_cv(profile, _FakeJob(), draft, set())
    all_shown = {name for group in structured.skills for name in group.items}
    assert all_shown == {s.name for s in profile.skills}


def test_experience_with_no_matching_draft_section_is_backfilled_not_left_empty():
    """The model omitting a role entirely (e.g. it judged it irrelevant to the
    job) must not make that role disappear from the CV -- every role the
    profile has real facts for gets at least one bullet."""
    profile = _profile()
    draft = DraftCv(
        summary="Summary.",
        summary_source_fact_ids=["summary_devops_years"],
        experience=[],  # model omitted PriorCo (and everything else) entirely
    )

    structured, report = build_verified_structured_cv(profile, _FakeJob(), draft, set())
    assert len(structured.experience) == len(profile.experience)
    prior_entry = next(e for e in structured.experience if e.company == "PriorCo")
    assert len(prior_entry.bullets) == 1
    assert "exp_priorco_devops_engineer" in report.backfilled_experience_ids


def test_experience_entry_with_no_profile_facts_at_all_stays_empty_and_is_not_backfilled():
    """An entry with genuinely nothing in the profile (no responsibilities,
    no achievements) can't be backfilled from thin air -- it's shown with
    just its header line, same as the candidate's own hand-authored CV does
    for a one-month internship with no recorded detail."""
    profile = _profile()
    # The fixture has no such entry, so simulate one directly.
    profile.experience[0].responsibilities = []
    profile.experience[0].achievements = []
    draft = DraftCv(summary="Summary.", summary_source_fact_ids=["summary_devops_years"], experience=[])

    structured, report = build_verified_structured_cv(profile, _FakeJob(), draft, set())
    entry = structured.experience[0]
    assert entry.bullets == []
    assert profile.experience[0].id not in report.backfilled_experience_ids


def test_matched_requirement_ids_filtered_to_known_set():
    profile = _profile()
    draft = DraftCv(
        summary="Summary.",
        summary_source_fact_ids=["summary_devops_years"],
        experience=[
            DraftExperienceSection(
                experience_id="exp_examplecorp_platform_engineer",
                bullets=[
                    DraftBullet(
                        text="Bullet.",
                        source_fact_ids=["resp_examplecorp_001"],
                        matched_requirement_ids=["must_1", "made_up_req"],
                        priority=1,
                        has_metric=False,
                    )
                ],
            )
        ],
    )

    structured, _ = build_verified_structured_cv(profile, _FakeJob(), draft, {"must_1"})
    entry = next(e for e in structured.experience if e.company == "ExampleCorp")
    assert entry.bullets[0].matched_requirement_ids == ["must_1"]
