from pathlib import Path

from app.core.config import Settings


def generation_dir(settings: Settings, job_id: str, version_number: int) -> Path:
    return settings.jobs_dir / job_id / "generations" / f"{version_number:04d}"


def cover_letter_dir(settings: Settings, job_id: str, version_number: int) -> Path:
    return settings.jobs_dir / job_id / "cover_letters" / f"{version_number:04d}"


def job_source_dir(settings: Settings, job_id: str) -> Path:
    return settings.jobs_dir / job_id / "source"


def write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.rename(path)


def relative_to_data(settings: Settings, path: Path) -> str:
    return str(path.relative_to(settings.data_dir))
