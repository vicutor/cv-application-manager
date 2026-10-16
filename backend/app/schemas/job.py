from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.application import ApplicationRead


class DuplicateInfo(BaseModel):
    job_posting_id: str
    match_level: str  # "exact" | "likely"
    company_name: str
    position_title: str


class JobImportUrlRequest(BaseModel):
    url: str = Field(min_length=1)


class JobImportHtmlRequest(BaseModel):
    html: str = Field(min_length=1)
    source_url: str = Field(min_length=1)


class JobImportListingRequest(BaseModel):
    listing_url: str = Field(min_length=1)


class BulkImportItemResponse(BaseModel):
    url: str
    status: str  # "imported" | "duplicate" | "skipped_no_structured_data" | "failed"
    job_posting_id: Optional[str] = None
    company_name: Optional[str] = None
    position_title: Optional[str] = None
    reason: Optional[str] = None


class BulkImportReportResponse(BaseModel):
    listing_url: str
    discovered_count: int
    imported_count: int
    duplicate_count: int
    items: list[BulkImportItemResponse]


class JobImportUrlPreviewResponse(BaseModel):
    extraction_method: str  # "json_ld" | "manual"
    canonical_url: str
    source_name: str
    staging_token: str
    company_name: str
    position_title: str
    location_text: Optional[str]
    remote_mode: str
    employment_types: list[str]
    salary_min: Optional[float]
    salary_max: Optional[float]
    salary_currency: Optional[str]
    salary_period: Optional[str]
    description_raw_text: str
    description_clean_text: str
    published_at: Optional[date]
    expires_at: Optional[date]
    external_job_id: Optional[str]
    technologies: list[str]
    duplicate: Optional[DuplicateInfo] = None


class JobImportUrlConfirmRequest(BaseModel):
    canonical_url: str
    staging_token: str = ""
    external_job_id: Optional[str] = None
    company_name: str = Field(min_length=1)
    position_title: str = Field(min_length=1)
    location_text: Optional[str] = None
    remote_mode: str = "unknown"
    employment_types: list[str] = Field(default_factory=list)
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_currency: Optional[str] = None
    salary_period: Optional[str] = None
    description_raw_text: str = Field(min_length=1)
    description_clean_text: str = ""
    published_at: Optional[date] = None
    expires_at: Optional[date] = None
    technologies: list[str] = Field(default_factory=list)
    allow_duplicate: bool = False


class AttachSourceRequest(BaseModel):
    canonical_url: str
    staging_token: str = ""
    source_name: str
    external_job_id: Optional[str] = None


class JobSourceRead(BaseModel):
    id: str
    source_name: str
    original_url: Optional[str]
    canonical_url: Optional[str]
    fetch_method: str
    fetched_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JobImportTextRequest(BaseModel):
    raw_text: str = Field(min_length=20, description="Full pasted job posting text")
    source_url: Optional[str] = None
    company_name: str = Field(min_length=1)
    position_title: str = Field(min_length=1)
    location_text: Optional[str] = None
    remote_mode: str = "unknown"
    technologies: list[str] = Field(default_factory=list)
    allow_duplicate: bool = False


class JobPostingListItem(BaseModel):
    id: str
    company_name: str
    position_title: str
    location_text: Optional[str]
    remote_mode: str
    source_name: str
    workflow_status: str
    match_score: Optional[float]
    has_cv: bool
    applied: bool
    applied_at: Optional[datetime]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JobPostingDetail(BaseModel):
    id: str
    source_type: str
    source_name: str
    source_url: Optional[str]
    company_name: str
    position_title: str
    location_text: Optional[str]
    remote_mode: str
    employment_types: list[str]
    salary_min: Optional[float]
    salary_max: Optional[float]
    salary_currency: Optional[str]
    description_raw_text: str
    description_clean_text: str
    requirements: list
    responsibilities: list
    nice_to_have: list
    technologies: list
    benefits: list
    workflow_status: str
    match_score: Optional[float]
    match_summary: Optional[str]
    created_at: datetime
    updated_at: datetime
    sources: list[JobSourceRead] = Field(default_factory=list)
    applications: list[ApplicationRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class JobPatchRequest(BaseModel):
    company_name: Optional[str] = None
    position_title: Optional[str] = None
    location_text: Optional[str] = None
    remote_mode: Optional[str] = None
    workflow_status: Optional[str] = None
