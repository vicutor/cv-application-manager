from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.usage import UsageSummary
from app.services.cv_generation.usage import compute_usage_summary

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("/summary", response_model=UsageSummary)
def get_usage_summary(db: Session = Depends(get_db)):
    return compute_usage_summary(db)
