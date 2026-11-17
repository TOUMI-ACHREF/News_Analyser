"""Database package: MongoDB client and repositories."""

from src.db.client import close_client, ensure_indexes, get_client, get_db, ping
from src.db.repositories import ArticleRepository, PredictionRepository, StatsRepository

__all__ = [
    "get_client",
    "get_db",
    "close_client",
    "ping",
    "ensure_indexes",
    "ArticleRepository",
    "PredictionRepository",
    "StatsRepository",
]
