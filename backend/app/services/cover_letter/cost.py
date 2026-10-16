from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.cover_letter import CoverLetter
from app.models.llm_run import LlmRun


def attach_cost_totals(db: Session, cover_letters: list[CoverLetter]) -> list[CoverLetter]:
    """Same pattern as cv_generation.cost.attach_cost_totals: total_cost_usd is
    always derived from llm_runs, never stored, and set as a plain attribute
    CoverLetterRead picks up via from_attributes."""
    if not cover_letters:
        return cover_letters
    ids = [c.id for c in cover_letters]
    rows = db.execute(
        select(LlmRun.cover_letter_id, func.sum(LlmRun.estimated_cost_usd))
        .where(LlmRun.cover_letter_id.in_(ids))
        .group_by(LlmRun.cover_letter_id)
    ).all()
    totals = {row[0]: (row[1] or 0.0) for row in rows}
    for c in cover_letters:
        c.total_cost_usd = totals.get(c.id, 0.0)
    return cover_letters
