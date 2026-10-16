import os
import tempfile
from pathlib import Path

# Must happen before any `app.*` import: Settings/engine are constructed at import
# time, so the test data dir + sqlite file have to be in place first. This keeps
# tests fully isolated from the real ./data dev directory.
_TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="cvapp-test-data-"))
os.environ["DATA_DIR"] = str(_TEST_DATA_DIR)
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DATA_DIR / 'app.db'}"
# Force the mock (deterministic, no-LLM) pipeline regardless of what's in the
# developer's local .env -- the test suite must stay free and offline, and
# must never depend on a real API key being present or absent on this machine.
os.environ["ANTHROPIC_API_KEY"] = ""

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import app.models  # noqa: E402,F401  (registers all models on Base.metadata)
from app.core.config import get_settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402
from app.services.candidate_profile.service import import_profile_version  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURE_PROFILE_PATH = REPO_ROOT / "fixtures" / "candidate.example.yaml"


@pytest.fixture(scope="session", autouse=True)
def _init_schema():
    Base.metadata.create_all(engine)
    yield


@pytest.fixture(scope="session")
def settings():
    return get_settings()


@pytest.fixture()
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client():
    return TestClient(fastapi_app)


@pytest.fixture()
def active_profile_version(db_session, settings):
    return import_profile_version(db_session, settings, FIXTURE_PROFILE_PATH)
