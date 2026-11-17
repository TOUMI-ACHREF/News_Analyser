"""Scraper-specific exceptions."""


class ScraperError(Exception):
    """Base error for the scraping layer."""


class FetchError(ScraperError):
    """HTTP / network failure while retrieving a page."""


class PermanentFetchError(FetchError):
    """Non-retryable fetch failure (404, 403, etc.)."""


class ParseError(ScraperError):
    """HTML structure could not be parsed into an article."""


class UnknownSourceError(ScraperError):
    """Requested source is not registered."""
