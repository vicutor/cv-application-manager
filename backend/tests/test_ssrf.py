import pytest

from app.services.ingestion.ssrf import UnsafeUrlError, assert_public_http_url


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://localhost/",
        "http://localhost:8000/api/health",
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata endpoint
        "http://[::1]/",
        "http://10.0.0.5/",
        "http://192.168.1.1/",
        "ftp://example.com/x",
        "file:///etc/passwd",
    ],
)
def test_unsafe_urls_are_rejected(url):
    with pytest.raises(UnsafeUrlError):
        assert_public_http_url(url)


def test_public_https_url_is_allowed():
    # example.com resolves to a public IP; this must not raise.
    assert_public_http_url("https://example.com/jobs/123")
