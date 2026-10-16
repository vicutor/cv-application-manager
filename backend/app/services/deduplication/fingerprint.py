import hashlib
import re

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def normalize_token(value: str) -> str:
    return _NON_ALNUM_RE.sub(" ", value.lower()).strip()


def content_hash(clean_text: str) -> str:
    return hashlib.sha256(clean_text.encode("utf-8")).hexdigest()


def dedupe_fingerprint(company_name: str, position_title: str, location_text: str | None) -> str:
    """Level-2 (likely duplicate) fingerprint: normalized company + title + location.
    Deliberately coarser than content_hash so the same posting re-pasted with minor
    text differences (e.g. copied from a different job board) still collides.
    """
    parts = [
        normalize_token(company_name),
        normalize_token(position_title),
        normalize_token(location_text or ""),
    ]
    joined = "|".join(parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()
