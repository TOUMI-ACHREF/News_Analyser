"""Registry mapping source names to scraper classes."""

from __future__ import annotations

from typing import Type

from src.scrapers.base import BaseScraper
from src.scrapers.exceptions import UnknownSourceError

# Populated by site modules via `@register_scraper` (Task 4).
SCRAPER_REGISTRY: dict[str, Type[BaseScraper]] = {}


def register_scraper(cls: Type[BaseScraper]) -> Type[BaseScraper]:
    """Class decorator: register a scraper under `cls.source_name`."""
    if not getattr(cls, "source_name", None):
        raise ValueError(f"{cls.__name__} must define source_name")
    SCRAPER_REGISTRY[cls.source_name] = cls
    return cls


def get_scraper_class(source_name: str) -> Type[BaseScraper]:
    try:
        return SCRAPER_REGISTRY[source_name]
    except KeyError as exc:
        known = ", ".join(sorted(SCRAPER_REGISTRY)) or "(none registered yet)"
        raise UnknownSourceError(
            f"Unknown source '{source_name}'. Registered: {known}"
        ) from exc


def create_scraper(source_name: str, **kwargs: object) -> BaseScraper:
    """Instantiate a registered scraper by source name."""
    scraper_cls = get_scraper_class(source_name)
    return scraper_cls(**kwargs)  # type: ignore[arg-type]


def list_registered_sources() -> list[str]:
    return sorted(SCRAPER_REGISTRY.keys())
