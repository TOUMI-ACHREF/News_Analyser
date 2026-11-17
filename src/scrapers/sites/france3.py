"""france3-regions — daily archives (httpx) + HTML article body."""

from __future__ import annotations

from datetime import date
from urllib.parse import urljoin

from src.scrapers.archive_urls import france3_archive_url
from src.scrapers.base import BaseScraper, ScrapedArticle
from src.scrapers.date_walk import walk_archive_dates
from src.scrapers.exceptions import ParseError
from src.scrapers.html_extract import extract_content, extract_title
from src.scrapers.registry import register_scraper


@register_scraper
class France3Scraper(BaseScraper):
    source_name = "france3"
    base_url = "https://france3-regions.franceinfo.fr/"

    def list_article_urls(self, limit: int) -> list[str]:
        return walk_archive_dates(
            self._links_for_day,
            limit=limit,
            max_days=self.settings.max_archive_days,
            empty_streak_max=self.settings.archive_empty_streak,
            source_name=self.source_name,
        )

    def _links_for_day(self, day: date) -> list[str]:
        html = self.fetch_html(france3_archive_url(day))
        soup = self.soup(html)
        urls: list[str] = []
        for a in soup.select("a[href]"):
            url = urljoin(self.base_url, a.get("href") or "").split("#")[0]
            if not url.endswith(".html"):
                continue
            if "franceinfo.fr" not in url and "francetvinfo.fr" not in url:
                continue
            if "/archives/" in url:
                continue
            urls.append(url)
        return urls

    def parse_article(self, url: str) -> ScrapedArticle:
        soup = self.soup(self.fetch_html(url))
        title = extract_title(soup)
        content = extract_content(
            soup,
            selectors=["[itemprop='articleBody']", ".c-body", "article", "main"],
        )
        if not title or not content:
            raise ParseError(f"Empty title/content for {url}")
        return ScrapedArticle(url=url, title=title, content=content, source=self.source_name)
