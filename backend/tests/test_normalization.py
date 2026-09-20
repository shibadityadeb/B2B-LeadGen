import pytest

from app.services.normalization import (
    derive_company_name,
    extract_domain,
    is_excluded_domain,
    is_probable_document,
    normalize_url,
    root_url,
)


@pytest.mark.parametrize(
    "url",
    [
        "https://www.example.com/about",
        "http://example.com/products",
        "https://example.com/",
        "https://EXAMPLE.com",
        "example.com/contact",
        "https://www.example.com/about?utm_source=google&utm_medium=cpc",
        "https://www.example.com/about#team",
    ],
)
def test_all_variants_resolve_to_one_canonical_domain(url):
    assert extract_domain(url) == "example.com"


def test_normalize_url_drops_tracking_and_fragment():
    assert (
        normalize_url("https://WWW.Example.com/About/?utm_source=x&fbclid=y&page=2#team")
        == "https://www.example.com/About?page=2"
    )


def test_normalize_url_keeps_meaningful_query_params():
    assert normalize_url("https://example.com/p?id=7") == "https://example.com/p?id=7"


def test_normalize_url_is_idempotent():
    once = normalize_url("http://example.com/a/?utm_source=x")
    assert normalize_url(once) == once


@pytest.mark.parametrize("url", ["", "   ", "not a url", "ftp://example.com/file", "mailto:a@b.com", "https://localhost/x"])
def test_normalize_url_rejects_unusable_input(url):
    assert normalize_url(url) is None


def test_multi_part_suffix_is_handled():
    assert extract_domain("https://shop.example.co.uk/items") == "example.co.uk"


def test_subdomains_collapse_to_registrable_domain():
    assert extract_domain("https://stores.brand.example.com") == "example.com"


def test_root_url_preserves_host():
    assert root_url("https://stores.example.com/a/b") == "https://stores.example.com"


@pytest.mark.parametrize(
    "domain", ["linkedin.com", "justdial.com", "facebook.com", "indiamart.com", "amazon.in", None]
)
def test_directories_and_social_are_excluded(domain):
    assert is_excluded_domain(domain) is True


def test_ordinary_company_domain_is_not_excluded():
    assert is_excluded_domain("sanwerwalajewellers.com") is False


def test_documents_are_not_treated_as_pages():
    assert is_probable_document("https://example.com/brochure.pdf") is True
    assert is_probable_document("https://example.com/about") is False


@pytest.mark.parametrize(
    "title,expected",
    [
        ("Acme Jewellers | Home", "Acme Jewellers"),
        ("Acme Jewellers - Best Jewellery Shop in Indore", "Acme Jewellers"),
        ("Home", "Example"),
        (None, "Example"),
        ("", "Example"),
    ],
)
def test_derive_company_name_trims_noise_without_inventing(title, expected):
    assert derive_company_name(title, "example.com") == expected


def test_derive_company_name_falls_back_to_readable_domain():
    assert derive_company_name(None, "acme-jewellers.co.in") == "Acme Jewellers"


def test_exclusion_list_is_extendable_without_a_code_change(monkeypatch):
    """Operators can block a newly-encountered directory via configuration."""
    from app.core.config import settings

    assert is_excluded_domain("some-new-directory.example") is False
    monkeypatch.setattr(settings, "search_excluded_domains", "some-new-directory.example")
    assert is_excluded_domain("some-new-directory.example") is True
