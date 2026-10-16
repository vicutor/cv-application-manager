"""Etap D -- fact audit. This is layer three of the anti-fabrication defense:

1. drafting.build_verified_structured_cv (Etap C) already rejects any bullet
   whose cited fact ids aren't real, or belong to the wrong experience entry.
2. evaluate_fact_audit() below independently re-checks evidence_level for
   every bullet in pure Python (no LLM involved, can't be talked out of it):
   any bullet sourced from a fact marked "unverified" in the candidate's own
   profile fails, full stop, regardless of what the LLM auditor below says.
3. run_fact_audit() below asks an LLM to compare each bullet's *wording*
   against its cited fact's *exact statement* -- catching semantic drift that
   id-membership checks can't see: a technically-real fact id whose bullet text
   nonetheless embellishes the number, date, scope, or claims production
   experience from what the fact only describes as a personal PoC or "tool
   familiarity".

Per spec: any failure blocks PDF generation until fixed or explicitly accepted
by the user -- this module only produces the report; the pipeline caller
decides how to act on it.

Note on pairing: StructuredCv.experience entries carry no experience_id (see
latex/render.py) -- they're always built by iterating profile.experience in
order (both here and in the mock pipeline), so pairing structured.experience[i]
with profile.experience[i] positionally is safe and is how both directions of
this module (building the LLM's input, and reading its output back) line up
experience sections.
"""

from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.services.candidate_profile.schema import CandidateProfile
from app.services.cv_generation.llm_client import call_structured
from app.services.latex.render import StructuredCv

PROMPT_VERSION = "fact-audit-v1"

_SYSTEM_PROMPT = """You are a strict fact-checker for a CV. You will be given the
candidate's exact source facts (their literal statements, with any metrics and
technologies) and the CV bullets/summary that claim to be derived from them.

For each bullet and the summary, check that the wording does NOT go beyond what
the cited source fact(s) literally support. Specifically flag as an issue any:
- number that doesn't match the source fact's number, or was added when the
  source had none;
- date, company name, or position title that doesn't match the source;
- technology named that isn't in the cited fact's own statement or technology
  list;
- broader scope than the source states (e.g. source says "one service", bullet
  says "the platform");
- upgrade from proof-of-concept / personal project to "production" experience,
  when the source doesn't describe production use;
- upgrade from "familiar with" / "exposure to" a tool to hands-on / extensive
  experience, when the source doesn't support that;
- any claim the source simply does not contain.

Rephrasing, tightening, and reordering are fine and NOT issues -- only flag
actual additions or overstatements of fact. If a bullet is a faithful, possibly
more concise restatement of its source fact(s), mark it passed with no issues.

For each experience section, return a bullets list containing EXACTLY one entry
per bullet given to you, in the same order, using its given bullet_index. Use
the experience_id exactly as given.

Be exact and literal. When genuinely unsure whether something is an
overstatement, flag it as an issue rather than pass it silently."""


class BulletFactCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bullet_index: int
    passed: bool
    issues: list[str]


class ExperienceFactCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")
    experience_id: str
    bullets: list[BulletFactCheck]


class FactAuditResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary_passed: bool
    summary_issues: list[str]
    experience: list[ExperienceFactCheck]


def _fact_lookup(profile: CandidateProfile) -> dict[str, str]:
    """id -> a fully rendered statement (with metrics/tech/evidence_level inline)
    so the model gets a single self-contained line per fact id."""
    lookup: dict[str, str] = {}
    for f in profile.summary_facts:
        lookup[f.id] = f"{f.statement} [evidence_level={f.evidence_level}]"
    for exp in profile.experience:
        for r in exp.responsibilities:
            lookup[r.id] = f"{r.statement} [evidence_level={r.evidence_level}]"
        for a in exp.achievements:
            extras = []
            if a.metrics:
                extras.append("metrics: " + "; ".join(f"{m.value}{m.unit} ({m.context})" for m in a.metrics))
            if a.technologies:
                extras.append("technologies: " + ", ".join(a.technologies))
            extras.append(f"evidence_level={a.evidence_level}")
            lookup[a.id] = f"{a.statement} [{'; '.join(extras)}]"
    return lookup


def _build_user_content(structured: StructuredCv, profile: CandidateProfile) -> str:
    facts = _fact_lookup(profile)
    lines: list[str] = []

    lines.append("SUMMARY:")
    lines.append(f'  text: "{structured.summary}"')
    for f in profile.summary_facts:
        lines.append(f"  candidate summary fact {f.id}: {facts[f.id]}")

    for exp, entry in zip(profile.experience, structured.experience):
        if not entry.bullets:
            continue
        lines.append(f"\nEXPERIENCE experience_id={exp.id} ({exp.position} @ {exp.company}):")
        for i, bullet in enumerate(entry.bullets):
            lines.append(f'  bullet_index={i}: "{bullet.text}"')
            for fid in bullet.source_fact_ids:
                lines.append(f"    cited source {fid}: {facts.get(fid, '(unknown fact id)')}")

    return "\n".join(lines)


def run_fact_audit(
    db: Session,
    settings: Settings,
    structured: StructuredCv,
    profile: CandidateProfile,
    job_posting_id: str,
    cv_generation_id: str | None = None,
) -> tuple[FactAuditResult, float]:
    return call_structured(
        db,
        settings,
        stage="fact_check",
        model=settings.llm_model_fact_check,
        system_prompt=_SYSTEM_PROMPT,
        user_content=_build_user_content(structured, profile),
        response_model=FactAuditResult,
        prompt_version=PROMPT_VERSION,
        job_posting_id=job_posting_id,
        cv_generation_id=cv_generation_id,
        max_tokens=12000,
        effort="medium",
    )


@dataclass
class FactAuditIssue:
    location: str  # "summary" or "<experience_id>#<bullet_index>"
    text: str
    issues: list[str]


@dataclass
class AggregatedFactAuditReport:
    passed: bool
    findings: list[FactAuditIssue] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "findings": [
                {"location": f.location, "text": f.text, "issues": f.issues} for f in self.findings
            ],
        }


def evaluate_fact_audit(
    structured: StructuredCv,
    profile: CandidateProfile,
    audit: FactAuditResult,
) -> AggregatedFactAuditReport:
    """Combines the LLM's semantic findings with an independent, deterministic
    evidence_level re-check the LLM has no ability to override."""
    evidence_level_by_id: dict[str, str] = {}
    for f in profile.summary_facts:
        evidence_level_by_id[f.id] = f.evidence_level
    for exp in profile.experience:
        for r in exp.responsibilities:
            evidence_level_by_id[r.id] = r.evidence_level
        for a in exp.achievements:
            evidence_level_by_id[a.id] = a.evidence_level

    findings: list[FactAuditIssue] = []

    if not audit.summary_passed:
        findings.append(
            FactAuditIssue("summary", structured.summary, list(audit.summary_issues) or ["flagged by fact auditor"])
        )

    audit_by_experience_id = {ec.experience_id: ec for ec in audit.experience}

    for exp, entry in zip(profile.experience, structured.experience):
        llm_bullets_by_index = {}
        ec = audit_by_experience_id.get(exp.id)
        if ec is not None:
            llm_bullets_by_index = {bc.bullet_index: bc for bc in ec.bullets}

        for i, bullet in enumerate(entry.bullets):
            issues: list[str] = []

            unverified = [fid for fid in bullet.source_fact_ids if evidence_level_by_id.get(fid) == "unverified"]
            if unverified:
                issues.append(
                    "unverified_evidence: source fact(s) marked unverified in the profile: "
                    + ", ".join(unverified)
                )

            llm_finding = llm_bullets_by_index.get(i)
            if llm_finding is not None and not llm_finding.passed:
                issues.extend(llm_finding.issues)

            if issues:
                findings.append(FactAuditIssue(f"{exp.id}#{i}", bullet.text, issues))

    return AggregatedFactAuditReport(passed=not findings, findings=findings)


def _plain_fact_statements(profile: CandidateProfile) -> dict[str, str]:
    """id -> the fact's bare statement text, with no bracketed metadata --
    used as a direct drop-in replacement for a flagged bullet's wording,
    unlike _fact_lookup()'s prompt-formatted version above."""
    lookup: dict[str, str] = {}
    for f in profile.summary_facts:
        lookup[f.id] = f.statement
    for exp in profile.experience:
        for r in exp.responsibilities:
            lookup[r.id] = r.statement
        for a in exp.achievements:
            lookup[a.id] = a.statement
    return lookup


def apply_fact_audit_corrections(
    structured: StructuredCv,
    profile: CandidateProfile,
    aggregated: AggregatedFactAuditReport,
) -> list[str]:
    """Instead of failing the whole generation over a single embellished
    phrase, revert exactly the flagged bullet(s)/summary to a verbatim
    concatenation of their own cited source facts' statements -- wording that
    was never reworded can't overclaim, so this is a strictly safe, always-
    converges fix. Mutates `structured` in place; returns the list of
    locations that were corrected (empty if nothing needed fixing).

    This replaces retrying the whole draft and hoping the model doesn't
    introduce a *different* embellishment elsewhere -- a real failure mode
    observed in practice (fixing one overclaim, the redraft added another).
    """
    if aggregated.passed:
        return []

    plain_facts = _plain_fact_statements(profile)
    flagged = {f.location for f in aggregated.findings}
    corrected: list[str] = []

    if "summary" in flagged:
        structured.summary = profile.summary_facts[0].statement if profile.summary_facts else structured.summary
        corrected.append("summary")

    for exp, entry in zip(profile.experience, structured.experience):
        for i, bullet in enumerate(entry.bullets):
            location = f"{exp.id}#{i}"
            if location not in flagged:
                continue
            verbatim = " ".join(
                plain_facts[fid] for fid in bullet.source_fact_ids if fid in plain_facts
            ).strip()
            if verbatim:
                bullet.text = verbatim
                corrected.append(location)

    return corrected
