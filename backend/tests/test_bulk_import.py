"""Tests for bulk-importing every posting on a job-board listing page, using
saved fixture HTML instead of a live network call (per spec section 20).
`fetch_url` is monkeypatched in both `bulk_import` (the listing page fetch)
and `url_import` (the per-posting fetch `preview_url_import` performs)."""

from pathlib import Path

from app.services.ingestion import bulk_import, url_import
from app.services.ingestion.http_fetcher import FetchResult

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURE_LISTING = REPO_ROOT / "fixtures" / "html" / "justjoinit_listing_sample.html"
FIXTURE_WITH_JSONLD = REPO_ROOT / "fixtures" / "html" / "justjoinit_bulk_sample.html"
FIXTURE_WITHOUT_JSONLD = REPO_ROOT / "fixtures" / "html" / "generic_no_jsonld_sample.html"

LISTING_URL = "https://justjoin.it/job-offers/remote/devops?published-date=1"
JOB_URL = "https://justjoin.it/job-offer/bulktestco-site-reliability-engineer-remote-devops"
GENERIC_URL = "https://example.com/careers/bulk-test-backend-engineer"

_PAGES = {
    JOB_URL: FIXTURE_WITH_JSONLD,
    GENERIC_URL: FIXTURE_WITHOUT_JSONLD,
}


def _mock_fetch_by_url(url: str, settings):
    return FetchResult(final_url=url, status_code=200, html=_PAGES[url].read_text(encoding="utf-8"))


def _mock_fetch_listing(url: str, settings):
    return FetchResult(final_url=url, status_code=200, html=FIXTURE_LISTING.read_text(encoding="utf-8"))


def test_bulk_import_discovers_and_imports_structured_postings(monkeypatch, db_session, settings):
    monkeypatch.setattr(bulk_import, "fetch_url", _mock_fetch_listing)
    monkeypatch.setattr(url_import, "fetch_url", _mock_fetch_by_url)

    report = bulk_import.bulk_import_from_listing(db_session, settings, LISTING_URL)

    assert report.discovered_urls == [JOB_URL, GENERIC_URL]
    assert len(report.items) == 2

    imported = next(i for i in report.items if i.url == JOB_URL)
    assert imported.status == "imported"
    assert imported.job_posting_id is not None
    assert imported.company_name == "BulkTestCo"

    skipped = next(i for i in report.items if i.url == GENERIC_URL)
    assert skipped.status == "skipped_no_structured_data"
    assert skipped.job_posting_id is None

    assert report.imported_count == 1
    assert report.duplicate_count == 0


def test_rerunning_bulk_import_never_creates_duplicates(monkeypatch, db_session, settings):
    monkeypatch.setattr(bulk_import, "fetch_url", _mock_fetch_listing)
    monkeypatch.setattr(url_import, "fetch_url", _mock_fetch_by_url)

    first = bulk_import.bulk_import_from_listing(db_session, settings, LISTING_URL)
    first_job_id = next(i for i in first.items if i.url == JOB_URL).job_posting_id

    second = bulk_import.bulk_import_from_listing(db_session, settings, LISTING_URL)

    duplicate_item = next(i for i in second.items if i.url == JOB_URL)
    assert duplicate_item.status == "duplicate"
    assert duplicate_item.job_posting_id == first_job_id
    assert second.imported_count == 0
    assert second.duplicate_count == 1
