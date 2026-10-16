from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UTCDateTime, new_uuid, utcnow

# status: drafting | ai_check | succeeded | failed


class CoverLetter(Base):
    __tablename__ = "cover_letters"

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
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="drafting")

    content_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    word_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    latex_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pdf_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Whether the AI-check stage judged the draft to read as AI-generated
    # (and therefore rewrote it) -- kept even after rewriting so the user can
    # see the check actually ran, not just trust a silent pass.
    sounds_ai_flagged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ai_check_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    model_provider: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    model_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    error_stage: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime(), nullable=True)

    job_posting: Mapped["JobPosting"] = relationship(back_populates="cover_letters")
