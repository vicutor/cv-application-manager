from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import JSON, Boolean, Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UTCDateTime, new_uuid, utcnow

# source_type: url | pasted_text | feed | extension
# remote_mode: remote | hybrid | onsite | unknown
# workflow_status: new | analyzed | cv_generated | applied | responded |
#                   hr_interview | technical_interview | offer | rejected |
#                   withdrawn | closed | archived


class JobPosting(Base):
    __tablename__ = "job_postings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)

    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_name: Mapped[str] = mapped_column(String(64), nullable=False, default="generic")
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    canonical_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    external_job_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    position_title: Mapped[str] = mapped_column(String(255), nullable=False)
    location_text: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    remote_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    employment_types: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    salary_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    salary_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    salary_currency: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    salary_period: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    salary_is_gross: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    description_raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    description_clean_text: Mapped[str] = mapped_column(Text, nullable=False)
    description_language: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)

    requirements: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    responsibilities: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    nice_to_have: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    technologies: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    benefits: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    company_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    published_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    expires_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    dedupe_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    duplicate_of_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("job_postings.id"), nullable=True
    )

    match_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    match_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    workflow_status: Mapped[str] = mapped_column(String(32), nullable=False, default="new")

    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utcnow, onupdate=utcnow
    )

    sources: Mapped[list["JobSource"]] = relationship(
        back_populates="job_posting", cascade="all, delete-orphan"
    )
    analyses: Mapped[list["JobAnalysis"]] = relationship(
        back_populates="job_posting", cascade="all, delete-orphan"
    )
    cv_generations: Mapped[list["CvGeneration"]] = relationship(
        back_populates="job_posting", cascade="all, delete-orphan"
    )
    applications: Mapped[list["Application"]] = relationship(
        back_populates="job_posting", cascade="all, delete-orphan"
    )
    cover_letters: Mapped[list["CoverLetter"]] = relationship(
        back_populates="job_posting", cascade="all, delete-orphan"
    )


class JobSource(Base):
    __tablename__ = "job_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    job_posting_id: Mapped[str] = mapped_column(String(36), ForeignKey("job_postings.id"), nullable=False)

    source_name: Mapped[str] = mapped_column(String(64), nullable=False)
    original_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    canonical_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    external_job_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    http_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    raw_artifact_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fetch_method: Mapped[str] = mapped_column(String(16), nullable=False, default="manual")
    fetch_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    job_posting: Mapped["JobPosting"] = relationship(back_populates="sources")
