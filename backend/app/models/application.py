from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UTCDateTime, new_uuid, utcnow

# channel: company_form | email | linkedin | recruiter | other
# status mirrors the applicable subset of job_postings.workflow_status
#   (applied | responded | hr_interview | technical_interview | offer |
#    rejected | withdrawn -- see APPLICATION_STATUSES in
#    services/applications/service.py for the authoritative set)


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    job_posting_id: Mapped[str] = mapped_column(String(36), ForeignKey("job_postings.id"), nullable=False)
    cv_generation_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("cv_generations.id"), nullable=True
    )

    applied_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    channel: Mapped[str] = mapped_column(String(16), nullable=False, default="other")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="applied")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utcnow, onupdate=utcnow
    )

    job_posting: Mapped["JobPosting"] = relationship(back_populates="applications")
    cv_generation: Mapped[Optional["CvGeneration"]] = relationship(back_populates="applications")
    events: Mapped[list["ApplicationEvent"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )


class ApplicationEvent(Base):
    __tablename__ = "application_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    application_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("applications.id"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    from_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    to_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    application: Mapped["Application"] = relationship(back_populates="events")
