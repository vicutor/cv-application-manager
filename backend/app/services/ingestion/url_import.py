import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.job_posting import JobPosting, JobSource
from app.schemas.job import JobImportUrlConfirmRequest
from app.services.deduplication.fingerprint import content_hash, dedupe_fingerprint
from app.services.deduplication.service import DuplicateMatch, find_duplicate
from app.services.extraction.candidate import ExtractedJobCandidate
from app.services.extraction.html_to_text import html_to_text
from app.services.extraction.jsonld import find_jobposting_jsonld, map_jsonld_to_candidate
from app.services.extraction.text_cleaning import clean_text
from app.services.ingestion.http_fetcher import FetchError, fetch_url
from app.services.ingestion.staging import pop_staged_html, stage_html
from app.services.ingestion.ssrf import UnsafeUrlError, assert_public_http_url
from app.services.ingestion.url_normalize import normalize_url

_KNOWN_BOARD_NAMES = {
    "justjoin.it": "justjoinit",
    "www.justjoin.it": "justjoinit",
    "nofluffjobs.com": "nofluffjobs",
    "www.nofluffjobs.com": "nofluffjobs",
    "rocketjobs.pl": "rocketjobs",
    "www.rocketjobs.pl": "rocketjobs",
    "pracuj.pl": "pracuj",
    "www.pracuj.pl": "pracuj",
    "linkedin.com": "linkedin",
    "www.linkedin.com": "linkedin",
}


def source_name_for_host(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    return _KNOWN_BOARD_NAMES.get(host, host or "generic")


@dataclass
class UrlImportPreview:
    candidate: ExtractedJobCandidate
    canonical_url: str
    source_name: str
    staging_token: str
    duplicate: DuplicateMatch | None


class UrlImportError(Exception):
    """Fetch/SSRF-validation failure -- surfaced to the caller as `fetch_failed`."""


def preview_url_import(db: Session, settings: Settings, raw_url: str) -> UrlImportPreview:
    canonical_url = normalize_url(raw_url)

    try:
        assert_public_http_url(canonical_url)
    except UnsafeUrlError as exc:
        raise UrlImportError(str(exc)) from exc

    try:
        fetched = fetch_url(canonical_url, settings)
    except FetchError as exc:
        raise UrlImportError(str(exc)) from exc

    return _build_preview(db, settings, fetched.html, fetched.final_url)


def preview_html_import(db: Session, settings: Settings, raw_html: str, source_url: str) -> UrlImportPreview:
    """For boards that block a server-side fetch (e.g. pracuj.pl's Cloudflare
    managed challenge): the user visits the page in their own browser -- which
    passes the challenge legitimately, the way it's meant to be passed -- and
    pastes that page's HTML here. We parse it locally with the exact same
    JSON-LD extraction as the URL-import path; no network fetch happens at
    all, so there's nothing to bypass.
    """
    canonical_url = normalize_url(source_url)

    try:
        assert_public_http_url(canonical_url)
    except UnsafeUrlError as exc:
        raise UrlImportError(str(exc)) from exc

    return _build_preview(db, settings, raw_html, canonical_url)


def _build_preview(db: Session, settings: Settings, html: str, canonical_url: str) -> UrlImportPreview:
    jsonld = find_jobposting_jsonld(html)
    if jsonld is not None:
        candidate = map_jsonld_to_candidate(jsonld, canonical_url)
    else:
        # No structured data on this board: fall back to the same manual-entry
        # path as paste-text import -- the user fills company/title themselves,
        # working from the (cleaned) page text we could pull out.
        candidate = ExtractedJobCandidate(
            description_raw_text=html,
            description_clean_text=clean_text(_best_effort_text(html)),
            extraction_method="manual",
        )

    staging_token = stage_html(settings, html)

    canonical_url_match = db.scalars(
        select(JobPosting).where(JobPosting.canonical_url == canonical_url)
    ).first()
    if canonical_url_match is not None:
        duplicate = DuplicateMatch(job_posting=canonical_url_match, match_level="exact")
    else:
        duplicate = None
        if candidate.description_clean_text:
            c_hash = content_hash(candidate.description_clean_text)
            fingerprint = dedupe_fingerprint(
                candidate.company_name, candidate.position_title, candidate.location_text
            )
            duplicate = find_duplicate(db, c_hash, fingerprint)

    return UrlImportPreview(
        candidate=candidate,
        canonical_url=canonical_url,
        source_name=source_name_for_host(canonical_url),
        staging_token=staging_token,
        duplicate=duplicate,
    )


def _best_effort_text(page_html: str) -> str:
    body_only = re.sub(r"(?is)<(script|style|nav|footer|header)[^>]*>.*?</\1>", " ", page_html)
    return html_to_text(body_only)


def confirm_url_import(
    db: Session, settings: Settings, payload: JobImportUrlConfirmRequest
) -> tuple[JobPosting | None, DuplicateMatch | None]:
    cleaned = clean_text(payload.description_clean_text or payload.description_raw_text)
    c_hash = content_hash(cleaned)
    fingerprint = dedupe_fingerprint(payload.company_name, payload.position_title, payload.location_text)

    canonical_url_match = db.scalars(
        select(JobPosting).where(JobPosting.canonical_url == payload.canonical_url)
    ).first()
    duplicate = (
        DuplicateMatch(job_posting=canonical_url_match, match_level="exact")
        if canonical_url_match is not None
        else find_duplicate(db, c_hash, fingerprint)
    )
    if duplicate is not None and not payload.allow_duplicate:
        return None, duplicate

    source_name = source_name_for_host(payload.canonical_url)

    job_posting = JobPosting(
        source_type="url",
        source_name=source_name,
        source_url=payload.canonical_url,
        canonical_url=payload.canonical_url,
        external_job_id=payload.external_job_id,
        company_name=payload.company_name,
        position_title=payload.position_title,
        location_text=payload.location_text,
        remote_mode=payload.remote_mode,
        employment_types=payload.employment_types,
        salary_min=payload.salary_min,
        salary_max=payload.salary_max,
        salary_currency=payload.salary_currency,
        salary_period=payload.salary_period,
        description_raw_text=payload.description_raw_text,
        description_clean_text=cleaned,
        technologies=payload.technologies,
        requirements=[],
        responsibilities=[],
        nice_to_have=[],
        benefits=[],
        published_at=payload.published_at,
        expires_at=payload.expires_at,
        content_hash=c_hash,
        dedupe_fingerprint=fingerprint,
        workflow_status="new",
    )
    db.add(job_posting)
    db.flush()

    raw_artifact_path = None
    staged_html = pop_staged_html(settings, payload.staging_token) if payload.staging_token else None
    if staged_html is not None:
        source_dir = settings.jobs_dir / job_posting.id / "source"
        source_dir.mkdir(parents=True, exist_ok=True)
        original_path = source_dir / "original.html"
        original_path.write_text(staged_html, encoding="utf-8")
        raw_artifact_path = str(original_path.relative_to(settings.data_dir))

    source = JobSource(
        job_posting_id=job_posting.id,
        source_name=source_name,
        original_url=payload.canonical_url,
        canonical_url=payload.canonical_url,
        external_job_id=payload.external_job_id,
        http_status=200,
        fetched_at=datetime.now(timezone.utc),
        raw_artifact_path=raw_artifact_path,
        fetch_method="http",
    )
    db.add(source)
    db.commit()
    db.refresh(job_posting)

    return job_posting, None


class SourceAlreadyAttachedError(Exception):
    pass


def attach_source_to_job(
    db: Session,
    settings: Settings,
    job: JobPosting,
    canonical_url: str,
    staging_token: str,
    source_name: str,
    external_job_id: str | None,
) -> JobSource:
    """A second listing of the same job on a different board shouldn't create an
    independent JobPosting -- it gets appended to job_sources instead, per spec
    section 11 ("druga publikacja tego samego ogłoszenia... powinna być dopisana
    do job_sources, a nie tworzyć oddzielną ofertę").
    """
    already_attached = db.scalars(
        select(JobSource).where(
            JobSource.job_posting_id == job.id, JobSource.canonical_url == canonical_url
        )
    ).first()
    if already_attached is not None:
        raise SourceAlreadyAttachedError(f"{canonical_url} is already attached to this job posting")

    raw_artifact_path = None
    staged_html = pop_staged_html(settings, staging_token) if staging_token else None
    if staged_html is not None:
        source_dir = settings.jobs_dir / job.id / "source"
        source_dir.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r"[^a-z0-9]+", "-", source_name.lower()).strip("-") or "source"
        original_path = source_dir / f"{safe_name}-{uuid.uuid4().hex[:8]}.html"
        original_path.write_text(staged_html, encoding="utf-8")
        raw_artifact_path = str(original_path.relative_to(settings.data_dir))

    source = JobSource(
        job_posting_id=job.id,
        source_name=source_name,
        original_url=canonical_url,
        canonical_url=canonical_url,
        external_job_id=external_job_id,
        http_status=200,
        fetched_at=datetime.now(timezone.utc),
        raw_artifact_path=raw_artifact_path,
        fetch_method="http",
    )
    db.add(source)
    job.last_seen_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(source)
    return source
