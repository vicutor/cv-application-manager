from dataclasses import asdict

from app.models.job_posting import JobPosting
from app.services.candidate_profile.schema import CandidateProfile
from app.services.cv_generation.profile_sections import (
    build_certification_entries,
    build_education_entries,
    build_language_entries,
    build_project_entries,
)
from app.services.cv_generation.skills_grouping import group_skills_by_category
from app.services.latex.render import CvBullet, CvExperienceEntry, StructuredCv


def build_structured_cv(profile: CandidateProfile, job: JobPosting) -> StructuredCv:
    """Deterministic (no-LLM) structured CV: every bullet is copied verbatim from
    the candidate profile and tagged with the fact id it came from. This is the
    'mock pipeline' referenced by the spec's first vertical slice -- content
    selection/rewriting by an LLM is a later stage (Etap 6), not part of this path.
    """
    summary = profile.summary_facts[0].statement if profile.summary_facts else ""

    experience_entries: list[CvExperienceEntry] = []
    for exp in profile.experience:
        bullets: list[CvBullet] = []
        for resp in exp.responsibilities:
            bullets.append(CvBullet(text=resp.statement, source_fact_ids=[resp.id]))
        for ach in exp.achievements:
            bullets.append(CvBullet(text=ach.statement, source_fact_ids=[ach.id]))

        date_range = f"{exp.start_date} - {exp.end_date or 'present'}"
        experience_entries.append(
            CvExperienceEntry(
                company=exp.company,
                position=exp.position,
                date_range=date_range,
                location=exp.location or "",
                bullets=bullets,
            )
        )

    return StructuredCv(
        full_name=profile.person.full_name,
        headline=job.position_title,
        location=profile.person.location or "",
        email=profile.person.email or "",
        phone=profile.person.phone or "",
        links=profile.person.links,
        summary=summary,
        experience=experience_entries,
        skills=group_skills_by_category(profile),
        language=profile.preferences.default_cv_language,
        certification_tagline=profile.person.certification_tagline or "",
        focus_tagline=profile.person.focus_tagline or "",
        photo_path=profile.person.photo_path or "",
        projects=build_project_entries(profile),
        certifications=build_certification_entries(profile),
        education=build_education_entries(profile),
        languages=build_language_entries(profile),
    )


def structured_cv_to_dict(cv: StructuredCv) -> dict:
    return asdict(cv)
