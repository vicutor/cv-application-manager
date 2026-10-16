from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class MarkAppliedRequest(BaseModel):
    # None when the user applied with a CV they didn't generate through this
    # app (e.g. a generic/manually-written one) -- still worth tracking as
    # applied, just with nothing to link back to.
    cv_generation_id: Optional[str] = None
    applied_at: date
    channel: str = "other"
    notes: Optional[str] = None


class ApplicationStatusUpdateRequest(BaseModel):
    status: str
    notes: Optional[str] = None


class ApplicationRead(BaseModel):
    id: str
    job_posting_id: str
    cv_generation_id: Optional[str]
    applied_at: datetime
    channel: str
    status: str
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
