"""Shared scraper interface and HTTP helpers."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from config.settings import Settings, get_settings
from src.scrapers.exceptions import FetchError, ParseError, PermanentFetchError
from src.scrapers.normalize import normalize_url

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ScrapedArticle:
    """Normalized article payload ready for MongoDB storage."""

    url: str
    title: str
    content: str
    source: str

    def to_dict(self) -> dict[str, str]:
        return {
            "url": self.url,
            "title": self.title,
            "content": self.content,
            "source": self.source,
        }


class BaseScraper(ABC):
    """
    Contract for every site scraper.

    Subclasses implement:
    - `list_article_urls`: discover recent article links from the homepage / listing
    - `parse_article`: extract title + text content from an article page
    """

    source_name: str
    base_url: str

    def __init__(self, settings: Settings | None = None, client: httpx.Client | None = None):
        self.settings = settings or get_settings()
        self._owns_client = client is None
        self.client = client or httpx.Client(
            timeout=self.settings.scrape_timeout_seconds,
            headers={
                "User-Agent": self.settings.scrape_user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
            },
            follow_redirects=True,
        )

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> BaseScraper:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    # --- HTTP / HTML helpers -------------------------------------------------

    @retry(
        retry=retry_if_exception(
            lambda exc: isinstance(exc, FetchError) and not isinstance(exc, PermanentFetchError)
        ),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    def fetch_html(self, url: str) -> str:
        """GET a page and return HTML. Retries transient network/5xx failures only."""
        try:
            response = self.client.get(url)
            if response.status_code in {400, 401, 403, 404, 410, 451}:
                raise PermanentFetchError(f"HTTP {response.status_code} for {url}")
            response.raise_for_status()
            return response.text
        except PermanentFetchError:
            raise
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status is not None and 400 <= status < 500 and status not in {408, 429}:
                raise PermanentFetchError(f"Failed to fetch {url}: {exc}") from exc
            raise FetchError(f"Failed to fetch {url}: {exc}") from exc
        except httpx.HTTPError as exc:
            raise FetchError(f"Failed to fetch {url}: {exc}") from exc

    def soup(self, html: str) -> BeautifulSoup:
        return BeautifulSoup(html, "lxml")

    def absolute_url(self, href: str) -> str:
        """Resolve a possibly relative href against the site base URL."""
        return urljoin(self.base_url, href)

    def is_same_domain(self, url: str) -> bool:
        base_host = urlparse(self.base_url).netloc.removeprefix("www.")
        url_host = urlparse(url).netloc.removeprefix("www.")
        return bool(url_host) and (url_host == base_host or url_host.endswith("." + base_host))

    @staticmethod
    def clean_text(value: Optional[str]) -> str:
        if not value:
            return ""
        return " ".join(value.split()).strip()

    # --- Site-specific hooks -------------------------------------------------

    @abstractmethod
    def list_article_urls(self, limit: int) -> list[str]:
        """Return unique recent article URLs (up to `limit`)."""

    @abstractmethod
    def parse_article(self, url: str) -> ScrapedArticle:
        """
        Parse one article page into a ScrapedArticle.

        Must raise ParseError when title or content cannot be extracted.
        """

    # --- Orchestration -------------------------------------------------------

    def scrape(
        self,
        limit: int | None = None,
        *,
        on_article: Callable[[ScrapedArticle], None] | None = None,
    ) -> list[ScrapedArticle]:
        """
        Collect articles for this source.

        Listing failures abort the run for this source.
        Per-article parse/fetch errors are logged and skipped.
        Optional `on_article(article)` is called after each successful parse
        (used by collect.py to upsert into Mongo immediately).
        """
        max_articles = limit if limit is not None else self.settings.max_articles_per_source
        articles: list[ScrapedArticle] = []

        try:
            urls = self.list_article_urls(max_articles)
        except FetchError:
            logger.exception("[%s] Failed to list article URLs", self.source_name)
            raise
        except Exception as exc:
            logger.exception("[%s] Unexpected error while listing URLs", self.source_name)
            raise FetchError(str(exc)) from exc

        logger.info("[%s] Listed %s URLs — parsing articles…", self.source_name, len(urls))
        seen: set[str] = set()
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
                article = self.parse_article(url)
                if not article.title or not article.content:
                    raise ParseError(f"Empty title/content for {url}")
                article.url = normalize_url(article.url) or article.url
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
