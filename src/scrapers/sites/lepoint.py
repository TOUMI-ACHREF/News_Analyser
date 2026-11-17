"""lepoint.fr — daily archives via headed Playwright (httpx is blocked)."""

from __future__ import annotations

import re
from datetime import date
from urllib.parse import urljoin

from src.scrapers.archive_urls import lepoint_archive_url
from src.scrapers.browser_archive import BrowserArchiveScraper
from src.scrapers.registry import register_scraper

ARTICLE_RE = re.compile(
    r"^https?://(?:www\.)?lepoint\.fr/"
    r"(?!tags/|stories/|magazine/|html/|auteur/|video/|videos/|services/)"
    r"[a-z0-9\-]+/"
    r"[a-z0-9\-]+-[A-Za-z0-9]{16,}/?$",
    re.I,
)


@register_scraper
class LepointScraper(BrowserArchiveScraper):
    source_name = "lepoint"
    base_url = "https://www.lepoint.fr/"
    headed = True
    content_selectors = ["article", "[itemprop='articleBody']", "main"]

    def archive_url_for(self, day: date) -> str:
        return lepoint_archive_url(day)

    def extract_listing_links(self, html: str, archive_url: str) -> list[str]:
        soup = self.soup(html)
        urls: list[str] = []
        for a in soup.select("article.story-item a.c-link, .stories-list a[href], .story-item a[href]"):
            url = urljoin(archive_url, a.get("href") or "").split("#")[0].split("?")[0]
            if ARTICLE_RE.match(url):
                urls.append(url)
        return urls
