"""mediacites.fr — RSS listing + HTML body (no useful archive)."""

from __future__ import annotations

from src.scrapers.base import BaseScraper, ScrapedArticle
from src.scrapers.exceptions import ParseError
from src.scrapers.html_extract import extract_content, extract_title
from src.scrapers.normalize import normalize_url
from src.scrapers.registry import register_scraper
from src.scrapers.rss import fetch_rss_items


@register_scraper
class MediacitesScraper(BaseScraper):
    source_name = "mediacites"
    base_url = "https://www.mediacites.fr/"
    feed_url = "https://www.mediacites.fr/feed/"

    def list_article_urls(self, limit: int) -> list[str]:
        items = fetch_rss_items(self, self.feed_url)
        seen: set[str] = set()
        urls: list[str] = []
        for item in items:
            url = normalize_url(item.url)
            if not url or url in seen:
                continue
            # skip shallow hubs
            if url.replace(self.base_url.rstrip("/"), "").count("/") < 3:
                continue
            seen.add(url)
            urls.append(item.url.split("#")[0])
            if len(urls) >= limit:
                break
        return urls

    def parse_article(self, url: str) -> ScrapedArticle:
        soup = self.soup(self.fetch_html(url))
        title = extract_title(soup)
        content = extract_content(soup, selectors=[".entry-content", "article", "main"])
        if not title or not content:
            raise ParseError(f"Empty title/content for {url}")
        return ScrapedArticle(url=url, title=title, content=content, source=self.source_name)
