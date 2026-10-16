from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.cover_letter import CoverLetter
from app.models.job_posting import JobPosting

router = APIRouter(prefix="/cover-letters", tags=["cover-letters"])


def _get_cover_letter_or_404(db: Session, cover_letter_id: str) -> CoverLetter:
    cover_letter = db.get(CoverLetter, cover_letter_id)
    if cover_letter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="cover letter not found")
    return cover_letter


def _friendly_filename(job: JobPosting, cover_letter: CoverLetter, ext: str) -> str:
    company = job.company_name.replace(" ", "_")
    position = job.position_title.replace(" ", "_")
    return f"CoverLetter_{company}_{position}_v{cover_letter.version_number}.{ext}"


@router.get("/{cover_letter_id}/pdf")
def download_pdf(cover_letter_id: str, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    cover_letter = _get_cover_letter_or_404(db, cover_letter_id)
    if not cover_letter.pdf_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="pdf not available")
    job = db.get(JobPosting, cover_letter.job_posting_id)
    filename = _friendly_filename(job, cover_letter, "pdf") if job else "cover_letter.pdf"
    return FileResponse(
        settings.data_dir / cover_letter.pdf_path, media_type="application/pdf", filename=filename
    )


@router.get("/{cover_letter_id}/tex")
def download_tex(cover_letter_id: str, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    cover_letter = _get_cover_letter_or_404(db, cover_letter_id)
    if not cover_letter.latex_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="tex source not available")
    job = db.get(JobPosting, cover_letter.job_posting_id)
    filename = _friendly_filename(job, cover_letter, "tex") if job else "cover_letter.tex"
    return FileResponse(
        settings.data_dir / cover_letter.latex_path, media_type="text/x-tex", filename=filename
    )
