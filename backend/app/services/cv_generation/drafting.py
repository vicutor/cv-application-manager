"""Etap C -- draft CV: the model selects, prioritizes, and phrases bullet
content, but every bullet must cite fact ids that literally exist in the
candidate's profile, scoped to the correct experience entry. The model may
rephrase and tighten wording; it must never introduce a claim, number, date,
company, or technology absent from the cited fact's own statement.

This is enforced twice: an explicit prompt instruction, and
build_verified_structured_cv() below, which drops -- entirely, not partially --
any bullet that cites even one fact id outside the experience entry it claims
to belong to. A bullet mixing one real and one fabricated id can't be trusted
to only reflect the real one, so the whole bullet is discarded rather than
salvaged.
"""

from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.job_analysis import EvidenceMatch
from app.models.job_posting import JobPosting
from app.services.candidate_profile.schema import CandidateProfile
from app.services.cv_generation.llm_client import call_structured
from app.services.cv_generation.profile_sections import (
    build_certification_entries,
    build_education_entries,
    build_language_entries,
    build_project_entries,
)
from app.services.cv_generation.skills_grouping import group_skills_by_category
from app.services.latex.render import CvBullet, CvExperienceEntry, StructuredCv

PROMPT_VERSION = "drafting-v1"

_SYSTEM_PROMPT = """You are a CV drafting engine. Your job is to select, prioritize,
and phrase the strongest possible CV content for a specific job application --
while staying strictly bound to evidence that is actually true.

You will receive:
1. The target job's title, and the requirements it lists (with ids).
2. A map of which requirement ids already have confirmed supporting evidence,
   and which candidate fact ids support them.
3. The candidate's full fact catalog, grouped by real experience entry (each
   with a real experience_id, company, position, and dates), plus their summary
   facts and skills.

Your task:
- Write a short, punchy professional summary (2-4 sentences) tailored to this
  job, built ONLY from the candidate's summary facts. Open with the single
  strongest, most quantified differentiator available in the summary facts
  (a concrete metric or outcome) rather than a generic scope-listing opener
  like "X years across A, B and C" -- a senior candidate leads with proof,
  not a table of contents. Cite which summary fact id(s) it draws from in
  summary_source_fact_ids. The summary is held to the exact same
  no-embellishment rule as bullets: if a summary fact says "experience spans
  X" or "familiar with X", your summary must not upgrade that to "deep
  hands-on expertise in X", "extensive experience with X", or similar
  stronger phrasing -- match the source fact's own level of confidence,
  don't raise it. Do not add a claim (e.g. "leading projects from design
  through production") that isn't stated in any cited summary fact, even if
  it sounds like a plausible summary of the experience section -- the
  summary can only assert what its cited summary facts themselves say.
  Staying within these limits, still write with a senior, confident voice
  (see the tone rule below) rather than a hedging, junior one.
- For each experience entry, select and phrase bullets from that entry's own
  responsibilities/achievements ONLY -- never pull a fact from one job into
  another job's bullet list. Every bullet's source_fact_ids must be real ids
  belonging to that exact experience entry.
- You may tighten, reorder, and rephrase a fact's wording for impact and
  concision, and combine multiple facts from the SAME experience into one
  bullet (citing all their ids) if it reads better. You must NOT add numbers,
  scope, tools, outcomes, or seniority claims that are not already present in
  the cited fact(s). If a fact is a proof-of-concept or personal project, do
  not reword it to sound like production experience. If a fact only mentions
  "familiarity" with a tool, do not reword it to claim hands-on production use.
  When combining facts, watch for scope creep specifically: if one cited fact
  names a specific, narrower scope (particular services, a specific count),
  the combined bullet must keep that scope exactly as narrow -- do not
  generalize "the identity service" into "all services" just because it
  reads more smoothly. The combined sentence's scope is the scope of its
  narrowest cited fact, never broader. One exception: internal environment
  codenames (e.g. "UAT1", "UAT2", "SIT") are jargon that means nothing to an
  outside reader -- generalize them to "multiple environments" / "several
  environments" by default rather than spelling out the codenames, and never
  label them with an internal category word like "preproduction" unless the
  cited fact itself uses that word.
- Senior tone: this candidate has 6+ years of experience and the CV must
  read that way. Lead each bullet with the outcome or the action taken, not
  a step-by-step diagnostic narration of how you got there ("noticed X, so I
  looked at Y, which led me to Z") -- state what you owned/built/fixed/cut
  first, then the supporting detail or root cause as a trailing clause or
  parenthetical if it's worth keeping. Numbers stay exactly as given (never
  invent, round favorably, or drop a number to sound smoother), but the
  sentence carrying them should sound like a senior engineer reporting
  impact, not a junior narrating their troubleshooting steps. This is a
  phrasing/ordering choice only -- it must never change what the number
  measures or add scope the source fact doesn't support.
- Don't let the CV look thinner than the candidate's real background actually
  supports. If a requirement (especially a must-have) has only
  partial/transferable support in the confirmed-evidence list, or none at
  all, actively scan the candidate's FULL fact catalog -- across every
  experience entry, not just the one role that obviously matches this job's
  domain -- for the closest real, honest connection, and write a bullet for
  it. Frame it as what it is: state the real thing the candidate actually
  did, in its real context, and let the relevance to this requirement come
  through in how you phrase and prioritize it, never by claiming the
  requirement itself was done. ("Coordinated delivery across three
  cross-functional engineering teams, from scoping to release" is honest and
  clearly transfers to a project-management posting; "led project management
  for engineering teams" is not, if the candidate's actual facts never
  describe owning a PM role.) The goal is surfacing real, relevant breadth a
  narrow keyword-match view would hide -- not manufacturing experience that
  isn't there.
- Weave in the job's ATS keywords (given to you below) naturally, inside a
  sentence describing real work -- e.g. if a cited fact already demonstrates
  "Terraform" and the job lists "Infrastructure as Code" as a keyword, it's
  fine to phrase the bullet using both terms together. Never insert a
  keyword a bullet's cited fact(s) don't actually support, and never append
  keywords as a bare list or tag -- a modern ATS/AI screener flags keyword
  stuffing as manipulative, and this candidate does not want that. If a
  keyword isn't genuinely backed by any fact, leave it out rather than force
  it in.
- Assign each bullet a priority (1 = most important to keep if the CV must be
  shortened, higher numbers = cut first). Prioritize bullets that support a
  requirement with confirmed evidence, especially must-have requirements.
- Set matched_requirement_ids to the requirement ids (from the input) this
  bullet is relevant to. Only include requirement ids that were given to you.
- Set has_metric to true only if the bullet text itself contains a real number
  that came from the cited fact (not an estimate you added).
- List keywords actually present in the bullet text that overlap with the
  job's ATS keywords -- do not list a keyword the bullet text doesn't contain.
- Cover EVERY experience entry given to you -- every experience_id in the fact
  catalog must get at least 1 bullet in your output, even if that role has no
  connection to this specific job. This candidate wants their full breadth of
  experience visible on every CV, not just the parts that match one posting.
  Never return an empty bullets list for an experience_id that exists in the
  input.
- Within that constraint, select bullets by RELEVANCE and IMPACT, not an
  arbitrary count. For the current/most recent role, and any other role
  genuinely relevant to this job, include every distinct, non-redundant
  bullet that either (a) supports a job requirement with confirmed evidence,
  or (b) demonstrates clear quantifiable impact (a real metric from the
  fact). Don't self-censor down to a token handful just to look brief -- a
  rich, relevant role can reasonably carry 6-10 bullets if the underlying
  facts genuinely support that many distinct points. For roles with weak or
  no relevance to this job, still show the role's own most interesting and
  impactful facts (typically 2-5 bullets, or fewer only if the role's fact
  catalog genuinely doesn't have more) -- their purpose is demonstrating that
  this candidate did substantive, engaging work everywhere, not just token
  continuity. A role with a rich fact catalog should not be flattened to a
  single line just because it doesn't match this specific posting. Never
  include two bullets that restate the same underlying point. The input tells you the target
  page count -- a downstream mechanism trims lowest-priority bullets first
  if the total doesn't fit, using the priority you assign below, and it
  never empties a role to zero. Your job here is to make sure nothing
  genuinely valuable is missing from the draft, not to pre-guess the page
  budget yourself.

The single most important rule: every word of every bullet must be
traceable to the fact id(s) you cited for it. When in doubt, cut the bullet or
soften the claim -- never embellish. A shorter, 100%-true CV beats a longer,
impressive-sounding one that overstates the candidate."""


class DraftBullet(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str
    source_fact_ids: list[str]
    matched_requirement_ids: list[str] = Field(default_factory=list)
    priority: int
    keywords: list[str] = Field(default_factory=list)
    has_metric: bool


class DraftExperienceSection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    experience_id: str
    bullets: list[DraftBullet]


class DraftCv(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str
    summary_source_fact_ids: list[str]
    experience: list[DraftExperienceSection]


def _confirmed_evidence_text(requirements: list[dict], evidence_matches: list[EvidenceMatch]) -> str:
    req_text = {r["id"]: r["text"] for r in requirements}
    by_requirement: dict[str, list[str]] = {}
    for m in evidence_matches:
        if m.must_not_claim or m.candidate_fact_id is None:
            continue
        by_requirement.setdefault(m.requirement_id, []).append(m.candidate_fact_id)

    if not by_requirement:
        return "(No requirement has confirmed supporting evidence in the candidate's profile.)"

    lines = []
    for req_id, fact_ids in by_requirement.items():
        text = req_text.get(req_id, req_id)
        lines.append(f"- {req_id} ({text}): confirmed facts = {', '.join(fact_ids)}")
    return "\n".join(lines)


def _fact_catalog_by_experience(profile: CandidateProfile) -> str:
    blocks = []
    for exp in profile.experience:
        lines = [f"experience_id={exp.id} | {exp.position} at {exp.company} ({exp.start_date} - {exp.end_date or 'present'})"]
        if exp.technologies:
            lines.append(f"  technologies used: {', '.join(exp.technologies)}")
        for r in exp.responsibilities:
            lines.append(f"  - id={r.id} [responsibility] {r.statement}")
        for a in exp.achievements:
            extras = []
            if a.metrics:
                extras.append("metrics: " + "; ".join(f"{m.value}{m.unit} ({m.context})" for m in a.metrics))
            if a.technologies:
                extras.append("tech: " + ", ".join(a.technologies))
            suffix = f" | {' | '.join(extras)}" if extras else ""
            lines.append(f"  - id={a.id} [achievement] {a.statement}{suffix}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def _summary_facts_text(profile: CandidateProfile) -> str:
    return "\n".join(f"- id={f.id}: {f.statement}" for f in profile.summary_facts)


def _skills_text(profile: CandidateProfile) -> str:
    return ", ".join(s.name for s in profile.skills)


def run_drafting(
    db: Session,
    settings: Settings,
    *,
    job: JobPosting,
    profile: CandidateProfile,
    requirements: list[dict],
    evidence_matches: list[EvidenceMatch],
    target_pages: int,
    ats_keywords: list[str] | None = None,
    cv_generation_id: str | None = None,
) -> tuple[DraftCv, float]:
    user_content = "\n\n".join(
        [
            f"Job: {job.position_title} at {job.company_name}",
            f"Target length: {target_pages} page(s). Select by relevance and impact, not an "
            f"arbitrary bullet count -- see the system instructions.",
            "Requirements:\n" + "\n".join(f"- {r['id']}: {r['text']}" for r in requirements),
            "Confirmed evidence per requirement:\n" + _confirmed_evidence_text(requirements, evidence_matches),
            "Job's ATS keywords (weave in naturally where a fact genuinely supports "
            "one -- see the system instructions; never force one in):\n"
            + (", ".join(ats_keywords) if ats_keywords else "(none extracted for this posting)"),
            "Candidate summary facts:\n" + _summary_facts_text(profile),
            "Candidate experience fact catalog:\n" + _fact_catalog_by_experience(profile),
            "Candidate skills:\n" + _skills_text(profile),
        ]
    )
    return call_structured(
        db,
        settings,
        stage="drafting",
        model=settings.llm_model_drafting,
        system_prompt=_SYSTEM_PROMPT,
        user_content=user_content,
        response_model=DraftCv,
        prompt_version=PROMPT_VERSION,
        job_posting_id=job.id,
        cv_generation_id=cv_generation_id,
        max_tokens=16000,
        effort="medium",
    )


@dataclass
class DraftValidationReport:
    dropped_bullets: list[str] = field(default_factory=list)
    dropped_summary: bool = False
    backfilled_experience_ids: list[str] = field(default_factory=list)


def _fallback_bullet(exp) -> CvBullet | None:
    """Deterministic, always-valid fallback for an experience entry the model
    left empty: the first achievement (reads best standalone) or else the
    first responsibility, copied verbatim from the profile -- guaranteed to
    cite a real fact id since nothing was rephrased."""
    if exp.achievements:
        a = exp.achievements[0]
        return CvBullet(text=a.statement, source_fact_ids=[a.id], priority=99, has_metric=bool(a.metrics))
    if exp.responsibilities:
        r = exp.responsibilities[0]
        return CvBullet(text=r.statement, source_fact_ids=[r.id], priority=99, has_metric=False)
    return None


def build_verified_structured_cv(
    profile: CandidateProfile,
    job: JobPosting,
    draft: DraftCv,
    known_requirement_ids: set[str],
) -> tuple[StructuredCv, DraftValidationReport]:
    report = DraftValidationReport()
    summary_fact_ids = {f.id for f in profile.summary_facts}

    summary = draft.summary
    if not draft.summary_source_fact_ids or any(
        fid not in summary_fact_ids for fid in draft.summary_source_fact_ids
    ):
        report.dropped_summary = True
        summary = profile.summary_facts[0].statement if profile.summary_facts else ""

    draft_by_experience = {section.experience_id: section for section in draft.experience}

    experience_entries: list[CvExperienceEntry] = []
    for exp in profile.experience:
        allowed_ids = {r.id for r in exp.responsibilities} | {a.id for a in exp.achievements}
        section = draft_by_experience.get(exp.id)
        bullets: list[CvBullet] = []
        if section is not None:
            for b in section.bullets:
                if not b.source_fact_ids or any(fid not in allowed_ids for fid in b.source_fact_ids):
                    report.dropped_bullets.append(b.text)
                    continue
                bullets.append(
                    CvBullet(
                        text=b.text,
                        source_fact_ids=b.source_fact_ids,
                        matched_requirement_ids=[
                            rid for rid in b.matched_requirement_ids if rid in known_requirement_ids
                        ],
                        priority=b.priority,
                        keywords=b.keywords,
                        has_metric=b.has_metric,
                    )
                )
        bullets.sort(key=lambda b: b.priority)

        if not bullets:
            # The model omitted this role entirely, or every bullet it drafted
            # for it got rejected -- the candidate wants every role visible on
            # every CV, so backfill one bullet straight from the profile
            # (guaranteed real, since it's copied verbatim) rather than
            # showing the role with nothing under it.
            fallback = _fallback_bullet(exp)
            if fallback is not None:
                bullets = [fallback]
                report.backfilled_experience_ids.append(exp.id)

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

    structured = StructuredCv(
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
    return structured, report
