import shutil
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.candidate_profile import CandidateProfileVersion
from app.services.candidate_profile.validation import content_hash, load_and_validate_yaml


class ProfileValidationError(Exception):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


def import_profile_version(
    db: Session, settings: Settings, source_yaml_path: Path
) -> CandidateProfileVersion:
    """Validate a candidate profile YAML file, store it as the next version under
    data/profile/versions/, and mark it the active version. Raises
    ProfileValidationError if the YAML fails schema or cross-reference validation.
    """
    result = load_and_validate_yaml(source_yaml_path)
    if not result.is_valid:
        raise ProfileValidationError(result.errors)

    versions_dir = settings.profile_dir / "versions"
    versions_dir.mkdir(parents=True, exist_ok=True)

    existing = db.scalars(
        select(CandidateProfileVersion).order_by(CandidateProfileVersion.version_number.desc())
    ).first()
    next_version = (existing.version_number + 1) if existing else 1

    dest_filename = f"{next_version:04d}.yaml"
    dest_path = versions_dir / dest_filename
    tmp_path = dest_path.with_suffix(".yaml.tmp")
    shutil.copyfile(source_yaml_path, tmp_path)
    tmp_path.rename(dest_path)

    raw = source_yaml_path.read_text(encoding="utf-8")

    db.query(CandidateProfileVersion).update({CandidateProfileVersion.is_active: False})

    version = CandidateProfileVersion(
        version_number=next_version,
        yaml_path=str(dest_path.relative_to(settings.data_dir)),
        content_hash=content_hash(raw),
        is_active=True,
        validation_status="valid",
        validation_errors=[],
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return version


def get_active_profile_version(db: Session) -> CandidateProfileVersion | None:
    return db.scalars(
        select(CandidateProfileVersion).where(CandidateProfileVersion.is_active.is_(True))
    ).first()
