from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class ExtractedJobCandidate:
    """Common output shape every extraction strategy (JSON-LD, a future per-domain
    adapter, generic HTML, or an LLM fallback) converges on before it reaches the
    dedupe/save step. Business logic downstream never branches on source_name.
    """

    company_name: str = ""
    position_title: str = ""
    location_text: Optional[str] = None
    remote_mode: str = "unknown"
    employment_types: list[str] = field(default_factory=list)
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_currency: Optional[str] = None
    salary_period: Optional[str] = None
    description_raw_text: str = ""
    description_clean_text: str = ""
    published_at: Optional[date] = None
    expires_at: Optional[date] = None
    external_job_id: Optional[str] = None
    technologies: list[str] = field(default_factory=list)
    extraction_method: str = "manual"  # "json_ld" | "manual"
