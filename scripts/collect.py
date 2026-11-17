"""
Collect articles equally from each registered scraper into MongoDB.

Per source:
  1. scrape up to MAX_ARTICLES_PER_SOURCE (default 30)
  2. upsert by normalized URL into `articles` as soon as each article is parsed
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import get_settings  # noqa: E402
from src.db import ArticleRepository, close_client, ensure_indexes, ping  # noqa: E402
from src.scrapers import create_scraper, list_registered_sources  # noqa: E402
from src.scrapers.exceptions import ScraperError  # noqa: E402
import src.scrapers.sites  # noqa: E402, F401

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("collect")

# httpx / RSS first so Mongo gets data even if Playwright sources are slow.
SOURCE_ORDER = (
    "france3",
    "gamespot",
    "humanite",
    "marianne",
    "mediacites",
    "france24",
    "lemonde",
    "lepoint",
)


def _ordered_sources(registered: list[str], requested: list[str] | None) -> list[str]:
    pool = set(registered)
    if requested:
        selected = [s for s in requested if s in pool]
        missing = sorted(set(requested) - pool)
        if missing:
            logger.warning("Unknown sources skipped: %s", ", ".join(missing))
        return selected

    ordered = [s for s in SOURCE_ORDER if s in pool]
    leftover = sorted(pool - set(ordered))
    return ordered + leftover


def collect(
    *,
    sources: list[str] | None = None,
    limit: int | None = None,
    skip_mongo_indexes: bool = False,
) -> dict[str, int]:
    settings = get_settings()
    per_source_limit = limit if limit is not None else settings.max_articles_per_source
    selected = _ordered_sources(list_registered_sources(), sources)

    if not selected:
        logger.error("No scrapers selected.")
        return {}

    logger.info("Mongo ping…")
    ping(settings)
    logger.info("Mongo OK (%s / %s)", settings.mongo_uri, settings.mongo_db)

    if not skip_mongo_indexes:
        ensure_indexes(settings)

    repo = ArticleRepository(settings=settings)
    results: dict[str, int] = {}

    logger.info(
        "Collecting up to %s articles/source from: %s",
        per_source_limit,
        ", ".join(selected),
    )

    try:
        for source_name in selected:
            saved = 0

            def on_article(article, *, _source=source_name) -> None:
                nonlocal saved
                repo.upsert_article(
                    url=article.url,
                    title=article.title,
                    content=article.content,
                    source=article.source,
                )
                saved += 1

            try:
                logger.info("===== [%s] start (target %s) =====", source_name, per_source_limit)
                with create_scraper(source_name, settings=settings) as scraper:
                    articles = scraper.scrape(limit=per_source_limit, on_article=on_article)
                results[source_name] = saved or len(articles)
                logger.info(
                    "===== [%s] done — %s in Mongo (scrape returned %s) =====",
                    source_name,
                    results[source_name],
                    len(articles),
                )
            except KeyboardInterrupt:
                results[source_name] = saved
                logger.warning(
                    "[%s] interrupted — %s articles already in Mongo; stopping collect",
                    source_name,
                    saved,
                )
                raise
            except ScraperError:
                logger.exception("[%s] scraper failed — continuing (%s already saved)", source_name, saved)
                results[source_name] = saved
            except Exception:
                logger.exception(
                    "[%s] unexpected failure — continuing (%s already saved)",
                    source_name,
                    saved,
                )
                results[source_name] = saved
    finally:
        close_client()

    logger.info(
        "Done. Saved %s articles across %s sources. DB count check left to you / Compass.",
        sum(results.values()),
        len(results),
    )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect news articles into MongoDB")
    parser.add_argument("--source", action="append", dest="sources", help="Repeatable source filter")
    parser.add_argument("--limit", type=int, default=None, help="Max articles per source")
    parser.add_argument("--skip-indexes", action="store_true")
    args = parser.parse_args()
    collect(sources=args.sources, limit=args.limit, skip_mongo_indexes=args.skip_indexes)


if __name__ == "__main__":
    main()
