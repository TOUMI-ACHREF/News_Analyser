"""CRUD repositories for articles, predictions and toxicity stats."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.results import InsertOneResult, UpdateResult

from config.settings import Settings, get_settings
from src.db.client import get_db


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ArticleRepository:
    """Persist scraped articles (url, title, content, source)."""

    def __init__(self, db: Database | None = None, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.db = db or get_db(self.settings)
        self.collection: Collection = self.db[self.settings.articles_collection]

    def upsert_article(
        self,
        *,
        url: str,
        title: str,
        content: str,
        source: str,
        scraped_at: datetime | None = None,
    ) -> UpdateResult:
        """Insert or update an article keyed by URL."""
        document = {
            "url": url,
            "title": title,
            "content": content,
            "source": source,
            "scraped_at": scraped_at or _utc_now(),
        }
        return self.collection.update_one(
            {"url": url},
            {"$set": document},
            upsert=True,
        )

    def upsert_many(self, articles: list[dict[str, Any]]) -> int:
        """Upsert a batch of articles. Returns number of processed docs."""
        count = 0
        for article in articles:
            self.upsert_article(
                url=article["url"],
                title=article["title"],
                content=article["content"],
                source=article["source"],
                scraped_at=article.get("scraped_at"),
            )
            count += 1
        return count

    def find_by_url(self, url: str) -> Optional[dict[str, Any]]:
        return self.collection.find_one({"url": url})

    def find_by_source(self, source: str, limit: int = 100) -> list[dict[str, Any]]:
        cursor = (
            self.collection.find({"source": source})
            .sort("scraped_at", -1)
            .limit(limit)
        )
        return list(cursor)

    def find_all(self, limit: int = 1000) -> list[dict[str, Any]]:
        return list(self.collection.find().sort("scraped_at", -1).limit(limit))

    def count(self, source: str | None = None) -> int:
        if source:
            return self.collection.count_documents({"source": source})
        return self.collection.count_documents({})


class PredictionRepository:
    """Persist API / pipeline toxicity predictions."""

    def __init__(self, db: Database | None = None, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.db = db or get_db(self.settings)
        self.collection: Collection = self.db[self.settings.predictions_collection]

    def create(
        self,
        *,
        text: str,
        prediction: str,
        score: float,
        url: str | None = None,
        source: str | None = None,
        date: datetime | None = None,
        toxicity_level: str | None = None,
    ) -> InsertOneResult:
        """
        Store one prediction.

        Required by the brief: text, prediction, score, date, optional url.
        `source` and `toxicity_level` are extras used by Part 3 analysis.
        """
        document: dict[str, Any] = {
            "text": text,
            "prediction": prediction,
            "score": float(score),
            "date": date or _utc_now(),
        }
        if url is not None:
            document["url"] = url
        if source is not None:
            document["source"] = source
        if toxicity_level is not None:
            document["toxicity_level"] = toxicity_level

        return self.collection.insert_one(document)

    def upsert_by_url(
        self,
        *,
        text: str,
        prediction: str,
        score: float,
        url: str,
        source: str | None = None,
        date: datetime | None = None,
        toxicity_level: str | None = None,
        probabilities: dict[str, float] | None = None,
    ) -> UpdateResult:
        """Insert or replace the latest prediction for an article URL."""
        document: dict[str, Any] = {
            "text": text,
            "prediction": prediction,
            "score": float(score),
            "date": date or _utc_now(),
            "url": url,
        }
        if source is not None:
            document["source"] = source
        if toxicity_level is not None:
            document["toxicity_level"] = toxicity_level
        if probabilities is not None:
            document["probabilities"] = probabilities
        return self.collection.update_one(
            {"url": url},
            {"$set": document},
            upsert=True,
        )

    def find_all(self, limit: int = 1000) -> list[dict[str, Any]]:
        return list(self.collection.find().sort("date", -1).limit(limit))

    def find_by_source(self, source: str, limit: int = 1000) -> list[dict[str, Any]]:
        cursor = (
            self.collection.find({"source": source})
            .sort("date", -1)
            .limit(limit)
        )
        return list(cursor)

    def count(self, source: str | None = None) -> int:
        if source:
            return self.collection.count_documents({"source": source})
        return self.collection.count_documents({})


class StatsRepository:
    """Persist per-source toxicity statistics (Part 3)."""

    def __init__(self, db: Database | None = None, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.db = db or get_db(self.settings)
        self.collection: Collection = self.db[self.settings.stats_collection]

    def upsert_source_stats(
        self,
        *,
        source: str,
        lightly_toxic_pct: float,
        highly_toxic_pct: float,
        total_count: int = 0,
        lightly_toxic_count: int = 0,
        highly_toxic_count: int = 0,
        computed_at: datetime | None = None,
    ) -> UpdateResult:
        """Insert or replace the latest stats document for a source."""
        document = {
            "source": source,
            "lightly_toxic_pct": float(lightly_toxic_pct),
            "highly_toxic_pct": float(highly_toxic_pct),
            "total_count": int(total_count),
            "lightly_toxic_count": int(lightly_toxic_count),
            "highly_toxic_count": int(highly_toxic_count),
            "computed_at": computed_at or _utc_now(),
        }
        return self.collection.update_one(
            {"source": source},
            {"$set": document},
            upsert=True,
        )

    def find_by_source(self, source: str) -> Optional[dict[str, Any]]:
        return self.collection.find_one({"source": source})

    def find_all(self) -> list[dict[str, Any]]:
        return list(self.collection.find().sort("source", 1))

    def delete_all(self) -> int:
        result = self.collection.delete_many({})
        return result.deleted_count
