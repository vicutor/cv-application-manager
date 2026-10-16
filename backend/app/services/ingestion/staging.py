import time
import uuid
from pathlib import Path

from app.core.config import Settings

STAGING_MAX_AGE_SECONDS = 3600


def _staging_dir(settings: Settings) -> Path:
    d = settings.data_dir / ".staging"
    d.mkdir(parents=True, exist_ok=True)
    return d


def stage_html(settings: Settings, html: str) -> str:
    """Cache fetched HTML between the preview and confirm steps of URL import, so
    confirm doesn't need to re-fetch the page (which could return different
    content) and the original page can still be persisted as a source artifact.
    No DB row -- this is deliberately just a short-lived file, cleaned up
    opportunistically on each preview call.
    """
    _cleanup_stale(settings)
    token = uuid.uuid4().hex
    path = _staging_dir(settings) / f"{token}.html"
    path.write_text(html, encoding="utf-8")
    return token


def pop_staged_html(settings: Settings, token: str) -> str | None:
    path = _staging_dir(settings) / f"{token}.html"
    if not path.exists():
        return None
    html = path.read_text(encoding="utf-8")
    path.unlink(missing_ok=True)
    return html


def _cleanup_stale(settings: Settings, max_age_seconds: int = STAGING_MAX_AGE_SECONDS) -> None:
    now = time.time()
    for path in _staging_dir(settings).glob("*.html"):
        if now - path.stat().st_mtime > max_age_seconds:
            path.unlink(missing_ok=True)
