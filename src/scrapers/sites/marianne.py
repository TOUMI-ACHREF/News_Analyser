"""marianne.net — daily archives (httpx) + HTML article body."""

from __future__ import annotations

import re
from datetime import date
from urllib.parse import urljoin, urlparse

from src.scrapers.archive_urls import marianne_archive_url
from src.scrapers.base import BaseScraper, ScrapedArticle
from src.scrapers.date_walk import walk_archive_dates
from src.scrapers.exceptions import ParseError
from src.scrapers.html_extract import extract_content, extract_title
from src.scrapers.registry import register_scraper


@register_scraper
class MarianneScraper(BaseScraper):
    source_name = "marianne"
    base_url = "https://www.marianne.net/"

    def list_article_urls(self, limit: int) -> list[str]:
        return walk_archive_dates(
            self._links_for_day,
            limit=limit,
            max_days=self.settings.max_archive_days,
            empty_streak_max=self.settings.archive_empty_streak,
            source_name=self.source_name,
        )

    def _links_for_day(self, day: date) -> list[str]:
        html = self.fetch_html(marianne_archive_url(day))
        soup = self.soup(html)
        urls: list[str] = []
        for a in soup.select(".thumbnail__content a[href], article a[href], h2 a[href], h3 a[href], main a[href]"):
            url = urljoin(self.base_url, a.get("href") or "").split("#")[0]
            if "www.marianne.net" not in url:
                continue
            if any(x in url for x in ("/archives/", "/auteur/", "/tag/", "/abonnement")):
                continue
            segs = [p for p in urlparse(url).path.split("/") if p]
            if len(segs) < 2:
                continue
            if len(segs) == 2 and len(segs[1]) < 18:
                continue
            if not re.search(r"marianne\.net/[a-z0-9\-]+/[a-z0-9\-]+", url):
                continue
            urls.append(url)
        return urls

    def parse_article(self, url: str) -> ScrapedArticle:
        soup = self.soup(self.fetch_html(url))
        title = extract_title(soup)
        content = extract_content(
            soup,
            selectors=[".article__content", "[itemprop='articleBody']", "article", "main"],
        )
        if not title or not content:
            raise ParseError(f"Empty title/content for {url}")
        return ScrapedArticle(url=url, title=title, content=content, source=self.source_name)
