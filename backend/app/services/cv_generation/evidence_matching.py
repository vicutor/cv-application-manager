"""Etap B -- evidence matching: map job requirements to candidate profile facts.

Every requirement gets matched against the candidate's fact catalog (summary
statements, job responsibilities, achievements -- the same set fact_check.py
validates bullets against, via collect_fact_ids). Two layers of defense against
fabrication: the system prompt instructs the model to never pad matches with
unsupported ids, and persist_evidence_matches() independently drops any fact id
the model returns that isn't actually in the known set, regardless of what the
model claims -- a hallucinated id here must never reach the drafting stage.
"""

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.job_analysis import EvidenceMatch, JobAnalysis
from app.services.candidate_profile.schema import CandidateProfile
from app.services.cv_generation.llm_client import call_structured

PROMPT_VERSION = "evidence-matching-v1"

_SYSTEM_PROMPT = """You are an evidence-matching engine for a CV tailoring pipeline.

You will receive a list of job requirements (each with a stable id) and a catalog
of the candidate's verified facts (each with a stable id: summary statements, job
responsibilities, and achievements from their real work history).

For EVERY requirement in the input, return exactly one match entry with:
- requirement_id: copy the id from the input, unchanged.
- candidate_fact_ids: ids (copied verbatim from the catalog only -- never invent
  an id) that genuinely support this requirement. Empty list if there is no real
  support.
- match_type: "direct" (the candidate did exactly this), "partial" (related but
  narrower or different scope), "transferable" (different context but the
  underlying skill clearly applies), or "none" (no real support).
- confidence: 0.0-1.0, your confidence in this match.
- reason: one short sentence explaining the match, or the lack of one.
- must_not_claim: true if there is insufficient evidence to claim this
  requirement on the CV at all. Always true when match_type is "none". Also
  true for a weak/partial match where stating it outright would overstate the
  candidate's experience (e.g. claiming "production experience" from a fact
  that only describes a personal proof-of-concept). Do NOT set this true just
  because match_type is "transferable" -- a transferable match is a real,
  honest connection (a real skill demonstrated in a different context that
  genuinely applies here), not an overclaim, and the drafting stage is
  separately instructed to frame it as transferable rather than as direct
  experience with the requirement. Suppressing transferable matches here is
  how a CV ends up looking thinner than the candidate's real, relevant
  background actually supports -- reserve must_not_claim for when the
  connection itself is too weak or speculative to state honestly, not merely
  because it isn't direct.

Do not pad candidate_fact_ids with loosely related ids to look more complete --
false positives here can lead to fabricated CV claims later in the pipeline,
which is the one thing this system must never produce. When genuinely unsure
whether a connection is real at all, leave it out entirely rather than forcing
a transferable label onto something that doesn't actually apply -- but once
you're confident a skill genuinely transfers, surface it; don't bury a real,
honest connection under a defensive must_not_claim just because it isn't a
direct match."""


class EvidenceMatchItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requirement_id: str
    candidate_fact_ids: list[str]
    match_type: str
    confidence: float
    reason: str
    must_not_claim: bool


class EvidenceMatchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    matches: list[EvidenceMatchItem]


def _fact_catalog_text(profile: CandidateProfile) -> str:
    lines: list[str] = []
    for f in profile.summary_facts:
        lines.append(f"- id={f.id} [summary] {f.statement}")
    for exp in profile.experience:
        ctx = f"{exp.company} / {exp.position}"
        for r in exp.responsibilities:
            lines.append(f"- id={r.id} [{ctx}, responsibility] {r.statement}")
        for a in exp.achievements:
            extras = []
            if a.metrics:
                extras.append("metrics: " + "; ".join(f"{m.value}{m.unit} ({m.context})" for m in a.metrics))
            if a.technologies:
                extras.append("tech: " + ", ".join(a.technologies))
            suffix = f" | {' | '.join(extras)}" if extras else ""
            lines.append(f"- id={a.id} [{ctx}, achievement] {a.statement}{suffix}")
    return "\n".join(lines)


def _requirements_text(requirements: list[dict]) -> str:
    return "\n".join(f"- id={r['id']}: {r['text']}" for r in requirements)


def run_evidence_matching(
    db: Session,
    settings: Settings,
    profile: CandidateProfile,
    requirements: list[dict],
    job_posting_id: str,
    cv_generation_id: str | None = None,
) -> tuple[EvidenceMatchResult, float]:
    user_content = (
        "Job requirements:\n"
        + _requirements_text(requirements)
        + "\n\nCandidate fact catalog:\n"
        + _fact_catalog_text(profile)
    )
    return call_structured(
        db,
        settings,
        stage="matching",
        model=settings.llm_model_matching,
        system_prompt=_SYSTEM_PROMPT,
        user_content=user_content,
        response_model=EvidenceMatchResult,
        prompt_version=PROMPT_VERSION,
        job_posting_id=job_posting_id,
        cv_generation_id=cv_generation_id,
        max_tokens=8192,
        effort="medium",
    )


def persist_evidence_matches(
    db: Session,
    job_analysis: JobAnalysis,
    result: EvidenceMatchResult,
    known_fact_ids: set[str],
) -> list[EvidenceMatch]:
    rows: list[EvidenceMatch] = []
    for item in result.matches:
        valid_ids = [fid for fid in item.candidate_fact_ids if fid in known_fact_ids]
        dropped = [fid for fid in item.candidate_fact_ids if fid not in known_fact_ids]
        reason = item.reason
        if dropped:
            reason = f"{reason} [dropped unknown fact id(s) from model output: {', '.join(dropped)}]"

        if not valid_ids:
            rows.append(
                EvidenceMatch(
                    job_analysis_id=job_analysis.id,
                    requirement_id=item.requirement_id,
                    candidate_fact_id=None,
                    match_type="none",
                    confidence=0.0,
                    reason=reason,
                    must_not_claim=True,
                )
            )
            continue

        for fid in valid_ids:
            rows.append(
                EvidenceMatch(
                    job_analysis_id=job_analysis.id,
                    requirement_id=item.requirement_id,
                    candidate_fact_id=fid,
                    match_type=item.match_type,
                    confidence=item.confidence,
                    reason=reason,
                    must_not_claim=item.must_not_claim,
                )
            )

    db.add_all(rows)
    db.commit()
    for row in rows:
        db.refresh(row)
    return rows
