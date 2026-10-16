from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UTCDateTime, new_uuid, utcnow

# validation_status: valid | invalid | pending


class CandidateProfileVersion(Base):
    __tablename__ = "candidate_profile_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    yaml_path: Mapped[str] = mapped_column(String(512), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    validation_status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    validation_errors: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
