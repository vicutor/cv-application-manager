"""Per-stage progress log for a CvGeneration. One GenerationEvent row per
pipeline stage, created "running" when the stage starts and updated in place
when it finishes -- so the frontend can poll /cv-generations/{id}/events while
a generation is in flight and render a live, non-blocking step-by-step view,
and the same rows remain afterward as a permanent record of what happened.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.models.cv_generation import CvGeneration
from app.models.generation_event import GenerationEvent
from app.models.llm_run import LlmRun


def start_event(db: Session, generation: CvGeneration, stage: str) -> GenerationEvent:
    event = GenerationEvent(cv_generation_id=generation.id, stage=stage, status="running")
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def finish_event(
    db: Session, event: GenerationEvent, status: str, message: str | None = None, llm_run_id: str | None = None
) -> None:
    event.status = status
    event.message = message
    event.llm_run_id = llm_run_id
    event.completed_at = utcnow()
    db.commit()


def latest_llm_run(db: Session, cv_generation_id: str, stage: str) -> LlmRun | None:
    return db.scalars(
        select(LlmRun)
        .where(LlmRun.cv_generation_id == cv_generation_id, LlmRun.stage == stage)
        .order_by(LlmRun.created_at.desc())
    ).first()


def llm_run_message(llm_run: LlmRun | None) -> str | None:
    if llm_run is None:
        return None
    tokens = f"{llm_run.input_tokens or 0} in / {llm_run.output_tokens or 0} out tokens"
    cost = f"${llm_run.estimated_cost_usd:.4f}" if llm_run.estimated_cost_usd is not None else "cost unknown"
    return f"{llm_run.model}: {tokens}, {cost}"
