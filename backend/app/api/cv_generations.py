from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.cv_generation import CvGeneration
from app.models.generation_event import GenerationEvent
from app.models.job_posting import JobPosting
from app.models.llm_run import LlmRun
from app.schemas.cv_generation import CvGenerationRead, GenerationEventRead
from app.services.cv_generation.cost import attach_cost_totals
from app.services.cv_generation.pipeline import run_generation

router = APIRouter(prefix="/cv-generations", tags=["cv-generations"])


def _get_generation_or_404(db: Session, generation_id: str) -> CvGeneration:
    generation = db.get(CvGeneration, generation_id)
    if generation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="cv generation not found")
    return generation


@router.get("/{generation_id}", response_model=CvGenerationRead)
def get_cv_generation(generation_id: str, db: Session = Depends(get_db)):
    generation = _get_generation_or_404(db, generation_id)
    attach_cost_totals(db, [generation])
    return generation


@router.get("/{generation_id}/events", response_model=list[GenerationEventRead])
def list_generation_events(generation_id: str, db: Session = Depends(get_db)):
    generation = _get_generation_or_404(db, generation_id)
    events = db.scalars(
        select(GenerationEvent)
        .where(GenerationEvent.cv_generation_id == generation.id)
        .order_by(GenerationEvent.started_at)
    ).all()

    llm_run_ids = [ev.llm_run_id for ev in events if ev.llm_run_id]
    llm_runs_by_id = {}
    if llm_run_ids:
        llm_runs_by_id = {
            run.id: run for run in db.scalars(select(LlmRun).where(LlmRun.id.in_(llm_run_ids))).all()
        }

    result = []
    for ev in events:
        llm_run = llm_runs_by_id.get(ev.llm_run_id) if ev.llm_run_id else None
        result.append(
            GenerationEventRead(
                id=ev.id,
                stage=ev.stage,
                status=ev.status,
                message=ev.message,
                started_at=ev.started_at,
                completed_at=ev.completed_at,
                input_tokens=llm_run.input_tokens if llm_run else None,
                output_tokens=llm_run.output_tokens if llm_run else None,
                cost_usd=llm_run.estimated_cost_usd if llm_run else None,
                model=llm_run.model if llm_run else None,
            )
        )
    return result


@router.get("/{generation_id}/pdf")
def download_pdf(generation_id: str, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    generation = _get_generation_or_404(db, generation_id)
    if not generation.pdf_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="pdf not available")
    job = db.get(JobPosting, generation.job_posting_id)
    filename = _friendly_filename(job, generation, "pdf") if job else "cv.pdf"
    return FileResponse(
        settings.data_dir / generation.pdf_path, media_type="application/pdf", filename=filename
    )


@router.get("/{generation_id}/tex")
def download_tex(generation_id: str, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    generation = _get_generation_or_404(db, generation_id)
    if not generation.latex_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="tex source not available")
    job = db.get(JobPosting, generation.job_posting_id)
    filename = _friendly_filename(job, generation, "tex") if job else "cv.tex"
    return FileResponse(
        settings.data_dir / generation.latex_path, media_type="text/x-tex", filename=filename
    )


@router.post("/{generation_id}/retry", status_code=status.HTTP_202_ACCEPTED, response_model=CvGenerationRead)
def retry_cv_generation(
    generation_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    generation = _get_generation_or_404(db, generation_id)
    if generation.status not in ("failed",):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="only a failed generation can be retried"
        )
    generation.status = "queued"
    generation.error_stage = None
    generation.error_message = None
    db.commit()
    background_tasks.add_task(run_generation, generation.id, settings)
    return generation


def _friendly_filename(job: JobPosting, generation: CvGeneration, ext: str) -> str:
    company = job.company_name.replace(" ", "_")
    position = job.position_title.replace(" ", "_")
    return f"CV_{company}_{position}_v{generation.version_number}.{ext}"
