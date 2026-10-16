from datetime import datetime, time, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.application import Application, ApplicationEvent
from app.models.cv_generation import CvGeneration
from app.models.job_posting import JobPosting
from app.schemas.application import MarkAppliedRequest

# A funnel, not strictly linear -- a real process can skip stages (straight
# to an offer) or bounce back and forth, but this is the expected order for
# "how far did I get" progress: applied -> responded -> hr_interview ->
# technical_interview -> offer. rejected/withdrawn are terminal and reachable
# from any stage. "interview" is kept only so pre-existing rows written
# before this stage set existed keep validating; new writes should use the
# more specific hr_interview/technical_interview instead.
APPLICATION_STATUSES = {
    "applied",
    "responded",
    "hr_interview",
    "technical_interview",
    "interview",
    "offer",
    "rejected",
    "withdrawn",
}


class CvGenerationNotFoundError(Exception):
    pass


class CvGenerationNotSucceededError(Exception):
    pass


def _get_active_application(db: Session, job_posting_id: str) -> Application | None:
    return db.scalars(
        select(Application)
        .where(Application.job_posting_id == job_posting_id)
        .order_by(Application.created_at.desc())
    ).first()


def mark_applied(db: Session, job: JobPosting, payload: MarkAppliedRequest) -> Application:
    """Create or update the job's single active application (spec 3.6/8: one active
    application per posting in the MVP, but every status change is recorded as an
    ApplicationEvent so history is preserved even though the row is reused).

    cv_generation_id is optional: the user may have applied with a CV they
    didn't generate through this app. When given, it's still validated to
    make sure it's a real, succeeded generation for this exact posting --
    that guarantee just doesn't apply when there's nothing to validate.
    """
    generation_id = payload.cv_generation_id
    if generation_id is not None:
        generation = db.get(CvGeneration, generation_id)
        if generation is None or generation.job_posting_id != job.id:
            raise CvGenerationNotFoundError("cv generation not found for this job posting")
        if generation.status != "succeeded":
            raise CvGenerationNotSucceededError("only a successfully generated CV can be marked as used")

    applied_at_dt = datetime.combine(payload.applied_at, time.min, tzinfo=timezone.utc)
    existing = _get_active_application(db, job.id)

    if existing is None:
        application = Application(
            job_posting_id=job.id,
            cv_generation_id=generation_id,
            applied_at=applied_at_dt,
            channel=payload.channel,
            status="applied",
            notes=payload.notes,
        )
        db.add(application)
        db.flush()
        db.add(
            ApplicationEvent(
                application_id=application.id,
                event_type="created",
                from_status=None,
                to_status="applied",
                notes=payload.notes,
            )
        )
    else:
        previous_status = existing.status
        existing.cv_generation_id = generation_id
        existing.applied_at = applied_at_dt
        existing.channel = payload.channel
        existing.status = "applied"
        existing.notes = payload.notes
        db.add(
            ApplicationEvent(
                application_id=existing.id,
                event_type="updated",
                from_status=previous_status,
                to_status="applied",
                notes=payload.notes,
            )
        )
        application = existing

    job.workflow_status = "applied"
    db.commit()
    db.refresh(application)
    return application


def update_status(db: Session, application: Application, new_status: str, notes: str | None) -> Application:
    if new_status not in APPLICATION_STATUSES:
        raise ValueError(f"invalid application status: {new_status!r}")

    previous_status = application.status
    application.status = new_status
    if notes is not None:
        application.notes = notes
    db.add(
        ApplicationEvent(
            application_id=application.id,
            event_type="status_changed",
            from_status=previous_status,
            to_status=new_status,
            notes=notes,
        )
    )

    job = db.get(JobPosting, application.job_posting_id)
    if job is not None and new_status in APPLICATION_STATUSES:
        job.workflow_status = new_status

    db.commit()
    db.refresh(application)
    return application


def list_applications(db: Session) -> list[Application]:
    return db.scalars(select(Application).order_by(Application.applied_at.desc())).all()
