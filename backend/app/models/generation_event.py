from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UTCDateTime, new_uuid, utcnow

# status: running | succeeded | failed | skipped


class GenerationEvent(Base):
    __tablename__ = "generation_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    cv_generation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("cv_generations.id"), nullable=False
    )
    llm_run_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("llm_runs.id"), nullable=True)

    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime(), nullable=True)

    cv_generation: Mapped["CvGeneration"] = relationship(back_populates="events")
