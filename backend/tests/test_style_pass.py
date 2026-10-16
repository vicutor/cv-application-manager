"""Etap F apply-side tests -- no real API calls. The behavior under test is the
numeric-fabrication guard: apply_style_pass() must reject any rewritten line
that introduces a number not present in the original, regardless of how
plausible-sounding the rewrite is.
"""

from pathlib import Path

from app.services.candidate_profile.validation import load_and_validate_yaml
from app.services.cv_generation.style_pass import (
    StyledBullet,
    StyledExperienceSection,
    StylePassResult,
    apply_style_pass,
)
from app.services.latex.render import CvBullet, CvExperienceEntry, StructuredCv

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURE_PROFILE_PATH = REPO_ROOT / "fixtures" / "candidate.example.yaml"


def _profile():
    result = load_and_validate_yaml(FIXTURE_PROFILE_PATH)
    assert result.is_valid, result.errors
    return result.profile


def _structured(profile, bullets_by_experience_index):
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
        summary="5 years of experience building cloud infrastructure.",
        experience=entries,
        skills=[],
        language="en",
    )


def test_clean_rewrite_with_same_numbers_is_applied():
    profile = _profile()
    structured = _structured(
        profile,
        {0: [CvBullet(text="Reduced deployment time by 40% via automation.", source_fact_ids=["ach_examplecorp_001"])]},
    )
    result = StylePassResult(
        summary="Cloud infrastructure engineer with 5 years of hands-on experience.",
        experience=[
            StyledExperienceSection(
                experience_id="exp_examplecorp_platform_engineer",
                bullets=[StyledBullet(bullet_index=0, text="Cut deployment time 40% by automating releases.")],
            )
        ],
    )
    styled, report = apply_style_pass(structured, profile, result)
    assert report.rejected_bullets == []
    assert report.rejected_summary is False
    assert styled.experience[0].bullets[0].text == "Cut deployment time 40% by automating releases."
    assert styled.summary == "Cloud infrastructure engineer with 5 years of hands-on experience."


def test_rewrite_that_invents_a_number_is_rejected_and_original_kept():
    profile = _profile()
    original_text = "Reduced deployment time by 40% via automation."
    structured = _structured(
        profile,
        {0: [CvBullet(text=original_text, source_fact_ids=["ach_examplecorp_001"])]},
    )
    result = StylePassResult(
        summary="5 years of experience building cloud infrastructure.",
        experience=[
            StyledExperienceSection(
                experience_id="exp_examplecorp_platform_engineer",
                # fabricated an extra "50" that wasn't in the original
                bullets=[StyledBullet(bullet_index=0, text="Cut deployment time 40% across 50 services via automation.")],
            )
        ],
    )
    styled, report = apply_style_pass(structured, profile, result)
    assert report.rejected_bullets == ["Cut deployment time 40% across 50 services via automation."]
    assert styled.experience[0].bullets[0].text == original_text


def test_rewrite_dropping_a_number_entirely_is_accepted():
    """Dropping a number is safe (never a fabrication risk) -- only additions
    are rejected."""
    profile = _profile()
    structured = _structured(
        profile,
        {0: [CvBullet(text="Reduced deployment time by 40% via automation.", source_fact_ids=["ach_examplecorp_001"])]},
    )
    result = StylePassResult(
        summary="5 years of experience building cloud infrastructure.",
        experience=[
            StyledExperienceSection(
                experience_id="exp_examplecorp_platform_engineer",
                bullets=[StyledBullet(bullet_index=0, text="Reduced deployment time via automation.")],
            )
        ],
    )
    styled, report = apply_style_pass(structured, profile, result)
    assert report.rejected_bullets == []
    assert styled.experience[0].bullets[0].text == "Reduced deployment time via automation."


def test_summary_with_fabricated_number_is_rejected():
    profile = _profile()
    structured = _structured(profile, {})
    result = StylePassResult(
        summary="Engineer with 12 years of experience across 30 production systems.",
        experience=[],
    )
    styled, report = apply_style_pass(structured, profile, result)
    assert report.rejected_summary is True
    assert styled.summary == structured.summary


def test_missing_experience_section_in_result_keeps_original_bullets():
    profile = _profile()
    structured = _structured(
        profile,
        {0: [CvBullet(text="Original bullet.", source_fact_ids=["resp_examplecorp_001"])]},
    )
    result = StylePassResult(summary="5 years of experience building cloud infrastructure.", experience=[])
    styled, report = apply_style_pass(structured, profile, result)
    assert styled.experience[0].bullets[0].text == "Original bullet."
    assert report.rejected_bullets == []


def test_non_numeric_fields_are_preserved_unchanged():
    profile = _profile()
    structured = _structured(
        profile,
        {0: [CvBullet(text="Original.", source_fact_ids=["resp_examplecorp_001"], matched_requirement_ids=["must_1"], priority=1, keywords=["Kubernetes"], has_metric=False)]},
    )
    result = StylePassResult(
        summary="5 years of experience building cloud infrastructure.",
        experience=[
            StyledExperienceSection(
                experience_id="exp_examplecorp_platform_engineer",
                bullets=[StyledBullet(bullet_index=0, text="Rewritten.")],
            )
        ],
    )
    styled, _ = apply_style_pass(structured, profile, result)
    bullet = styled.experience[0].bullets[0]
    assert bullet.text == "Rewritten."
    assert bullet.source_fact_ids == ["resp_examplecorp_001"]
    assert bullet.matched_requirement_ids == ["must_1"]
    assert bullet.priority == 1
    assert bullet.keywords == ["Kubernetes"]
