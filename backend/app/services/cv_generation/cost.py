from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.cv_generation import CvGeneration
from app.models.llm_run import LlmRun


def attach_cost_totals(db: Session, generations: list[CvGeneration]) -> list[CvGeneration]:
    """Sets total_cost_usd/total_input_tokens/total_output_tokens as plain
    attributes on each ORM instance (not mapped columns -- these are always
    derived from llm_runs, never stored). CvGenerationRead picks them up via
    from_attributes when the API handler returns these objects directly."""
    if not generations:
        return generations
    ids = [g.id for g in generations]
    rows = db.execute(
        select(
            LlmRun.cv_generation_id,
            func.sum(LlmRun.estimated_cost_usd),
            func.sum(LlmRun.input_tokens),
            func.sum(LlmRun.output_tokens),
        )
        .where(LlmRun.cv_generation_id.in_(ids))
        .group_by(LlmRun.cv_generation_id)
    ).all()
    totals = {row[0]: (row[1] or 0.0, row[2] or 0, row[3] or 0) for row in rows}
    for g in generations:
        cost, in_tok, out_tok = totals.get(g.id, (0.0, 0, 0))
        g.total_cost_usd = cost
        g.total_input_tokens = in_tok
        g.total_output_tokens = out_tok
    return generations
