"""MongoDB connection helpers."""

from __future__ import annotations

from typing import Optional

from pymongo import ASCENDING, MongoClient
from pymongo.database import Database

from config.settings import Settings, get_settings

_client: Optional[MongoClient] = None


def get_client(settings: Settings | None = None) -> MongoClient:
    """Return a process-wide MongoClient (lazy singleton)."""
    global _client
    if _client is None:
        cfg = settings or get_settings()
        _client = MongoClient(
            cfg.mongo_uri,
            serverSelectionTimeoutMS=5000,
        )
    return _client


def get_db(settings: Settings | None = None) -> Database:
    """Return the configured application database."""
    cfg = settings or get_settings()
    return get_client(cfg)[cfg.mongo_db]


def close_client() -> None:
    """Close the shared client (useful in tests / shutdown hooks)."""
    global _client
    if _client is not None:
        _client.close()
        _client = None


def ping(settings: Settings | None = None) -> bool:
    """Return True if MongoDB answers a ping command."""
    cfg = settings or get_settings()
    get_client(cfg).admin.command("ping")
    return True


def ensure_indexes(settings: Settings | None = None) -> None:
    """Create indexes expected by the repositories."""
    cfg = settings or get_settings()
    db = get_db(cfg)

    db[cfg.articles_collection].create_index(
        [("url", ASCENDING)],
        unique=True,
        name="uniq_article_url",
    )
    db[cfg.articles_collection].create_index(
        [("source", ASCENDING), ("scraped_at", ASCENDING)],
        name="articles_source_scraped_at",
    )

    # Sparse: API /predict may omit url; only indexed docs with a url must be unique.
    db[cfg.predictions_collection].create_index(
        [("url", ASCENDING)],
        unique=True,
        sparse=True,
        name="uniq_prediction_url",
    )
    db[cfg.predictions_collection].create_index(
        [("date", ASCENDING)],
        name="predictions_date",
    )
    db[cfg.predictions_collection].create_index(
        [("source", ASCENDING), ("date", ASCENDING)],
        name="predictions_source_date",
    )

    db[cfg.stats_collection].create_index(
        [("source", ASCENDING)],
        unique=True,
        name="uniq_stats_source",
    )
