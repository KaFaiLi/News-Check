"""Utilities for normalizing and canonicalizing URLs."""

from typing import Optional
from urllib.parse import parse_qs, urlparse, urlunparse, urlencode


TRACKING_PARAMS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "source",
    "cmpid",
}


def unwrap_google_url(url: str) -> str:
    """Extract the target URL from Google redirect URLs when present."""
    if not url:
        return url

    if url.startswith("/url?"):
        url = f"https://www.google.com{url}"

    parsed = urlparse(url)
    if "google.com" not in parsed.netloc:
        return url

    if parsed.path != "/url":
        return url

    query = parse_qs(parsed.query)
    for key in ("q", "url"):
        if key in query and query[key]:
            return query[key][0]

    return url


def normalize_url(url: Optional[str]) -> Optional[str]:
    """Normalize URLs for dedupe and source matching."""
    if not url:
        return None

    url = unwrap_google_url(url)
    parsed = urlparse(url)

    if not parsed.scheme or not parsed.netloc:
        return url

    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]

    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")

    query = parse_qs(parsed.query, keep_blank_values=True)
    cleaned_query = {}
    for key, value in query.items():
        if key.lower().startswith("utm_"):
            continue
        if key.lower() in TRACKING_PARAMS:
            continue
        cleaned_query[key] = value

    query_string = urlencode(cleaned_query, doseq=True)

    normalized = urlunparse((parsed.scheme.lower(), netloc, path, "", query_string, ""))
    return normalized
