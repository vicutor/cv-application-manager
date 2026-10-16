from dataclasses import dataclass

import httpx

from app.core.config import Settings
from app.services.ingestion.ssrf import assert_public_http_url

MAX_REDIRECTS = 5
MAX_RESPONSE_BYTES = 5 * 1024 * 1024  # 5 MB: a job posting page, not a video


class FetchError(Exception):
    pass


@dataclass
class FetchResult:
    final_url: str
    status_code: int
    html: str


def fetch_url(url: str, settings: Settings) -> FetchResult:
    """SSRF-safe fetch: every hop (including redirect targets) is re-validated
    against the public-host allowlist before being requested, and the response
    body is capped so a misbehaving/huge endpoint can't exhaust memory.
    """
    current_url = assert_public_http_url(url)
    headers = {"User-Agent": settings.http_user_agent}

    with httpx.Client(follow_redirects=False, timeout=settings.http_timeout_seconds) as client:
        for _hop in range(MAX_REDIRECTS + 1):
            try:
                with client.stream("GET", current_url, headers=headers) as response:
                    if response.is_redirect:
                        next_url = response.headers.get("location")
                        if not next_url:
                            raise FetchError("redirect response missing Location header")
                        current_url = assert_public_http_url(
                            str(httpx.URL(next_url, base=current_url))
                        )
                        continue

                    if response.status_code >= 400:
                        raise FetchError(f"HTTP {response.status_code} fetching {current_url}")

                    chunks: list[bytes] = []
                    total = 0
                    for chunk in response.iter_bytes():
                        total += len(chunk)
                        if total > MAX_RESPONSE_BYTES:
                            raise FetchError(f"response exceeded {MAX_RESPONSE_BYTES} byte limit")
                        chunks.append(chunk)

                    body = b"".join(chunks)
                    encoding = response.encoding or "utf-8"
                    html = body.decode(encoding, errors="replace")
                    return FetchResult(final_url=current_url, status_code=response.status_code, html=html)
            except httpx.TimeoutException as exc:
                raise FetchError(f"timed out fetching {current_url}") from exc
            except httpx.HTTPError as exc:
                raise FetchError(f"error fetching {current_url}: {exc}") from exc

    raise FetchError("too many redirects")
