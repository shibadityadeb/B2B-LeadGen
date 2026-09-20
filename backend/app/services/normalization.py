"""URL, domain and company-name normalization.

Pure functions, no I/O — this is the deduplication backbone of the discovery
pipeline and is covered directly by unit tests.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import tldextract

from app.core.config import settings

# Use the bundled public-suffix snapshot: no network call at import time.
_extract = tldextract.TLDExtract(suffix_list_urls=(), fallback_to_snapshot=True)

# Query parameters that never identify a distinct page.
_TRACKING_PARAM_PREFIXES = ("utm_", "ad_", "mc_", "pk_", "hsa_", "_hs")
_TRACKING_PARAMS = {
    "fbclid", "gclid", "gbraid", "wbraid", "msclkid", "dclid", "yclid",
    "igshid", "mkt_tok", "ref", "referrer", "source", "src", "campaign_id",
    "_ga", "_gl", "trk", "spm",
}

# Hosts that are never a company's own website. Deliberately generic:
# search engines, social networks, marketplaces, directories, doc/file hosts.
# This list is infrastructure, not industry logic.
EXCLUDED_DOMAINS: frozenset[str] = frozenset({
    # search / portals
    "google.com", "google.co.in", "bing.com", "duckduckgo.com", "yahoo.com",
    "baidu.com", "yandex.com", "ecosia.org", "startpage.com", "brave.com",
    # social
    "linkedin.com", "facebook.com", "instagram.com", "twitter.com", "x.com",
    "youtube.com", "pinterest.com", "reddit.com", "tiktok.com", "threads.net",
    "whatsapp.com", "telegram.org", "quora.com", "medium.com", "tumblr.com",
    "vimeo.com", "snapchat.com",
    # business directories / aggregators
    "justdial.com", "indiamart.com", "tradeindia.com", "exportersindia.com",
    "sulekha.com", "yelp.com", "yellowpages.com", "tripadvisor.com",
    "zaubacorp.com", "tofler.in", "thecompanycheck.com", "instafinancials.com",
    "crunchbase.com", "owler.com", "zoominfo.com", "apollo.io", "dnb.com",
    "glassdoor.com", "ambitionbox.com", "indeed.com", "naukri.com",
    "clutch.co", "goodfirms.co", "g2.com", "capterra.com", "trustpilot.com",
    "mapquest.com", "foursquare.com", "bbb.org", "jooble.org", "shine.com",
    "monsterindia.com", "timesjobs.com", "d7leadfinder.com", "bdir.in",
    "indianyellowpages.com", "yellowpages.in", "asklaila.com", "grotal.com",
    "citypedia.in", "connect2india.com", "99acres.com", "magicbricks.com",
    "bing.com", "tripoto.com", "zomato.com", "swiggy.com",
    # knowledge / news aggregators / file hosts
    "wikipedia.org", "wikimedia.org", "amazon.com", "amazon.in", "flipkart.com",
    "ebay.com", "alibaba.com", "etsy.com", "scribd.com", "slideshare.net",
    "issuu.com", "archive.org", "blogspot.com", "wordpress.com", "wixsite.com",
    "github.com", "gitlab.com", "docs.google.com", "drive.google.com",
    "apps.apple.com", "play.google.com",
})

# File extensions that are documents/assets rather than company pages.
_NON_PAGE_EXTENSIONS = (
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".zip", ".rar",
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".mp4", ".mp3", ".csv",
)

# Noise commonly appended to page titles.
_TITLE_SEPARATORS = ("|", "-", "–", "—", "::", "·", "»", ":")
_NAME_NOISE = re.compile(
    r"\b(home|homepage|official website|official site|welcome to|welcome|"
    r"best|top|near me|online|buy|shop now|contact us|about us|"
    r"products?|services?|price list)\b",
    re.IGNORECASE,
)
_WHITESPACE = re.compile(r"\s+")


def normalize_url(url: str) -> str | None:
    """Canonicalize a URL: lowercase scheme/host, drop fragments and tracking params.

    Returns None when the input is not a usable http(s) URL.
    """
    if not url or not isinstance(url, str):
        return None
    raw = url.strip()
    if not raw:
        return None
    if raw.startswith("//"):
        raw = "https:" + raw
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", raw):
        # A non-http scheme such as `mailto:` or `tel:` must be rejected, not
        # prefixed — prefixing would misread the address as a host.
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", raw):
            return None
        raw = "https://" + raw

    try:
        parts = urlsplit(raw)
    except ValueError:
        return None

    if parts.scheme not in ("http", "https"):
        return None
    host = (parts.hostname or "").lower().strip(".")
    if not host or "." not in host:
        return None

    netloc = host
    if parts.port and parts.port not in (80, 443):
        netloc = f"{host}:{parts.port}"

    path = parts.path or "/"
    if len(path) > 1:
        path = path.rstrip("/") or "/"

    kept = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=False)
        if not _is_tracking_param(key)
    ]
    query = urlencode(sorted(kept))

    return urlunsplit((parts.scheme, netloc, path, query, ""))


def _is_tracking_param(key: str) -> bool:
    lowered = key.lower()
    return lowered in _TRACKING_PARAMS or lowered.startswith(_TRACKING_PARAM_PREFIXES)


def extract_domain(url: str) -> str | None:
    """Return the canonical registrable domain (``www.Example.com/x`` -> ``example.com``)."""
    normalized = normalize_url(url)
    if not normalized:
        return None
    host = urlsplit(normalized).hostname or ""
    result = _extract(host)
    if not result.domain or not result.suffix:
        return None
    return f"{result.domain}.{result.suffix}".lower()


def root_url(url: str) -> str | None:
    """Return the scheme + host root of a URL, e.g. ``https://example.com``."""
    normalized = normalize_url(url)
    if not normalized:
        return None
    parts = urlsplit(normalized)
    return f"{parts.scheme}://{parts.netloc}"


def _configured_exclusions() -> frozenset[str]:
    """Extra domains from SEARCH_EXCLUDED_DOMAINS, so new aggregators can be
    blocked without a code change."""
    extra = settings.search_excluded_domains or ""
    return frozenset(
        item.strip().lower().lstrip("www.")
        for item in extra.replace("\n", ",").split(",")
        if item.strip()
    )


def is_excluded_domain(domain: str | None) -> bool:
    """True for directories, social networks and other non-company hosts."""
    if not domain:
        return True
    if domain in EXCLUDED_DOMAINS or domain in _configured_exclusions():
        return True
    # Catch country variants of excluded hosts, e.g. amazon.co.uk, google.de.
    label = domain.split(".", 1)[0]
    return any(label == excluded.split(".", 1)[0] for excluded in EXCLUDED_DOMAINS)


def is_probable_document(url: str) -> bool:
    normalized = normalize_url(url)
    if not normalized:
        return True
    path = urlsplit(normalized).path.lower()
    return path.endswith(_NON_PAGE_EXTENSIONS)


def domain_to_name(domain: str) -> str:
    """Fallback company name derived from the domain itself."""
    label = domain.split(".", 1)[0].replace("-", " ").replace("_", " ")
    return " ".join(word.capitalize() for word in label.split() if word) or domain


def derive_company_name(title: str | None, domain: str) -> str:
    """Best-effort company name from a search result title, falling back to the domain.

    Never invents information: it only trims known title noise.
    """
    if not title:
        return domain_to_name(domain)

    candidates = [title]
    for separator in _TITLE_SEPARATORS:
        if separator in title:
            candidates = [part.strip() for part in title.split(separator) if part.strip()]
            break

    for candidate in candidates:
        cleaned = _NAME_NOISE.sub("", candidate)
        cleaned = _WHITESPACE.sub(" ", cleaned).strip(" -–—|:,·»")
        if 2 <= len(cleaned) <= 120 and re.search(r"[A-Za-z]", cleaned):
            return cleaned[:120]

    return domain_to_name(domain)
