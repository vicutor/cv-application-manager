from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.application import Application
from app.schemas.application import ApplicationRead, ApplicationStatusUpdateRequest
from app.services.applications.service import list_applications, update_status

router = APIRouter(prefix="/applications", tags=["applications"])


@router.get("", response_model=list[ApplicationRead])
def get_applications(db: Session = Depends(get_db)):
    return list_applications(db)


@router.patch("/{application_id}", response_model=ApplicationRead)
def patch_application(
    application_id: str, payload: ApplicationStatusUpdateRequest, db: Session = Depends(get_db)
):
    application = db.get(Application, application_id)
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="application not found")
    try:
        return update_status(db, application, payload.status, payload.notes)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
