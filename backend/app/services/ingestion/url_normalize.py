from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TRACKING_PARAM_PREFIXES = ("utm_",)
_TRACKING_PARAMS = {"fbclid", "gclid", "gh_src", "ref", "referrer", "source"}


def normalize_url(url: str) -> str:
    """Canonical form used for exact-duplicate detection: lowercase scheme/host,
    default ports stripped, tracking query params removed, fragment dropped,
    trailing slash on the path normalized away.
    """
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    host = parts.hostname.lower() if parts.hostname else ""
    if ":" in host:  # IPv6 literal -- urlsplit strips the brackets, so restore them
        host = f"[{host}]"
    port = parts.port
    default_port = {"http": 80, "https": 443}.get(scheme)
    netloc = host if port is None or port == default_port else f"{host}:{port}"

    kept_params = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in _TRACKING_PARAMS and not k.lower().startswith(_TRACKING_PARAM_PREFIXES)
    ]
    kept_params.sort()
    query = urlencode(kept_params)

    path = parts.path.rstrip("/") or "/"

    return urlunsplit((scheme, netloc, path, query, ""))
