from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.cover_letter import CoverLetter
from app.models.cv_generation import CvGeneration
from app.schemas.cv_generation import CvGenerationCreateRequest, CvGenerationRead
from app.schemas.job import (
    AttachSourceRequest,
    BulkImportItemResponse,
    BulkImportReportResponse,
    DuplicateInfo,
    JobImportHtmlRequest,
    JobImportListingRequest,
    JobImportTextRequest,
    JobImportUrlConfirmRequest,
    JobImportUrlPreviewResponse,
    JobImportUrlRequest,
    JobPatchRequest,
    JobPostingDetail,
    JobPostingListItem,
    JobSourceRead,
)
from app.schemas.application import ApplicationRead, MarkAppliedRequest
from app.schemas.cover_letter import CoverLetterRead
from app.services.applications.service import (
    CvGenerationNotFoundError,
    CvGenerationNotSucceededError,
    mark_applied,
)
from app.services.cover_letter.cost import attach_cost_totals as attach_cover_letter_cost_totals
from app.services.cover_letter.generation import NoActiveProfileError as CoverLetterNoActiveProfileError
from app.services.cover_letter.generation import generate_cover_letter
from app.services.cv_generation.cost import attach_cost_totals
from app.services.cv_generation.pipeline import NoActiveProfileError, create_queued_generation, run_generation
from app.services.ingestion.bulk_import import BulkImportError, bulk_import_from_listing
from app.services.ingestion.text_import import import_from_text
from app.services.ingestion.url_import import (
    SourceAlreadyAttachedError,
    UrlImportError,
    attach_source_to_job,
    confirm_url_import,
    preview_html_import,
    preview_url_import,
)
from app.services.jobs.service import archive_job, delete_job, get_job, list_jobs, patch_job

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/import-text", status_code=status.HTTP_201_CREATED, response_model=JobPostingDetail)
def import_job_from_text(payload: JobImportTextRequest, db: Session = Depends(get_db)):
    outcome = import_from_text(db, payload)
    if outcome.job_posting is None:
        duplicate = outcome.duplicate
        assert duplicate is not None
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=DuplicateInfo(
                job_posting_id=duplicate.job_posting.id,
                match_level=duplicate.match_level,
                company_name=duplicate.job_posting.company_name,
                position_title=duplicate.job_posting.position_title,
            ).model_dump(),
        )
    return outcome.job_posting


def _preview_response(preview) -> JobImportUrlPreviewResponse:
    duplicate_info = None
    if preview.duplicate is not None:
        duplicate_info = DuplicateInfo(
            job_posting_id=preview.duplicate.job_posting.id,
            match_level=preview.duplicate.match_level,
            company_name=preview.duplicate.job_posting.company_name,
            position_title=preview.duplicate.job_posting.position_title,
        )

    c = preview.candidate
    return JobImportUrlPreviewResponse(
        extraction_method=c.extraction_method,
        canonical_url=preview.canonical_url,
        source_name=preview.source_name,
        staging_token=preview.staging_token,
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
        external_job_id=c.external_job_id,
        technologies=c.technologies,
        duplicate=duplicate_info,
    )


@router.post("/import-url", response_model=JobImportUrlPreviewResponse)
def preview_job_from_url(
    payload: JobImportUrlRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Fetches the URL and extracts what it can (JSON-LD JobPosting when present),
    but does NOT save anything -- this is the "show a preview the user can correct"
    step from the spec's URL-import flow. Saving happens via /import-url/confirm.
    """
    try:
        preview = preview_url_import(db, settings, payload.url)
    except UrlImportError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"fetch_failed: {exc}") from exc

    return _preview_response(preview)


@router.post("/import-html", response_model=JobImportUrlPreviewResponse)
def preview_job_from_html(
    payload: JobImportHtmlRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Same preview as /import-url, but for pages a server-side fetch can't
    reach (e.g. pracuj.pl's Cloudflare managed challenge): the user pastes the
    HTML from their own browser -- which already passed the challenge
    legitimately -- instead of giving us a URL to fetch ourselves. Confirming
    goes through the same /import-url/confirm endpoint.
    """
    try:
        preview = preview_html_import(db, settings, payload.html, payload.source_url)
    except UrlImportError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"invalid_source_url: {exc}") from exc

    return _preview_response(preview)


@router.post("/import-url/confirm", status_code=status.HTTP_201_CREATED, response_model=JobPostingDetail)
def confirm_job_from_url(
    payload: JobImportUrlConfirmRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    job_posting, duplicate = confirm_url_import(db, settings, payload)
    if job_posting is None:
        assert duplicate is not None
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=DuplicateInfo(
                job_posting_id=duplicate.job_posting.id,
                match_level=duplicate.match_level,
                company_name=duplicate.job_posting.company_name,
                position_title=duplicate.job_posting.position_title,
            ).model_dump(),
        )
    return job_posting


@router.post("/import-listing", response_model=BulkImportReportResponse)
def import_jobs_from_listing(
    payload: JobImportListingRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Bulk-imports every posting found on a job-board search/listing page
    (e.g. a justjoin.it `/job-offers/...?published-date=1` URL). Each posting
    goes through the same fetch/extract/dedupe path as a single manual URL
    import, so re-running this on an overlapping listing never creates
    duplicates -- already-imported postings are just reported, not re-saved.
    """
    try:
        report = bulk_import_from_listing(db, settings, payload.listing_url)
    except BulkImportError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"listing_fetch_failed: {exc}") from exc

    return BulkImportReportResponse(
        listing_url=report.listing_url,
        discovered_count=len(report.discovered_urls),
        imported_count=report.imported_count,
        duplicate_count=report.duplicate_count,
        items=[
            BulkImportItemResponse(
                url=i.url,
                status=i.status,
                job_posting_id=i.job_posting_id,
                company_name=i.company_name,
                position_title=i.position_title,
                reason=i.reason,
            )
            for i in report.items
        ],
    )


@router.post("/{job_id}/sources", status_code=status.HTTP_201_CREATED, response_model=JobSourceRead)
def attach_source(
    job_id: str,
    payload: AttachSourceRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Links a URL-import preview to an EXISTING posting instead of creating a new
    one -- for when the same job turns up on a second board. See spec section 11.
    """
    job = get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    try:
        return attach_source_to_job(
            db,
            settings,
            job,
            canonical_url=payload.canonical_url,
            staging_token=payload.staging_token,
            source_name=payload.source_name,
            external_job_id=payload.external_job_id,
        )
    except SourceAlreadyAttachedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("", response_model=list[JobPostingListItem])
def get_jobs(status_filter: Optional[str] = None, db: Session = Depends(get_db)):
    return list_jobs(db, status=status_filter)


@router.get("/{job_id}", response_model=JobPostingDetail)
def get_job_detail(job_id: str, db: Session = Depends(get_db)):
    job = get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    return job


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job_endpoint(
    job_id: str, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
):
    job = get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    delete_job(db, settings, job)


@router.patch("/{job_id}", response_model=JobPostingDetail)
def patch_job_detail(job_id: str, payload: JobPatchRequest, db: Session = Depends(get_db)):
    job = get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    return patch_job(db, job, payload)


@router.post("/{job_id}/archive", response_model=JobPostingDetail)
def archive_job_endpoint(job_id: str, db: Session = Depends(get_db)):
    job = get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    return archive_job(db, job)


@router.post(
    "/{job_id}/cv-generations", status_code=status.HTTP_202_ACCEPTED, response_model=CvGenerationRead
)
def create_cv_generation(
    job_id: str,
    payload: CvGenerationCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    job = get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    try:
        generation = create_queued_generation(
            db, settings, job, language=payload.language, target_pages=payload.target_pages
        )
    except NoActiveProfileError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    background_tasks.add_task(run_generation, generation.id, settings)
    return generation


@router.get("/{job_id}/cv-generations", response_model=list[CvGenerationRead])
def list_cv_generations(job_id: str, db: Session = Depends(get_db)):
    generations = list(
        db.scalars(
            select(CvGeneration)
            .where(CvGeneration.job_posting_id == job_id)
            .order_by(CvGeneration.version_number.desc())
        ).all()
    )
    return attach_cost_totals(db, generations)


@router.post("/{job_id}/cover-letters", status_code=status.HTTP_201_CREATED, response_model=CoverLetterRead)
def create_cover_letter(job_id: str, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    """Runs synchronously (two short LLM calls, no LaTeX compile) so the
    response already carries the finished letter -- see
    cover_letter.generation for why this doesn't need the queued/background
    pattern cv-generations uses."""
    job = get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    try:
        cover_letter = generate_cover_letter(db, settings, job)
    except CoverLetterNoActiveProfileError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return attach_cover_letter_cost_totals(db, [cover_letter])[0]


@router.get("/{job_id}/cover-letters", response_model=list[CoverLetterRead])
def list_cover_letters(job_id: str, db: Session = Depends(get_db)):
    letters = list(
        db.scalars(
            select(CoverLetter)
            .where(CoverLetter.job_posting_id == job_id)
            .order_by(CoverLetter.version_number.desc())
        ).all()
    )
    return attach_cover_letter_cost_totals(db, letters)


@router.post("/{job_id}/applications", status_code=status.HTTP_201_CREATED, response_model=ApplicationRead)
def create_application(job_id: str, payload: MarkAppliedRequest, db: Session = Depends(get_db)):
    job = get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    try:
        return mark_applied(db, job, payload)
    except CvGenerationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except CvGenerationNotSucceededError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
