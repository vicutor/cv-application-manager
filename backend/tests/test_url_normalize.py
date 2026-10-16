from app.services.ingestion.url_normalize import normalize_url


def test_normalize_lowercases_scheme_and_host():
    assert normalize_url("HTTP://Example.COM/Path") == "http://example.com/Path"


def test_normalize_strips_default_port():
    assert normalize_url("http://example.com:80/x") == "http://example.com/x"
    assert normalize_url("https://example.com:443/x") == "https://example.com/x"
    assert normalize_url("https://example.com:8443/x") == "https://example.com:8443/x"


def test_normalize_strips_tracking_params_and_sorts_the_rest():
    result = normalize_url("https://example.com/x?b=2&utm_source=newsletter&a=1&fbclid=abc")
    assert result == "https://example.com/x?a=1&b=2"


def test_normalize_strips_fragment_and_trailing_slash():
    assert normalize_url("https://example.com/jobs/123/#apply") == "https://example.com/jobs/123"
    assert normalize_url("https://example.com/") == "https://example.com/"


def test_normalize_preserves_ipv6_brackets():
    assert normalize_url("http://[::1]:8080/x?utm_source=foo") == "http://[::1]:8080/x"
