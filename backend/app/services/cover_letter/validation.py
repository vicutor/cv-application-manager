"""Deterministic fact-citation check for a cover-letter draft -- the safety
net between the model's draft and what actually gets saved, mirroring
build_verified_structured_cv() for CV bullets.

Unlike a CV, where a bullet citing a bad fact id gets dropped and the CV
still reads fine with one fewer bullet, a 3-paragraph cover letter can't
gracefully lose a paragraph -- so this fails the whole draft rather than
silently shipping a truncated letter. The caller (generation.py) turns that
into a "failed" status the user can just retry rather than a mangled result.
"""

from app.services.candidate_profile.schema import CandidateProfile
from app.services.candidate_profile.validation import collect_fact_ids
from app.services.cover_letter.drafting import CoverLetterDraft


def validate_cover_letter_draft(profile: CandidateProfile, draft: CoverLetterDraft) -> tuple[str, bool]:
    """Returns (assembled_text, all_valid)."""
    known_ids = collect_fact_ids(profile)
    all_valid = bool(draft.paragraphs) and all(
        p.source_fact_ids and all(fid in known_ids for fid in p.source_fact_ids) for p in draft.paragraphs
    )
    text = "\n\n".join(p.text for p in draft.paragraphs)
    return text, all_valid
