"""Scraping package: base interface, registry and site scrapers."""

from src.scrapers.base import BaseScraper, ScrapedArticle
from src.scrapers.exceptions import (
    FetchError,
    ParseError,
    ScraperError,
    UnknownSourceError,
)
from src.scrapers.registry import (
    SCRAPER_REGISTRY,
    create_scraper,
    get_scraper_class,
    list_registered_sources,
    register_scraper,
)

# Register implemented site scrapers on package import.
from src.scrapers import sites as _sites  # noqa: F401

__all__ = [
    "BaseScraper",
    "ScrapedArticle",
    "ScraperError",
    "FetchError",
    "ParseError",
    "UnknownSourceError",
    "SCRAPER_REGISTRY",
    "register_scraper",
    "get_scraper_class",
    "create_scraper",
    "list_registered_sources",
]
