import shutil

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.application import Application
from app.models.cv_generation import CvGeneration
from app.models.job_posting import JobPosting
from app.schemas.job import JobPatchRequest, JobPostingListItem


def list_jobs(db: Session, status: str | None = None) -> list[JobPostingListItem]:
    stmt = select(JobPosting).order_by(JobPosting.created_at.desc())
    if status:
        stmt = stmt.where(JobPosting.workflow_status == status)
    postings = db.scalars(stmt).all()

    items: list[JobPostingListItem] = []
    for posting in postings:
        has_cv = (
            db.scalars(
                select(CvGeneration.id)
                .where(CvGeneration.job_posting_id == posting.id, CvGeneration.status == "succeeded")
                .limit(1)
            ).first()
            is not None
        )
        active_application = db.scalars(
            select(Application)
            .where(Application.job_posting_id == posting.id)
            .order_by(Application.applied_at.desc())
            .limit(1)
        ).first()

        items.append(
            JobPostingListItem(
                id=posting.id,
                company_name=posting.company_name,
                position_title=posting.position_title,
                location_text=posting.location_text,
                remote_mode=posting.remote_mode,
                source_name=posting.source_name,
                workflow_status=posting.workflow_status,
                match_score=posting.match_score,
                has_cv=has_cv,
                applied=active_application is not None,
                applied_at=active_application.applied_at if active_application else None,
                created_at=posting.created_at,
            )
        )
    return items


def get_job(db: Session, job_id: str) -> JobPosting | None:
    return db.get(JobPosting, job_id)


def patch_job(db: Session, job: JobPosting, patch: JobPatchRequest) -> JobPosting:
    for field, value in patch.model_dump(exclude_unset=True).items():
        setattr(job, field, value)
    db.commit()
    db.refresh(job)
    return job


def archive_job(db: Session, job: JobPosting) -> JobPosting:
    job.workflow_status = "archived"
    db.commit()
    db.refresh(job)
    return job


def delete_job(db: Session, settings: Settings, job: JobPosting) -> None:
    """Permanently removes the posting: DB row (cascades to sources, analyses,
    cv_generations, applications/events via ORM cascade="all, delete-orphan") and
    its on-disk artifact directory (source HTML, generated .tex/.pdf files).
    Irreversible -- unlike archive_job, which just hides the posting.
    """
    job_dir = settings.jobs_dir / job.id
    db.delete(job)
    db.commit()
    if job_dir.exists():
        shutil.rmtree(job_dir)
