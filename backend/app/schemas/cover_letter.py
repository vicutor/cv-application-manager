from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, computed_field


class CoverLetterRead(BaseModel):
    id: str
    job_posting_id: str
    version_number: int
    language: str
    status: str
    content_text: Optional[str]
    word_count: Optional[int]
    sounds_ai_flagged: bool
    ai_check_notes: Optional[str]
    pdf_path: Optional[str] = None
    latex_path: Optional[str] = None
    error_stage: Optional[str]
    error_message: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]
    total_cost_usd: float = 0.0

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def has_pdf(self) -> bool:
        return bool(self.pdf_path)

    @computed_field
    @property
    def has_tex(self) -> bool:
        return bool(self.latex_path)
