"""Shared Playwright archive scrape loop (one browser session per run)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date

from src.scrapers.base import BaseScraper, ScrapedArticle
from src.scrapers.browser import browser_page, fetch_with_cookies, open_url
from src.scrapers.date_walk import walk_archive_dates
from src.scrapers.exceptions import FetchError, ParseError
from src.scrapers.html_extract import extract_content, extract_title
from src.scrapers.normalize import normalize_url

logger = logging.getLogger(__name__)


class BrowserArchiveScraper(BaseScraper):
    """
    Listing + article parse through Playwright.

    Subclasses set `headed`, content selectors, and implement
    `extract_listing_links` + `archive_url_for`.
    """

    headed: bool = True
    content_selectors: list[str] = ["article", "main"]
    min_content_chars: int = 250
    # Prefer cookie-authenticated request for article bodies (much faster).
    prefer_context_request: bool = True

    def archive_url_for(self, day: date) -> str:
        raise NotImplementedError

    def extract_listing_links(self, html: str, archive_url: str) -> list[str]:
        raise NotImplementedError

    def list_article_urls(self, limit: int) -> list[str]:
        with browser_page(self.settings, headed=self.headed) as page:
            return self._list_with_page(page, limit)

    def parse_article(self, url: str) -> ScrapedArticle:
        with browser_page(self.settings, headed=self.headed) as page:
            return self._parse_with_page(page, url)

    def scrape(
        self,
        limit: int | None = None,
        *,
        on_article: Callable[[ScrapedArticle], None] | None = None,
    ) -> list[ScrapedArticle]:
        max_articles = limit if limit is not None else self.settings.max_articles_per_source
        articles: list[ScrapedArticle] = []
        seen: set[str] = set()

        with browser_page(self.settings, headed=self.headed) as page:
            urls = self._list_with_page(page, max_articles)
            logger.info("[%s] Listed %s URLs — parsing articles…", self.source_name, len(urls))

            for index, url in enumerate(urls, start=1):
                canon = normalize_url(url)
                if not canon or canon in seen:
                    continue
                seen.add(canon)
                if len(articles) >= max_articles:
                    break

                logger.info(
                    "[%s] fetching article %s/%s %s",
                    self.source_name,
                    index,
                    min(len(urls), max_articles),
                    canon[:110],
                )
                try:
                    article = self._parse_with_page(page, url)
                    article.url = canon
                    articles.append(article)
                    if on_article is not None:
                        on_article(article)
                    logger.info(
                        "[%s] saved article %s/%s (%s chars)",
                        self.source_name,
                        len(articles),
                        max_articles,
                        len(article.content),
                    )
                except (FetchError, ParseError) as exc:
                    logger.warning("[%s] Skipping %s (%s)", self.source_name, url, exc)
                except Exception:
                    logger.exception("[%s] Unexpected error parsing %s", self.source_name, url)

        logger.info("[%s] Collected %s/%s articles", self.source_name, len(articles), max_articles)
        return articles

    def _list_with_page(self, page, limit: int) -> list[str]:
        fetched_listings: set[str] = set()

        def fetch_day(day: date) -> list[str] | None:
            archive = self.archive_url_for(day)
            if archive in fetched_listings:
                return None
            fetched_listings.add(archive)
            html = open_url(page, archive, wait_ms=2000, dismiss=True, timeout_ms=25000)
            return self.extract_listing_links(html, archive)

        return walk_archive_dates(
            fetch_day,
            limit=limit,
            max_days=self.settings.max_archive_days,
            empty_streak_max=self.settings.archive_empty_streak,
            source_name=self.source_name,
        )

    def _parse_with_page(self, page, url: str) -> ScrapedArticle:
        html = ""
        used_navigation = False

        if self.prefer_context_request:
            try:
                html = fetch_with_cookies(page, url, timeout_ms=20000)
            except FetchError as exc:
                logger.info("[%s] context request failed (%s) — navigating", self.source_name, exc)

        if not html:
            used_navigation = True
            html = open_url(page, url, wait_ms=800, dismiss=False, timeout_ms=25000)

        soup = self.soup(html)
        title = extract_title(soup)
        if used_navigation and not title:
            title = (page.title() or "").strip()

        content = extract_content(
            soup,
            selectors=self.content_selectors,
            min_chars=self.min_content_chars,
        )

        if used_navigation and len(content) < self.min_content_chars:
            try:
                texts = page.eval_on_selector_all(
                    "article p, main p, p",
                    "els => els.map(e => (e.innerText || '').trim()).filter(t => t.length > 40)",
                )
                content = "\n".join(texts)
            except Exception:  # noqa: BLE001
                pass

        if not title or len(content) < self.min_content_chars:
            raise ParseError(f"Could not extract title/content from {url}")

        return ScrapedArticle(
            url=url,
            title=self.clean_text(title),
            content=content,
            source=self.source_name,
        )
