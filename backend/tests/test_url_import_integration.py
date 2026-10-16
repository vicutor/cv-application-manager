"""Integration tests for the URL-import flow, using saved fixture HTML instead of
a live network call (per spec section 20: tests must not fetch real job boards).
`fetch_url` is monkeypatched; SSRF validation still runs for real (a DNS lookup of
a real hostname, no page fetch), so the safety check itself stays exercised.
"""

from pathlib import Path

import pytest

from app.schemas.job import JobImportUrlConfirmRequest
from app.services.ingestion import url_import
from app.services.ingestion.http_fetcher import FetchResult

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURE_WITH_JSONLD = REPO_ROOT / "fixtures" / "html" / "justjoinit_devops_sample.html"
FIXTURE_WITHOUT_JSONLD = REPO_ROOT / "fixtures" / "html" / "generic_no_jsonld_sample.html"
FIXTURE_EMBEDDED_HTML_DESCRIPTION = REPO_ROOT / "fixtures" / "html" / "nofluffjobs_devsecops_sample.html"
FIXTURE_PRACUJ_NULL_DESCRIPTION = REPO_ROOT / "fixtures" / "html" / "pracuj_localization_pm_sample.html"

JOB_URL = "https://justjoin.it/job-offer/codetalent-devops-engineer-warszawa-devops"
GENERIC_URL = "https://example.com/careers/backend-engineer"


def _mock_fetch(fixture_path: Path):
    def _fetch(url: str, settings):
        return FetchResult(final_url=url, status_code=200, html=fixture_path.read_text(encoding="utf-8"))

    return _fetch


def test_preview_extracts_from_jsonld_fixture(monkeypatch, db_session, settings):
    monkeypatch.setattr(url_import, "fetch_url", _mock_fetch(FIXTURE_WITH_JSONLD))

    preview = url_import.preview_url_import(db_session, settings, JOB_URL)

    assert preview.candidate.extraction_method == "json_ld"
    assert preview.candidate.company_name == "CodeTalent"
    assert preview.candidate.position_title == "Devops Engineer"
    assert preview.source_name == "justjoinit"
    assert preview.staging_token != ""
    assert preview.duplicate is None


def test_preview_falls_back_to_manual_without_jsonld(monkeypatch, db_session, settings):
    monkeypatch.setattr(url_import, "fetch_url", _mock_fetch(FIXTURE_WITHOUT_JSONLD))

    preview = url_import.preview_url_import(db_session, settings, GENERIC_URL)

    assert preview.candidate.extraction_method == "manual"
    assert preview.candidate.company_name == ""
    assert "Backend Engineer" in preview.candidate.description_clean_text


def test_preview_html_import_never_calls_fetch_url(monkeypatch, db_session, settings):
    """pracuj.pl blocks a server-side fetch_url() call with a Cloudflare managed
    challenge, so this path must parse pasted HTML directly and never touch the
    network -- asserted here by making fetch_url raise if it's ever called.
    """

    def _fetch_should_not_be_called(url: str, settings):
        raise AssertionError("preview_html_import must not call fetch_url")

    monkeypatch.setattr(url_import, "fetch_url", _fetch_should_not_be_called)

    html = FIXTURE_PRACUJ_NULL_DESCRIPTION.read_text(encoding="utf-8")
    preview = url_import.preview_html_import(
        db_session,
        settings,
        html,
        "https://www.pracuj.pl/praca/localization-project-manager-warszawa,oferta,1005138702",
    )

    assert preview.candidate.extraction_method == "json_ld"
    assert preview.candidate.company_name == "Mindbox Sp. z o.o."
    assert preview.candidate.position_title == "Localization Project Manager"
    assert "None" not in preview.candidate.description_clean_text
    assert "Lead end-to-end localization project execution" in preview.candidate.description_clean_text
    assert preview.source_name == "pracuj"
    assert preview.staging_token != ""


def test_confirm_then_reimport_is_flagged_as_duplicate(monkeypatch, db_session, settings):
    monkeypatch.setattr(url_import, "fetch_url", _mock_fetch(FIXTURE_WITH_JSONLD))

    preview = url_import.preview_url_import(db_session, settings, JOB_URL)
    c = preview.candidate
    confirm_payload = JobImportUrlConfirmRequest(
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
        technologies=["Kubernetes", "Terraform"],
    )

    job_posting, duplicate = url_import.confirm_url_import(db_session, settings, confirm_payload)
    assert duplicate is None
    assert job_posting is not None
    assert job_posting.source_type == "url"
    assert job_posting.source_name == "justjoinit"
    assert job_posting.technologies == ["Kubernetes", "Terraform"]

    # The staged HTML must have been persisted as a source artifact and removed
    # from staging (not left around indefinitely).
    source = job_posting.sources[0]
    assert source.raw_artifact_path is not None
    assert (settings.data_dir / source.raw_artifact_path).exists()
    assert not (settings.data_dir / ".staging" / f"{preview.staging_token}.html").exists()

    # Re-preview must surface the exact duplicate without needing to save again.
    monkeypatch.setattr(url_import, "fetch_url", _mock_fetch(FIXTURE_WITH_JSONLD))
    second_preview = url_import.preview_url_import(db_session, settings, JOB_URL)
    assert second_preview.duplicate is not None
    assert second_preview.duplicate.job_posting.id == job_posting.id
    assert second_preview.duplicate.match_level == "exact"

    # Confirming again without allow_duplicate must be rejected, not silently save.
    job_posting_2, duplicate_2 = url_import.confirm_url_import(db_session, settings, confirm_payload)
    assert job_posting_2 is None
    assert duplicate_2 is not None


def test_attach_source_links_to_existing_posting_instead_of_duplicating(monkeypatch, db_session, settings):
    primary_url = "https://justjoin.it/job-offer/codetalent-devops-engineer-warszawa-devops-attach-test"
    monkeypatch.setattr(url_import, "fetch_url", _mock_fetch(FIXTURE_WITH_JSONLD))
    preview = url_import.preview_url_import(db_session, settings, primary_url)
    c = preview.candidate
    job_posting, _ = url_import.confirm_url_import(
        db_session,
        settings,
        JobImportUrlConfirmRequest(
            canonical_url=preview.canonical_url,
            staging_token=preview.staging_token,
            external_job_id=c.external_job_id,
            company_name=c.company_name,
            position_title=c.position_title,
            location_text=c.location_text,
            remote_mode=c.remote_mode,
            description_raw_text=c.description_raw_text,
            description_clean_text=c.description_clean_text,
            allow_duplicate=True,  # earlier tests already saved this fixture's content/fingerprint
        ),
    )
    assert job_posting is not None

    # Same job, found again via a different board -- attach rather than duplicate.
    monkeypatch.setattr(url_import, "fetch_url", _mock_fetch(FIXTURE_EMBEDDED_HTML_DESCRIPTION))
    second_preview = url_import.preview_url_import(db_session, settings, GENERIC_URL)

    source = url_import.attach_source_to_job(
        db_session,
        settings,
        job_posting,
        canonical_url=second_preview.canonical_url,
        staging_token=second_preview.staging_token,
        source_name="nofluffjobs",
        external_job_id=second_preview.candidate.external_job_id,
    )

    assert source.job_posting_id == job_posting.id
    assert source.source_name == "nofluffjobs"
    assert source.raw_artifact_path is not None
    assert (settings.data_dir / source.raw_artifact_path).exists()

    db_session.refresh(job_posting)
    assert len(job_posting.sources) == 2

    # Attaching the exact same URL again must not create a duplicate JobSource row.
    with pytest.raises(url_import.SourceAlreadyAttachedError):
        url_import.attach_source_to_job(
            db_session,
            settings,
            job_posting,
            canonical_url=second_preview.canonical_url,
            staging_token="",
            source_name="nofluffjobs",
            external_job_id=None,
        )
