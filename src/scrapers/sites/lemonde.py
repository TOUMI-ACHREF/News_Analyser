"""lemonde.fr — daily archives via Playwright + auto cookie dismiss."""

from __future__ import annotations

from datetime import date
from urllib.parse import urljoin

from src.scrapers.archive_urls import lemonde_archive_url
from src.scrapers.browser_archive import BrowserArchiveScraper
from src.scrapers.registry import register_scraper


@register_scraper
class LemondeScraper(BrowserArchiveScraper):
    source_name = "lemonde"
    base_url = "https://www.lemonde.fr/"
    headed = True
    content_selectors = [
        "[itemprop='articleBody']",
        ".article__content",
        "article",
        "main",
    ]

    def archive_url_for(self, day: date) -> str:
        return lemonde_archive_url(day)

    def extract_listing_links(self, html: str, archive_url: str) -> list[str]:
        soup = self.soup(html)
        urls: list[str] = []
        for a in soup.select("#river a.teaser__link, .river a.teaser__link, #river a[href], .teaser a[href]"):
            url = urljoin(archive_url, a.get("href") or "").split("#")[0].split("?")[0]
            if "/live/" in url:
                continue
            if "/article/" not in url and "_article_" not in url:
                continue
            # skip partner / service teasers when obvious
            if "guides-d-achat" in url or "empreinte-carbone" in url:
                continue
            urls.append(url)
        return urls
