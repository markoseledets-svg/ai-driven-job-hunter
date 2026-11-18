from job_hunter.sources.normalizer import (
    build_dedup_hash,
    canonicalize_url,
    sanitize_html,
)


def test_canonicalize_url_strips_tracking_params_and_normalizes_case() -> None:
    url = (
        "HTTPS://Jobs.DOU.UA/companies/acme/vacancies/12345/"
        "?utm_source=telegram&utm_medium=cpc&ref=home&id=99&fbclid=abc#apply"
    )
    assert canonicalize_url(url) == "https://jobs.dou.ua/companies/acme/vacancies/12345?id=99"


def test_canonicalize_url_preserves_root_slash() -> None:
    assert canonicalize_url("https://Example.COM/") == "https://example.com/"


def test_sanitize_html_removes_tags_and_scripts() -> None:
    raw = (
        "<p>We are hiring a <b>Python</b> engineer.</p>"
        "<script>alert('xss')</script>"
        "<style>.hidden{display:none}</style>"
        "<ul><li>FastAPI</li><li>PostgreSQL</li></ul>"
    )
    clean = sanitize_html(raw)
    assert clean == "We are hiring a\nPython\nengineer.\nFastAPI\nPostgreSQL"
    assert "alert" not in clean
    assert "<" not in clean


def test_sanitize_html_truncates_and_handles_empty() -> None:
    assert sanitize_html("") == ""
    assert sanitize_html("<p>" + ("a" * 100) + "</p>", max_length=20) == "a" * 20


def test_build_dedup_hash_is_deterministic() -> None:
    h1 = build_dedup_hash("  Python Backend Dev ", " Acme Corp ")
    h2 = build_dedup_hash("python backend dev", "acme corp")
    assert h1 == h2
    assert len(h1) == 64
