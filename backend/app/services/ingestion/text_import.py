from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.job_posting import JobPosting, JobSource
from app.schemas.job import JobImportTextRequest
from app.services.deduplication.fingerprint import content_hash, dedupe_fingerprint
from app.services.deduplication.service import DuplicateMatch, find_duplicate
from app.services.extraction.text_cleaning import clean_text


@dataclass
class TextImportOutcome:
    job_posting: JobPosting | None
    duplicate: DuplicateMatch | None


def import_from_text(db: Session, request: JobImportTextRequest) -> TextImportOutcome:
    cleaned = clean_text(request.raw_text)
    c_hash = content_hash(cleaned)
    fingerprint = dedupe_fingerprint(request.company_name, request.position_title, request.location_text)

    duplicate = find_duplicate(db, c_hash, fingerprint)
    if duplicate is not None and not request.allow_duplicate:
        return TextImportOutcome(job_posting=None, duplicate=duplicate)

    job_posting = JobPosting(
        source_type="pasted_text",
        source_name="generic",
        source_url=request.source_url,
        canonical_url=request.source_url,
        company_name=request.company_name,
        position_title=request.position_title,
        location_text=request.location_text,
        remote_mode=request.remote_mode,
        employment_types=[],
        description_raw_text=request.raw_text,
        description_clean_text=cleaned,
        technologies=request.technologies,
        requirements=[],
        responsibilities=[],
        nice_to_have=[],
        benefits=[],
        content_hash=c_hash,
        dedupe_fingerprint=fingerprint,
        workflow_status="new",
    )
    db.add(job_posting)
    db.flush()

    source = JobSource(
        job_posting_id=job_posting.id,
        source_name="generic",
        original_url=request.source_url,
        canonical_url=request.source_url,
        fetch_method="manual",
    )
    db.add(source)
    db.commit()
    db.refresh(job_posting)

    return TextImportOutcome(job_posting=job_posting, duplicate=None)
