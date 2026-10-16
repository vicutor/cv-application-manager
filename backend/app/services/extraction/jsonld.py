import json
import re
from datetime import date
from typing import Any, Optional
from urllib.parse import urlsplit

from app.services.extraction.candidate import ExtractedJobCandidate
from app.services.extraction.html_to_text import html_to_text
from app.services.extraction.text_cleaning import clean_text

_SCRIPT_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.DOTALL | re.IGNORECASE
)


def _iter_jsonld_objects(html: str):
    for match in _SCRIPT_RE.finditer(html):
        raw = match.group(1).strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        candidates = data if isinstance(data, list) else [data]
        for item in candidates:
            if isinstance(item, dict) and "@graph" in item and isinstance(item["@graph"], list):
                yield from item["@graph"]
            else:
                yield item


def find_jobposting_jsonld(html: str) -> Optional[dict[str, Any]]:
    for obj in _iter_jsonld_objects(html):
        if not isinstance(obj, dict):
            continue
        obj_type = obj.get("@type")
        types = obj_type if isinstance(obj_type, list) else [obj_type]
        if any(isinstance(t, str) and t.lower() == "jobposting" for t in types):
            return obj
    return None


def find_collection_urls_jsonld(html: str) -> list[str]:
    """A job-board search/listing page (e.g. justjoin.it's `/job-offers/...`
    filtered views) commonly embeds a schema.org CollectionPage whose `hasPart`
    lists every individual posting shown, each with its canonical url -- this
    is what a bulk-import feature reads to discover posting URLs, without
    needing to reverse-engineer the board's private API."""
    urls: list[str] = []
    for obj in _iter_jsonld_objects(html):
        if not isinstance(obj, dict):
            continue
        obj_type = obj.get("@type")
        types = obj_type if isinstance(obj_type, list) else [obj_type]
        if not any(isinstance(t, str) and t.lower() == "collectionpage" for t in types):
            continue
        for part in obj.get("hasPart") or []:
            if isinstance(part, dict) and isinstance(part.get("url"), str) and part["url"]:
                urls.append(part["url"])
    return urls


def _parse_iso_date(value: Any) -> Optional[date]:
    if not isinstance(value, str) or not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _location_text(job_location: Any) -> Optional[str]:
    if not isinstance(job_location, dict):
        return None
    address = job_location.get("address")
    if not isinstance(address, dict):
        return None
    parts = [address.get("addressLocality"), address.get("addressRegion"), address.get("addressCountry")]
    parts = [p for p in parts if p]
    return ", ".join(parts) if parts else None


def _remote_mode(data: dict[str, Any]) -> str:
    job_location_type = data.get("jobLocationType")
    types = job_location_type if isinstance(job_location_type, list) else [job_location_type]
    if any(isinstance(t, str) and t.upper() == "TELECOMMUTE" for t in types):
        return "remote"
    if data.get("jobLocation"):
        return "onsite"
    return "unknown"


def _employment_types(data: dict[str, Any]) -> list[str]:
    value = data.get("employmentType")
    if not value:
        return []
    return value if isinstance(value, list) else [value]


def _salary(data: dict[str, Any]) -> tuple[Optional[float], Optional[float], Optional[str], Optional[str]]:
    base = data.get("baseSalary")
    if not isinstance(base, dict):
        return None, None, None, None
    currency = base.get("currency")
    value = base.get("value")
    if not isinstance(value, dict):
        return None, None, currency, None
    unit = value.get("unitText")
    period = {"HOUR": "hourly", "DAY": "daily", "WEEK": "weekly", "MONTH": "monthly", "YEAR": "yearly"}.get(
        (unit or "").upper()
    )
    min_v = value.get("minValue", value.get("value"))
    max_v = value.get("maxValue", value.get("value"))
    return (
        float(min_v) if min_v is not None else None,
        float(max_v) if max_v is not None else None,
        currency,
        period,
    )


def _external_job_id(data: dict[str, Any], page_url: str) -> Optional[str]:
    identifier = data.get("identifier")
    if isinstance(identifier, dict) and identifier.get("value"):
        return str(identifier["value"])
    slug = urlsplit(page_url).path.rstrip("/").rsplit("/", 1)[-1]
    return slug or None


def _company_name(data: dict[str, Any]) -> str:
    hiring_org = data.get("hiringOrganization")
    if isinstance(hiring_org, dict):
        return str(hiring_org.get("name") or "")
    # schema.org also allows hiringOrganization to be a plain string (the org
    # name) rather than an Organization object -- pracuj.pl does this.
    if isinstance(hiring_org, str):
        return hiring_org
    return ""


def _description_text(data: dict[str, Any]) -> str:
    description = data.get("description")
    if isinstance(description, str) and description.strip():
        return description
    # Some boards (e.g. pracuj.pl) leave `description` null and instead split
    # the posting's actual content across their own non-standard fields --
    # fall back to stitching those together rather than losing the content.
    parts = [data.get("responsibilities"), data.get("experienceRequirements"), data.get("jobBenefits")]
    return "\n\n".join(str(p) for p in parts if isinstance(p, str) and p.strip())


def map_jsonld_to_candidate(data: dict[str, Any], page_url: str) -> ExtractedJobCandidate:
    raw_description = html_to_text(_description_text(data))
    salary_min, salary_max, salary_currency, salary_period = _salary(data)

    company_name = _company_name(data)

    return ExtractedJobCandidate(
        company_name=company_name,
        position_title=str(data.get("title", "")),
        location_text=_location_text(data.get("jobLocation")),
        remote_mode=_remote_mode(data),
        employment_types=_employment_types(data),
        salary_min=salary_min,
        salary_max=salary_max,
        salary_currency=salary_currency,
        salary_period=salary_period,
        description_raw_text=raw_description,
        description_clean_text=clean_text(raw_description),
        published_at=_parse_iso_date(data.get("datePosted")),
        expires_at=_parse_iso_date(data.get("validThrough")),
        external_job_id=_external_job_id(data, page_url),
        technologies=[],
        extraction_method="json_ld",
    )
