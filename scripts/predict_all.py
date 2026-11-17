"""
Score every article in MongoDB and upsert into `predictions`.

Usage:
  python scripts/predict_all.py
  python scripts/predict_all.py --source france3
  python scripts/predict_all.py --limit 10
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
from src.db import (  # noqa: E402
    ArticleRepository,
    PredictionRepository,
    close_client,
    ensure_indexes,
    ping,
)
from src.ml import ToxicityClassifier  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("predict_all")

# Store a bounded preview in Mongo (full article can be huge).
TEXT_STORE_MAX = 2000


def main() -> None:
    parser = argparse.ArgumentParser(description="Predict toxicity for all Mongo articles")
    parser.add_argument("--source", action="append", dest="sources", help="Filter by source")
    parser.add_argument("--limit", type=int, default=None, help="Max articles to score")
    parser.add_argument("--skip-indexes", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    logger.info("Mongo ping…")
    ping(settings)
    if not args.skip_indexes:
        ensure_indexes(settings)

    articles_repo = ArticleRepository(settings=settings)
    predictions_repo = PredictionRepository(settings=settings)

    if args.sources:
        articles: list[dict] = []
        for source in args.sources:
            articles.extend(articles_repo.find_by_source(source, limit=args.limit or 10_000))
    else:
        # High ceiling so we cover the full collection for this project size.
        articles = articles_repo.find_all(limit=args.limit or 50_000)

    if args.limit is not None:
        articles = articles[: args.limit]

    total = len(articles)
    if total == 0:
        logger.error("No articles found. Run collect.py first.")
        sys.exit(1)

    logger.info("Scoring %s articles with %s…", total, settings.toxicity_model_name)
    clf = ToxicityClassifier(settings=settings)

    ok = 0
    skipped = 0
    errors = 0
    for index, art in enumerate(articles, start=1):
        url = art.get("url") or ""
        title = art.get("title") or ""
        content = art.get("content") or ""
        source = art.get("source")
        if not url:
            skipped += 1
            continue
        try:
            result = clf.predict_article(title=title, content=content)
            text_store = result.text[:TEXT_STORE_MAX]
            predictions_repo.upsert_by_url(
                text=text_store,
                prediction=result.prediction,
                score=result.score,
                url=url,
                source=source,
                toxicity_level=result.toxicity_level,
                probabilities=result.probabilities,
            )
            ok += 1
            if index == 1 or index % 10 == 0 or index == total:
                logger.info(
                    "[%s/%s] %s | %s | score=%.4f | %s",
                    index,
                    total,
                    source,
                    result.prediction,
                    result.score,
                    result.toxicity_level,
                )
        except Exception:  # noqa: BLE001
            errors += 1
            logger.exception("[%s/%s] failed for %s", index, total, url)

    logger.info(
        "Done. saved=%s skipped=%s errors=%s | predictions in Mongo: %s",
        ok,
        skipped,
        errors,
        predictions_repo.count(),
    )
    close_client()


if __name__ == "__main__":
    main()
