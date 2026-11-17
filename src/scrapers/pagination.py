"""Small helpers to walk archive listing pages."""

from __future__ import annotations

import logging
from collections.abc import Callable
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from src.scrapers.normalize import normalize_url

logger = logging.getLogger(__name__)


def with_query(url: str, **params: str | int) -> str:
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    for key, value in params.items():
        query[key] = str(value)
    return urlunparse(parsed._replace(query=urlencode(query)))


def collect_paginated_links(
    *,
    page_urls: list[str],
    fetch_html: Callable[[str], str],
    extract_links: Callable[[str, str], list[str]],
    source_name: str = "",
    already_seen: set[str] | None = None,
    stop_when_no_new: bool = True,
    limit: int | None = None,
) -> list[str]:
    """
    Fetch listing pages in order and accumulate unique article links.

    Stops when:
    - `limit` unique NEW links are collected (if set)
    - a page adds 0 new links (if stop_when_no_new and page index > 1)
    """
    seen = set(already_seen or [])
    ordered: list[str] = []
    label = source_name or "pager"
    baseline = len(seen)

    for index, page_url in enumerate(page_urls, start=1):
        if limit is not None and len(ordered) >= limit:
            break

        html = fetch_html(page_url)
        links = extract_links(html, page_url)
        new = 0
        for url in links:
            if limit is not None and len(ordered) >= limit:
                break
            canon = normalize_url(url)
            if not canon or canon in seen:
                continue
            seen.add(canon)
            ordered.append(url.split("#")[0])
            new += 1

        logger.info(
            "[%s] page %s: +%s (batch %s%s) %s",
            label,
            index,
            new,
            len(ordered),
            f"/{limit}" if limit is not None else "",
            page_url,
        )
        if stop_when_no_new and new == 0 and index > 1:
            break
        if limit is not None and len(ordered) >= limit:
            break

    logger.debug(
        "[%s] pagination done: +%s new (seen was %s)",
        label,
        len(ordered),
        baseline,
    )
    return ordered


def france24_month_page_urls(month_archive_url: str, max_pages: int = 20) -> list[str]:
    """
    France24 month pages:
      /fr/archives/2026/11/
      /fr/archives/2026/11/2/
      /fr/archives/2026/11/3/
    """
    base = month_archive_url.rstrip("/") + "/"
    urls = [base]
    for page in range(2, max_pages + 1):
        urls.append(f"{base}{page}/")
    return urls


def humanite_day_page_urls(day_archive_url: str, max_pages: int = 20) -> list[str]:
    """Humanite day pages: ?paged=1 (implicit), ?paged=2, ..."""
    urls = [day_archive_url]
    for page in range(2, max_pages + 1):
        urls.append(with_query(day_archive_url, paged=page))
    return urls
