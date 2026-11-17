"""france24.com — monthly FR archives with /2/, /3/ pagination via Playwright."""

from __future__ import annotations

import logging
from datetime import date
from urllib.parse import unquote, urljoin

from src.scrapers.archive_urls import as_date, france24_archive_url, step_back
from src.scrapers.browser import browser_page, open_url
from src.scrapers.browser_archive import BrowserArchiveScraper
from src.scrapers.normalize import normalize_url
from src.scrapers.pagination import collect_paginated_links, france24_month_page_urls
from src.scrapers.registry import register_scraper

logger = logging.getLogger(__name__)

_SKIP_PARTS = ("/vidéo/", "/video/", "/émissions/", "/emissions/", "/tv-shows/", "/archives/")


@register_scraper
class France24Scraper(BrowserArchiveScraper):
    source_name = "france24"
    base_url = "https://www.france24.com/fr/"
    headed = True
    # France24 blocks context.request (403); full navigation works.
    prefer_context_request = False
    min_content_chars = 200
    max_pages_per_month = 20
    max_months = 12
    content_selectors = [
        "#main-content",
        ".t-content--article",
        ".t-content",
        "article",
        "main",
    ]

    def archive_url_for(self, day: date) -> str:
        return france24_archive_url(day)

    def extract_listing_links(self, html: str, archive_url: str) -> list[str]:
        soup = self.soup(html)
        urls: list[str] = []
        for a in soup.select("a.a-archive-link, .o-archive-list a[href]"):
            url = urljoin(archive_url, a.get("href") or "").split("#")[0]
            decoded = unquote(url).lower()
            if "france24.com/fr/" not in decoded:
                continue
            if any(part in decoded for part in _SKIP_PARTS):
                continue
            urls.append(url)
        return urls

    def _list_with_page(self, page, limit: int) -> list[str]:
        """Walk months backwards; for each month paginate / , /2/ , /3/ ..."""
        seen: set[str] = set()
        ordered: list[str] = []
        day = as_date()
        empty_months = 0

        def fetch_html(url: str) -> str:
            # Dismiss cookies on first archive page only; later pages are same site.
            return open_url(page, url, wait_ms=1200, dismiss=True, timeout_ms=25000)

        for _ in range(self.max_months):
            if len(ordered) >= limit:
                break

            month_url = self.archive_url_for(day)
            remaining = limit - len(ordered)
            page_urls = france24_month_page_urls(month_url, max_pages=self.max_pages_per_month)
            before = len(ordered)
            month_links = collect_paginated_links(
                page_urls=page_urls,
                fetch_html=fetch_html,
                extract_links=self.extract_listing_links,
                source_name=self.source_name,
                already_seen=seen,
                stop_when_no_new=True,
                limit=remaining,
            )
            for url in month_links:
                canon = normalize_url(url)
                if not canon or canon in seen:
                    continue
                seen.add(canon)
                ordered.append(url)
                if len(ordered) >= limit:
                    break

            gained = len(ordered) - before
            logger.info(
                "[%s] month %s: +%s (total %s/%s)",
                self.source_name,
                month_url,
                gained,
                len(ordered),
                limit,
            )
            if gained == 0:
                empty_months += 1
                if empty_months >= 3:
                    break
            else:
                empty_months = 0

            # jump to previous month
            day = step_back(day.replace(day=1), unit="month")

        return ordered[:limit]

    def list_article_urls(self, limit: int) -> list[str]:
        with browser_page(self.settings, headed=self.headed) as page:
            return self._list_with_page(page, limit)
