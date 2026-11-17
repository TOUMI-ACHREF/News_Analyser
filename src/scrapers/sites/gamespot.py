"""gamespot.com — RSS fulltext (HTML listing/pages often blocked)."""

from __future__ import annotations

from src.scrapers.base import BaseScraper, ScrapedArticle
from src.scrapers.exceptions import ParseError
from src.scrapers.normalize import normalize_url
from src.scrapers.registry import register_scraper
from src.scrapers.rss import RssItem, fetch_rss_items


@register_scraper
class GamespotScraper(BaseScraper):
    source_name = "gamespot"
    base_url = "https://www.gamespot.com/"
    feed_urls = [
        "https://www.gamespot.com/feeds/news/",
        "https://www.gamespot.com/feeds/mashup/",
        "https://www.gamespot.com/feeds/reviews/",
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._by_url: dict[str, RssItem] = {}

    def list_article_urls(self, limit: int) -> list[str]:
        self._by_url.clear()
        seen: set[str] = set()
        urls: list[str] = []
        for feed in self.feed_urls:
            try:
                items = fetch_rss_items(self, feed)
            except Exception:
                continue
            for item in items:
                canon = normalize_url(item.url)
                if not canon or canon in seen:
                    continue
                if len(item.summary) < 250:
                    continue
                seen.add(canon)
                self._by_url[canon] = item
                urls.append(item.url.split("#")[0])
                if len(urls) >= limit:
                    return urls
        return urls

    def parse_article(self, url: str) -> ScrapedArticle:
        item = self._by_url.get(normalize_url(url))
        if item is None or len(item.summary) < 250:
            raise ParseError(f"No RSS fulltext for {url}")
        return ScrapedArticle(
            url=url,
            title=item.title or url,
            content=item.summary,
            source=self.source_name,
        )
