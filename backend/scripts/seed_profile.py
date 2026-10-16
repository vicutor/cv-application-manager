"""Import fixtures/candidate.example.yaml as the active candidate profile version.

Idempotent by default: if an active profile version already exists, this is a
no-op (so it's safe to run on every container start). Pass --force to import a
fresh version anyway (e.g. after editing the fixture).

Usage (from backend/, with the venv active):
    python scripts/seed_profile.py [--force]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.candidate_profile.service import (
    ProfileValidationError,
    get_active_profile_version,
    import_profile_version,
)


def main() -> None:
    force = "--force" in sys.argv[1:]

    settings = get_settings()
    fixture_path = Path("../fixtures/candidate.example.yaml")
    if not fixture_path.exists():
        raise SystemExit(f"fixture not found: {fixture_path}")

    db = SessionLocal()
    try:
        existing = get_active_profile_version(db)
        if existing is not None and not force:
            print(f"Active profile version {existing.version_number} already exists, skipping.")
            return

        version = import_profile_version(db, settings, fixture_path)
        print(f"Imported profile version {version.version_number} ({version.yaml_path})")
    except ProfileValidationError as exc:
        raise SystemExit(f"profile validation failed: {exc.errors}") from exc
    finally:
        db.close()


if __name__ == "__main__":
    main()
