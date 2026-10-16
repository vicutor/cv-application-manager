from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UTCDateTime, new_uuid, utcnow

# status: queued | analyzing | matching | drafting | fact_checking | ats_checking |
#         style | writing_latex | compiling | validating | succeeded | failed
# fact_check_status: pending | passed | corrected | failed | overridden
#   "corrected": the LLM fact audit flagged an embellishment and it was
#   automatically reverted to verbatim source text (see
#   fact_audit.apply_fact_audit_corrections) -- the CV is still fully
#   evidence-bound, just not the model's first-draft phrasing everywhere.


class CvGeneration(Base):
    __tablename__ = "cv_generations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    job_posting_id: Mapped[str] = mapped_column(String(36), ForeignKey("job_postings.id"), nullable=False)
    candidate_profile_version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("candidate_profile_versions.id"), nullable=False
    )
    job_analysis_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("job_analyses.id"), nullable=True
    )

    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="en")
    target_pages: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")

    model_provider: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    model_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    generation_config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    structured_cv_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    latex_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pdf_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pdf_page_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    pdf_text_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    ats_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fact_check_status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")

    error_stage: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime(), nullable=True)

    job_posting: Mapped["JobPosting"] = relationship(back_populates="cv_generations")
    applications: Mapped[list["Application"]] = relationship(back_populates="cv_generation")
    events: Mapped[list["GenerationEvent"]] = relationship(
        back_populates="cv_generation", cascade="all, delete-orphan"
    )
