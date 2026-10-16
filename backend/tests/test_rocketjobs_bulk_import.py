"""rocketjobs.pl runs the same underlying job-board platform as justjoin.it
(same schema.org CollectionPage/JobPosting JSON-LD shape), so bulk_import.py
needs zero board-specific code -- this test just locks that in with its own
fixtures and confirms source_name_for_host maps the host to a friendly name.
"""

from pathlib import Path

from app.services.ingestion import bulk_import, url_import
from app.services.ingestion.http_fetcher import FetchResult
from app.services.ingestion.url_import import source_name_for_host

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURE_LISTING = REPO_ROOT / "fixtures" / "html" / "rocketjobs_listing_sample.html"
FIXTURE_WITH_JSONLD = REPO_ROOT / "fixtures" / "html" / "rocketjobs_bulk_sample.html"
FIXTURE_WITHOUT_JSONLD = REPO_ROOT / "fixtures" / "html" / "generic_no_jsonld_sample.html"

LISTING_URL = "https://rocketjobs.pl/oferty-pracy/praca-zdalna?keyword=project+manager&data-publikacji=1"
JOB_URL = "https://rocketjobs.pl/oferta-pracy/bulktestco-project-manager-remote"
GENERIC_URL = "https://example.com/careers/bulk-test-pm-role"

_PAGES = {JOB_URL: FIXTURE_WITH_JSONLD, GENERIC_URL: FIXTURE_WITHOUT_JSONLD}


def _mock_fetch_by_url(url: str, settings):
    return FetchResult(final_url=url, status_code=200, html=_PAGES[url].read_text(encoding="utf-8"))


def _mock_fetch_listing(url: str, settings):
    return FetchResult(final_url=url, status_code=200, html=FIXTURE_LISTING.read_text(encoding="utf-8"))


def test_source_name_for_rocketjobs_host():
    assert source_name_for_host(JOB_URL) == "rocketjobs"


def test_bulk_import_from_rocketjobs_listing(monkeypatch, db_session, settings):
    monkeypatch.setattr(bulk_import, "fetch_url", _mock_fetch_listing)
    monkeypatch.setattr(url_import, "fetch_url", _mock_fetch_by_url)

    report = bulk_import.bulk_import_from_listing(db_session, settings, LISTING_URL)

    assert report.discovered_urls == [JOB_URL, GENERIC_URL]
    imported = next(i for i in report.items if i.url == JOB_URL)
    assert imported.status == "imported"
    assert imported.company_name == "BulkTestCo RJ"
