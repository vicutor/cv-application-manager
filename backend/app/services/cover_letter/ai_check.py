"""Cover-letter AI-detection self-check -- the explicit step the user asked
for: judge honestly whether the draft reads as AI-written, and if so, rewrite
it until it doesn't. This is the same "avoid-ai-writing" ruleset the CV style
pass (Etap F) uses, but framed as an auditable judgment (sounds_ai_generated
+ reasoning) rather than a silent rewrite, and applied to a much shorter,
higher-stakes piece of text where a residual AI tell is more visible.

Same hard constraint as the CV style pass: this stage may only touch rhythm
and word choice, never a fact. apply_ai_check() below independently rejects
any rewrite that introduces a number absent from the original, exactly like
apply_style_pass() does for CV bullets.
"""

import re

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.services.cv_generation.llm_client import call_structured

PROMPT_VERSION = "cover-letter-ai-check-v1"

_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")

_SYSTEM_PROMPT = """You are doing one honest self-check on a short cover
letter, written for a laid-back, easygoing candidate who wants to sound like
himself, not like a well-optimized document. Two separate failure modes both
count as "sounds AI-generated" here, and the second one is the sneakier,
more common one:

1. The obvious tells: generic uplifting phrasing, symmetric rule-of-three
   lists, hollow enthusiasm, em dashes used as connective tissue,
   "leverage/robust/seamless/cutting-edge" vocabulary, "I am excited to..."
   energy.
2. The subtler one: technically clean, on-topic, free of buzzwords, but
   still cold -- a paragraph that lists several technical facts back to
   back like an inventory, every sentence the same measured length and
   shape, zero contractions, nothing that sounds like a specific person's
   voice. This reads as "competent AI output" even with none of the obvious
   tells, and it's the more common failure here. Ask yourself: if this were
   read aloud, would it sound like a person talking, or like a paragraph
   being recited?

HARD CONSTRAINTS on any rewrite -- never violate these:
- Never add, remove, or change a number, date, company name, or technology
  name.
- Never add a claim that wasn't already in the text.
- You are fixing rhythm, word choice, and how facts are stitched together,
  not content. If you can't fix a sentence without touching what it claims,
  leave it closer to the original rather than risk changing meaning.

Judge first, honestly, against BOTH failure modes above: does the text below
read as AI-written? Set sounds_ai_generated accordingly and explain briefly
in reasoning (2-3 sentences, specific about which patterns and where) --
don't default to "looks fine" just because it avoids the obvious buzzwords.

Then:
- If sounds_ai_generated is true, rewrite it so it reads like a specific,
  laid-back person wrote it in one sitting: use contractions, vary sentence
  length and rhythm, if a sentence lists more than two technical facts back
  to back cut it down to the single most important one instead of just
  rephrasing the list, replace hollow abstractions with the concrete detail
  already present in the text.
- If sounds_ai_generated is false, return the text unchanged in
  revised_text.

Return sounds_ai_generated, reasoning, and revised_text."""


class CoverLetterAiCheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sounds_ai_generated: bool
    reasoning: str
    revised_text: str


def run_cover_letter_ai_check(
    db: Session,
    settings: Settings,
    *,
    text: str,
    job_posting_id: str | None = None,
    cover_letter_id: str | None = None,
) -> tuple[CoverLetterAiCheckResult, float]:
    return call_structured(
        db,
        settings,
        stage="cover_letter_ai_check",
        model=settings.llm_model_style,
        system_prompt=_SYSTEM_PROMPT,
        user_content=f'Cover letter text:\n"""\n{text}\n"""',
        response_model=CoverLetterAiCheckResult,
        prompt_version=PROMPT_VERSION,
        job_posting_id=job_posting_id,
        cover_letter_id=cover_letter_id,
        max_tokens=4096,
        effort="medium",
    )


def apply_ai_check(original_text: str, result: CoverLetterAiCheckResult) -> tuple[str, bool]:
    """Returns (final_text, rewrite_rejected). Mirrors apply_style_pass's
    digit-preservation guard: a rewrite that introduces a number the
    original didn't have is rejected outright, keeping the original text
    even though sounds_ai_generated may still be true -- silently trusting
    the rewrite here is exactly the kind of ungrounded step this pipeline
    doesn't take."""
    if not result.sounds_ai_generated:
        return original_text, False

    original_numbers = set(_NUMBER_RE.findall(original_text))
    revised_numbers = set(_NUMBER_RE.findall(result.revised_text))
    if not revised_numbers <= original_numbers:
        return original_text, True

    return result.revised_text, False
