"""Etap E -- ATS audit (LLM layer). The deterministic keyword-coverage score in
ats_audit.py (run_ats_audit) remains the score of record -- it's a pure
token-overlap calculation that can't be talked into inflating a number. This
module adds the qualitative checks a token-overlap score can't do: whether
keyword usage reads naturally vs. stuffed, whether the CV title aligns with the
job title, and whether phrasing would survive an ATS text extraction cleanly.

Per spec (Etap E): this is advisory, not authoritative, and must never suggest
adding a keyword the candidate's profile doesn't actually support -- the model
is only allowed to comment on keywords already present in the CV/job, never to
propose new unverified ones.
"""

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.job_analysis import JobAnalysis
from app.models.job_posting import JobPosting
from app.services.cv_generation.llm_client import call_structured
from app.services.latex.render import StructuredCv

PROMPT_VERSION = "ats-audit-v1"

_SYSTEM_PROMPT = """You are an ATS (applicant tracking system) readability
auditor. You will be given a CV's text content and the target job's title and
ATS keywords. Assess:

- title_alignment_ok / title_alignment_note: does the CV's headline reasonably
  align with the job title (doesn't need to be identical, but shouldn't read as
  an unrelated role)?
- missing_keywords: job ATS keywords that are genuinely absent from the CV text.
  Only list keywords that were given to you as job keywords -- never invent a
  new one, and never suggest the CV should claim a keyword the candidate hasn't
  actually demonstrated (you have no way to know if it's true, so only report
  absence, don't recommend addition).
- keyword_stuffing_detected / keyword_stuffing_notes: does any keyword appear
  unnaturally often, or is it crammed into a sentence where it doesn't
  grammatically belong?
- phrasing_natural / phrasing_notes: does the bullet/summary phrasing read as
  natural, professional prose that would extract cleanly as plain text (no
  broken sentence fragments, no dangling keyword lists)?
- section_naming_ok / section_naming_note: are section headings standard and
  ATS-parseable (e.g. "Experience", "Skills", "Summary") rather than creative
  or non-standard labels?

Be concise. This is advisory feedback, not a pass/fail gate."""


class AtsLlmAuditResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title_alignment_ok: bool
    title_alignment_note: str
    missing_keywords: list[str]
    keyword_stuffing_detected: bool
    keyword_stuffing_notes: str
    phrasing_natural: bool
    phrasing_notes: str
    section_naming_ok: bool
    section_naming_note: str


def _cv_text(structured: StructuredCv) -> str:
    lines = [f"Headline: {structured.headline}", f"Summary: {structured.summary}"]
    for entry in structured.experience:
        lines.append(f"\n{entry.position} at {entry.company} ({entry.date_range})")
        for bullet in entry.bullets:
            lines.append(f"- {bullet.text}")
    for group in structured.skills:
        lines.append(f"\n{group.name}: {', '.join(group.items)}")
    return "\n".join(lines)


def run_ats_llm_audit(
    db: Session,
    settings: Settings,
    structured: StructuredCv,
    job: JobPosting,
    job_analysis: JobAnalysis,
    cv_generation_id: str | None = None,
) -> tuple[AtsLlmAuditResult, float]:
    user_content = "\n\n".join(
        [
            f"Job title: {job.position_title}",
            "Job ATS keywords:\n" + ", ".join(job_analysis.ats_keywords),
            "CV content:\n" + _cv_text(structured),
        ]
    )
    return call_structured(
        db,
        settings,
        stage="ats",
        model=settings.llm_model_ats,
        system_prompt=_SYSTEM_PROMPT,
        user_content=user_content,
        response_model=AtsLlmAuditResult,
        prompt_version=PROMPT_VERSION,
        job_posting_id=job.id,
        cv_generation_id=cv_generation_id,
        max_tokens=2048,
        effort=None,
    )
