"""Bulk import: discover every posting URL on a job-board listing page (e.g.
justjoin.it's `/job-offers/remote/devops?published-date=1`) and import each one
through the exact same fetch/extract/dedupe pipeline as a single manual URL
import -- no separate scraping logic, no separate duplicate-detection rules.

Runs unattended (no per-item human review), so anything that can't be
auto-filled from structured JobPosting data on the page is skipped rather than
silently saved with blank fields -- the user can still import it manually via
the single-URL flow if they want it despite the missing structured data.
"""

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.schemas.job import JobImportUrlConfirmRequest
from app.services.extraction.jsonld import find_collection_urls_jsonld
from app.services.ingestion.http_fetcher import FetchError, fetch_url
from app.services.ingestion.ssrf import UnsafeUrlError, assert_public_http_url
from app.services.ingestion.url_import import UrlImportError, confirm_url_import, preview_url_import
from app.services.ingestion.url_normalize import normalize_url


@dataclass
class BulkImportItem:
    url: str
    status: str  # "imported" | "duplicate" | "skipped_no_structured_data" | "failed"
    job_posting_id: str | None = None
    company_name: str | None = None
    position_title: str | None = None
    reason: str | None = None


@dataclass
class BulkImportReport:
    listing_url: str
    discovered_urls: list[str] = field(default_factory=list)
    items: list[BulkImportItem] = field(default_factory=list)

    @property
    def imported_count(self) -> int:
        return sum(1 for i in self.items if i.status == "imported")

    @property
    def duplicate_count(self) -> int:
        return sum(1 for i in self.items if i.status == "duplicate")


class BulkImportError(Exception):
    """Fetching/parsing the listing page itself failed -- distinct from a
    single item within it failing, which is recorded per-item instead."""


def _import_one(db: Session, settings: Settings, url: str) -> BulkImportItem:
    try:
        preview = preview_url_import(db, settings, url)
    except UrlImportError as exc:
        return BulkImportItem(url=url, status="failed", reason=str(exc))

    if preview.duplicate is not None:
        d = preview.duplicate
        return BulkImportItem(
            url=url,
            status="duplicate",
            job_posting_id=d.job_posting.id,
            company_name=d.job_posting.company_name,
            position_title=d.job_posting.position_title,
        )

    c = preview.candidate
    if c.extraction_method != "json_ld" or not c.company_name or not c.position_title:
        # No one is reviewing this posting before it gets saved -- an
        # unstructured page would otherwise save with a blank company/title,
        # which is worse than just leaving it for manual single-URL import.
        return BulkImportItem(url=url, status="skipped_no_structured_data")

    payload = JobImportUrlConfirmRequest(
        canonical_url=preview.canonical_url,
        staging_token=preview.staging_token,
        external_job_id=c.external_job_id,
        company_name=c.company_name,
        position_title=c.position_title,
        location_text=c.location_text,
        remote_mode=c.remote_mode,
        employment_types=c.employment_types,
        salary_min=c.salary_min,
        salary_max=c.salary_max,
        salary_currency=c.salary_currency,
        salary_period=c.salary_period,
        description_raw_text=c.description_raw_text,
        description_clean_text=c.description_clean_text,
        published_at=c.published_at,
        expires_at=c.expires_at,
        technologies=c.technologies,
        allow_duplicate=False,
    )
    job_posting, duplicate = confirm_url_import(db, settings, payload)
    if job_posting is None:
        # Became a duplicate between the preview and confirm checks above
        # (e.g. the same job appeared twice in this listing).
        assert duplicate is not None
        return BulkImportItem(
            url=url,
            status="duplicate",
            job_posting_id=duplicate.job_posting.id,
            company_name=duplicate.job_posting.company_name,
            position_title=duplicate.job_posting.position_title,
        )
    return BulkImportItem(
        url=url,
        status="imported",
        job_posting_id=job_posting.id,
        company_name=job_posting.company_name,
        position_title=job_posting.position_title,
    )


def bulk_import_from_listing(db: Session, settings: Settings, listing_url: str) -> BulkImportReport:
    canonical_listing_url = normalize_url(listing_url)
    try:
        assert_public_http_url(canonical_listing_url)
    except UnsafeUrlError as exc:
        raise BulkImportError(str(exc)) from exc

    try:
        fetched = fetch_url(canonical_listing_url, settings)
    except FetchError as exc:
        raise BulkImportError(str(exc)) from exc

    urls = find_collection_urls_jsonld(fetched.html)
    if not urls:
        raise BulkImportError(
            "no listing data found on this page (expected a schema.org CollectionPage) -- "
            "is this a search/listing URL, not a single job posting?"
        )

    items = [_import_one(db, settings, url) for url in urls]
    return BulkImportReport(listing_url=fetched.final_url, discovered_urls=urls, items=items)
