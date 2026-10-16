"""Etap F -- style pass, using the vendored `avoid-ai-writing` skill (MIT,
conorbronsdon/avoid-ai-writing -- see vendor/avoid-ai-writing/PROVENANCE.md) as
the reference ruleset for removing AI-sounding writing patterns.

Applies ONLY to the summary and experience bullet text, per spec (Etap F).
Never touches: technology names, numbers, dates, company/position names, the
skills section, needed/true keywords, or source fact ids -- the model is told
this explicitly, and apply_style_pass() below independently rejects any
rewritten line that introduces a number absent from the original (a cheap,
deterministic guard against the style pass quietly fabricating a metric while
"improving" the prose). Per spec, fact-check and ATS coverage must be re-run
after this stage -- that's orchestrated by the pipeline (run_generation), not
here, since it just reuses the existing fact_audit/ats_audit functions.
"""

import re
from dataclasses import dataclass, field, replace

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.services.candidate_profile.schema import CandidateProfile
from app.services.cv_generation.llm_client import call_structured
from app.services.latex.render import CvExperienceEntry, StructuredCv

PROMPT_VERSION = "style-pass-avoid-ai-writing-v1"

_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")

# Condensed from the vendored SKILL.md (Tier 1A/1B/Tier 2 word tables, sentence
# structure rules, template/transition phrases) -- the subset that actually
# shows up in short professional bullets, not the long-form-blog-specific
# sections (hashtag stuffing, paragraph rhythm, etc.) that don't apply here.
_SYSTEM_PROMPT = """You are a style editor rewriting a CV's summary and
experience bullets to remove AI-sounding writing patterns, using the rules
below (condensed from the open-source "avoid-ai-writing" skill).

HARD CONSTRAINTS -- never violate these, even to improve the prose:
- Do not add, remove, or change any number (metric, percentage, count, years).
- Do not add, remove, or change any date, company name, position title, or
  technology name.
- Do not add any claim, scope, or outcome that wasn't already in the text.
- Do not remove a keyword that is accurate and relevant just to sound less
  repetitive -- only cut a keyword if it was genuinely redundant filler.
- You are rewriting STYLE, not content. If you can't find a way to de-AI a
  sentence without changing its factual content, leave it closer to the
  original rather than risk altering meaning.

STYLE RULES:
- Em dashes: eliminate. Use a comma, period, or two sentences instead.
- Cut hollow intensifiers: "genuinely", "truly", "really", "actually" (when
  just adding emphasis), "quite frankly".
- Cut hedging filler: "it's worth noting that", "to be clear".
- Avoid the compulsive rule-of-three ("adjective, adjective, and adjective")
  -- use one or two instead.
- Replace Tier-1 AI-frequency words on sight: "leverage" -> use; "robust" ->
  strong/reliable; "seamless(ly)" -> smooth/easy; "cutting-edge" -> latest;
  "comprehensive" -> thorough/complete; "pivotal" -> important/key;
  "spearheaded" -> led/drove/ran; "streamlined" -> simplified; "utilize(d)" ->
  use(d); "in order to" -> to; "facilitate(d)" -> enable(d)/helped.
- Avoid resume-cliche filler that means nothing on its own: "results-driven",
  "detail-oriented", "proven track record", "dynamic professional",
  "extensive experience" (state the actual duration or scope instead), "team
  player", "go-getter", "responsible for" (prefer an active verb: "led",
  "built", "ran" instead of "was responsible for").
- Cut generic transition phrases: "moreover", "furthermore", "additionally" --
  just use "and" or restructure, or drop the connector entirely.
- Avoid significance inflation ("played a pivotal role", "drove significant
  impact") -- state the concrete action and result instead.
- Prefer active voice and a strong verb at the start of each bullet.
- Vary sentence openings across bullets -- don't start every bullet with the
  same verb or pattern.

Return the summary and, for each experience section given to you, one entry
per bullet_index you were given (same order, same indices), with the rewritten
text. If a bullet already reads naturally and has no AI-sounding patterns,
return it unchanged."""


class StyledBullet(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bullet_index: int
    text: str


class StyledExperienceSection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    experience_id: str
    bullets: list[StyledBullet]


class StylePassResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str
    experience: list[StyledExperienceSection]


def _build_user_content(structured: StructuredCv, profile: CandidateProfile) -> str:
    lines = [f'Summary: "{structured.summary}"']
    for exp, entry in zip(profile.experience, structured.experience):
        if not entry.bullets:
            continue
        lines.append(f"\nexperience_id={exp.id} ({entry.position} @ {entry.company}):")
        for i, bullet in enumerate(entry.bullets):
            lines.append(f'  bullet_index={i}: "{bullet.text}"')
    return "\n".join(lines)


def run_style_pass(
    db: Session,
    settings: Settings,
    structured: StructuredCv,
    profile: CandidateProfile,
    job_posting_id: str,
    cv_generation_id: str | None = None,
) -> tuple[StylePassResult, float]:
    return call_structured(
        db,
        settings,
        stage="style",
        model=settings.llm_model_style,
        system_prompt=_SYSTEM_PROMPT,
        user_content=_build_user_content(structured, profile),
        response_model=StylePassResult,
        prompt_version=PROMPT_VERSION,
        job_posting_id=job_posting_id,
        cv_generation_id=cv_generation_id,
        max_tokens=12000,
        effort="medium",
    )


@dataclass
class StylePassReport:
    rejected_summary: bool = False
    rejected_bullets: list[str] = field(default_factory=list)


def apply_style_pass(
    structured: StructuredCv,
    profile: CandidateProfile,
    result: StylePassResult,
) -> tuple[StructuredCv, StylePassReport]:
    """Applies the rewritten text, but rejects (keeps original) any line where
    the rewrite introduces a number not present in the original -- a cheap,
    deterministic net under the "never add a metric" instruction, since a
    style pass has no business inventing or dropping a number at all."""
    report = StylePassReport()

    new_summary = structured.summary
    if set(_NUMBER_RE.findall(result.summary)) <= set(_NUMBER_RE.findall(structured.summary)):
        new_summary = result.summary
    else:
        report.rejected_summary = True

    styled_by_experience_id = {sec.experience_id: sec for sec in result.experience}

    new_experience: list[CvExperienceEntry] = []
    for exp, entry in zip(profile.experience, structured.experience):
        styled_section = styled_by_experience_id.get(exp.id)
        styled_by_index = {b.bullet_index: b.text for b in styled_section.bullets} if styled_section else {}

        new_bullets = []
        for i, bullet in enumerate(entry.bullets):
            new_text = styled_by_index.get(i, bullet.text)
            original_numbers = set(_NUMBER_RE.findall(bullet.text))
            new_numbers = set(_NUMBER_RE.findall(new_text))
            if not new_numbers <= original_numbers:
                report.rejected_bullets.append(new_text)
                new_text = bullet.text
            new_bullets.append(replace(bullet, text=new_text))
        new_experience.append(
            CvExperienceEntry(
                company=entry.company,
                position=entry.position,
                date_range=entry.date_range,
                location=entry.location,
                bullets=new_bullets,
            )
        )

    styled_structured = StructuredCv(
        full_name=structured.full_name,
        headline=structured.headline,
        location=structured.location,
        email=structured.email,
        phone=structured.phone,
        links=structured.links,
        summary=new_summary,
        experience=new_experience,
        skills=structured.skills,
        language=structured.language,
        certification_tagline=structured.certification_tagline,
        focus_tagline=structured.focus_tagline,
        photo_path=structured.photo_path,
        projects=structured.projects,
        certifications=structured.certifications,
        education=structured.education,
        languages=structured.languages,
    )
    return styled_structured, report
