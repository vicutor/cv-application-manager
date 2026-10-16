from datetime import datetime
from typing import Optional

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UTCDateTime, new_uuid, utcnow

# status: success | error | timeout | rate_limited
# Never store API keys or secrets here.


class LlmRun(Base):
    __tablename__ = "llm_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    job_posting_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("job_postings.id"), nullable=True
    )
    cv_generation_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("cv_generations.id"), nullable=True
    )
    cover_letter_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("cover_letters.id"), nullable=True
    )

    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    input_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    estimated_cost_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    status: Mapped[str] = mapped_column(String(16), nullable=False)
    request_artifact_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    response_artifact_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
