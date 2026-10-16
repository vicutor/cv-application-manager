from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UTCDateTime, new_uuid, utcnow

# match_type: direct | partial | transferable | none


class JobAnalysis(Base):
    __tablename__ = "job_analyses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    job_posting_id: Mapped[str] = mapped_column(String(36), ForeignKey("job_postings.id"), nullable=False)
    analysis_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    must_have: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    nice_to_have: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    responsibilities: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    ats_keywords: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    seniority_signals: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    domain_signals: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    screening_risks: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)

    model_provider: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    model_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    job_posting: Mapped["JobPosting"] = relationship(back_populates="analyses")
    evidence_matches: Mapped[list["EvidenceMatch"]] = relationship(
        back_populates="job_analysis", cascade="all, delete-orphan"
    )


class EvidenceMatch(Base):
    __tablename__ = "evidence_matches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    job_analysis_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("job_analyses.id"), nullable=False
    )
    requirement_id: Mapped[str] = mapped_column(String(128), nullable=False)
    candidate_fact_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    match_type: Mapped[str] = mapped_column(String(16), nullable=False, default="none")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    must_not_claim: Mapped[bool] = mapped_column(nullable=False, default=False)

    job_analysis: Mapped["JobAnalysis"] = relationship(back_populates="evidence_matches")
