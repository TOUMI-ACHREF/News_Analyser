"""humanite.fr — daily archives with ?paged=N pagination + HTML body."""

from __future__ import annotations

from datetime import date
from urllib.parse import urljoin

from src.scrapers.archive_urls import humanite_archive_url
from src.scrapers.base import BaseScraper, ScrapedArticle
from src.scrapers.date_walk import walk_archive_dates
from src.scrapers.exceptions import ParseError
from src.scrapers.html_extract import extract_content, extract_title
from src.scrapers.pagination import collect_paginated_links, humanite_day_page_urls
from src.scrapers.registry import register_scraper


@register_scraper
class HumaniteScraper(BaseScraper):
    source_name = "humanite"
    base_url = "https://www.humanite.fr/"
    max_pages_per_day = 15

    def list_article_urls(self, limit: int) -> list[str]:
        return walk_archive_dates(
            self._links_for_day,
            limit=limit,
            max_days=self.settings.max_archive_days,
            empty_streak_max=self.settings.archive_empty_streak,
            source_name=self.source_name,
        )

    def _extract_links(self, html: str, page_url: str) -> list[str]:
        soup = self.soup(html)
        urls: list[str] = []
        for a in soup.select("article a[href], .article-small a[href], main a[href]"):
            url = urljoin(self.base_url, a.get("href") or "").split("#")[0]
            if "humanite.fr" not in url:
                continue
            if any(
                x in url
                for x in (
                    "/toutes-les-archives/",
                    "/mot-cle/",
                    "/surtitre/",
                    "/sections/",
                    "kiosque.",
                )
            ):
                continue
            if url.rstrip("/").count("/") < 4:
                continue
            urls.append(url)
        return urls

    def _links_for_day(self, day: date, remaining: int = 100) -> list[str]:
        day_url = humanite_archive_url(day)
        page_urls = humanite_day_page_urls(day_url, max_pages=self.max_pages_per_day)
        return collect_paginated_links(
            page_urls=page_urls,
            fetch_html=self.fetch_html,
            extract_links=self._extract_links,
            source_name=self.source_name,
            stop_when_no_new=True,
            limit=remaining,
        )

    def parse_article(self, url: str) -> ScrapedArticle:
        soup = self.soup(self.fetch_html(url))
        title = extract_title(soup)
        content = extract_content(soup, selectors=["article", "main", ".article-content"])
        if not title or not content:
            raise ParseError(f"Empty title/content for {url}")
        return ScrapedArticle(url=url, title=title, content=content, source=self.source_name)
