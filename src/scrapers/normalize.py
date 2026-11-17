"""URL canonicalization to avoid duplicate articles."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

_DROP_QUERY_PREFIXES = ("utm_", "fbclid", "gclid", "mc_", "vero_")
_DROP_QUERY_KEYS = {"fbclid", "gclid", "igshid", "ref", "s"}


def normalize_url(url: str) -> str:
    """Normalize URL for deduplication (strip tracking, fragment, trailing slash)."""
    if not url:
        return ""
    raw = url.strip().split("#")[0]
    parsed = urlparse(raw)

    scheme = (parsed.scheme or "https").lower()
    if scheme == "http":
        scheme = "https"

    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]

    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path[:-1]

    query_items = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        lk = key.lower()
        if lk in _DROP_QUERY_KEYS or any(lk.startswith(p) for p in _DROP_QUERY_PREFIXES):
            continue
        query_items.append((key, value))
    query = urlencode(query_items, doseq=True)

    return urlunparse((scheme, netloc, path, "", query, ""))
