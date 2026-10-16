from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, computed_field


class CvGenerationCreateRequest(BaseModel):
    language: str = "en"
    target_pages: Optional[int] = None


class CvGenerationRead(BaseModel):
    id: str
    job_posting_id: str
    version_number: int
    language: str
    target_pages: int
    status: str
    pdf_page_count: Optional[int]
    fact_check_status: str
    ats_score: Optional[float]
    error_stage: Optional[str]
    error_message: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]
    pdf_path: Optional[str] = None
    latex_path: Optional[str] = None
    model_provider: Optional[str] = None
    model_name: Optional[str] = None

    # Aggregated from llm_runs for this generation -- not ORM attributes, set
    # explicitly by the API handler (None means "not computed", not "zero cost").
    total_cost_usd: Optional[float] = None
    total_input_tokens: Optional[int] = None
    total_output_tokens: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def has_pdf(self) -> bool:
        return bool(self.pdf_path)

    @computed_field
    @property
    def has_tex(self) -> bool:
        return bool(self.latex_path)


class GenerationEventRead(BaseModel):
    id: str
    stage: str
    status: str
    message: Optional[str]
    started_at: datetime
    completed_at: Optional[datetime]
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cost_usd: Optional[float] = None
    model: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
