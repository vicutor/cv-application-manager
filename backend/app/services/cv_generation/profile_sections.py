"""Deterministic (no-LLM) mapping from profile data to the render-ready
Projects/Certifications/Education/Languages sections. These sections are
shown in full, verbatim from the profile, in both the mock and real
pipelines -- unlike experience bullets, they aren't tailored per job posting.
"""

from app.services.candidate_profile.schema import CandidateProfile
from app.services.latex.render import CvCertificationEntry, CvEducationEntry, CvLanguageEntry, CvProjectEntry


def _date_range(start: str | None, end: str | None) -> str:
    if start and end:
        return f"{start} - {end}"
    return start or end or ""


def build_education_entries(profile: CandidateProfile) -> list[CvEducationEntry]:
    return [
        CvEducationEntry(
            institution=edu.institution, degree=edu.degree, date_range=_date_range(edu.start_date, edu.end_date)
        )
        for edu in profile.education
    ]


def build_certification_entries(profile: CandidateProfile) -> list[CvCertificationEntry]:
    return [CvCertificationEntry(name=cert.name, issuer=cert.issuer or "") for cert in profile.certifications]


def build_language_entries(profile: CandidateProfile) -> list[CvLanguageEntry]:
    return [CvLanguageEntry(name=lang.name, level=lang.level) for lang in profile.languages]


def build_project_entries(profile: CandidateProfile) -> list[CvProjectEntry]:
    return [
        CvProjectEntry(name=proj.name, bullets=[proj.statement] if proj.statement else [])
        for proj in profile.projects
    ]
