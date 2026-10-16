import ipaddress
import socket
from urllib.parse import urlsplit


class UnsafeUrlError(Exception):
    pass


def _is_blocked_ip(ip_str: str) -> bool:
    ip = ipaddress.ip_address(ip_str)
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def assert_public_http_url(url: str) -> str:
    """Reject anything that isn't a plain http(s) URL pointing at a public,
    externally-routable host. Raises UnsafeUrlError; never silently rewrites the
    URL. Call this again on every redirect hop, not just the original URL.
    """
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise UnsafeUrlError(f"scheme not allowed: {parts.scheme!r}")
    if not parts.hostname:
        raise UnsafeUrlError("URL has no hostname")

    hostname = parts.hostname
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise UnsafeUrlError("localhost is not allowed")

    try:
        addr_infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise UnsafeUrlError(f"could not resolve host: {hostname!r}") from exc

    for family, _type, _proto, _canonname, sockaddr in addr_infos:
        ip_str = sockaddr[0]
        if _is_blocked_ip(ip_str):
            raise UnsafeUrlError(f"host {hostname!r} resolves to a blocked address: {ip_str}")

    return url
