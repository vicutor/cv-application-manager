from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.job_posting import JobPosting


@dataclass
class DuplicateMatch:
    job_posting: JobPosting
    match_level: str  # "exact" | "likely"


def find_duplicate(db: Session, content_hash: str, dedupe_fingerprint: str) -> DuplicateMatch | None:
    exact = db.scalars(
        select(JobPosting).where(JobPosting.content_hash == content_hash)
    ).first()
    if exact is not None:
        return DuplicateMatch(job_posting=exact, match_level="exact")

    likely = db.scalars(
        select(JobPosting).where(JobPosting.dedupe_fingerprint == dedupe_fingerprint)
    ).first()
    if likely is not None:
        return DuplicateMatch(job_posting=likely, match_level="likely")

    return None
