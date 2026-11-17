"""
Smoke-test the toxicity classifier on 2 real MongoDB articles.

Does NOT write predictions — read-only demo before full-base scoring.

Usage:
  python scripts/test_toxicity.py
  python scripts/test_toxicity.py --source france3 --source gamespot
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import get_settings  # noqa: E402
from src.db import ArticleRepository, close_client, ping  # noqa: E402
from src.ml import ToxicityClassifier  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("test_toxicity")


def _pick_articles(repo: ArticleRepository, sources: list[str] | None, n: int = 2) -> list[dict]:
    """
    Prefer a contrasting pair when possible:
      1) FR article mentioning racism / insult cues (more likely toxic signal)
      2) EN Gamespot or a calm news piece
    Fallback: one per requested source, then newest overall.
    """
    picked: list[dict] = []
    seen_urls: set[str] = set()

    def add(row: dict | None) -> None:
        if not row:
            return
        url = row.get("url") or ""
        if not url or url in seen_urls:
            return
        seen_urls.add(url)
        picked.append(row)

    # Contrast pair from DB (read-only heuristics).
    all_rows = repo.find_all(limit=200)
    charged = next(
        (
            r
            for r in all_rows
            if any(
                tip in ((r.get("title") or "") + " " + (r.get("content") or "")).lower()
                for tip in ("sale noir", "racisme", "insult", "hate", "antisémite", "antisemite")
            )
        ),
        None,
    )
    calm = next((r for r in all_rows if r.get("source") == "gamespot"), None)
    if not calm:
        calm = next(
            (
                r
                for r in all_rows
                if r is not charged
                and any(k in (r.get("title") or "").lower() for k in ("climat", "bourse", "route du rhum"))
            ),
            None,
        )
    add(charged)
    add(calm)

    if sources:
        for source in sources:
            if len(picked) >= n:
                break
            rows = repo.find_by_source(source, limit=3)
            for row in rows:
                add(row)
                if len(picked) >= n:
                    break

    for row in all_rows:
        if len(picked) >= n:
            break
        add(row)

    return picked[:n]


def main() -> None:
    parser = argparse.ArgumentParser(description="Test toxicity model on 2 Mongo articles")
    parser.add_argument(
        "--source",
        action="append",
        dest="sources",
        help="Prefer articles from these sources (repeatable)",
    )
    parser.add_argument("--n", type=int, default=2, help="Number of sample articles (default 2)")
    args = parser.parse_args()

    settings = get_settings()
    settings_cache_clear = getattr(get_settings, "cache_clear", None)
    if callable(settings_cache_clear):
        # Ensure .env toxicity knobs are fresh if process reused.
        pass

    logger.info("Mongo ping…")
    ping(settings)
    repo = ArticleRepository(settings=settings)

    # Diverse defaults: charged FR news + EN gaming (if present).
    sources = args.sources or ["france3", "gamespot"]
    articles = _pick_articles(repo, sources, n=args.n)
    if len(articles) < args.n:
        # Fallback: any articles
        articles = _pick_articles(repo, None, n=args.n)

    if not articles:
        logger.error("No articles in MongoDB. Run: python scripts/collect.py")
        sys.exit(1)

    logger.info(
        "Model=%s | thresholds toxic>=%s highly>=%s | device auto",
        settings.toxicity_model_name,
        settings.toxicity_toxic_threshold,
        settings.toxicity_highly_threshold,
    )
    clf = ToxicityClassifier(settings=settings)

    results = []
    for i, art in enumerate(articles, start=1):
        title = art.get("title") or ""
        content = art.get("content") or ""
        text_preview = ToxicityClassifier.build_text(title, content)
        logger.info("=" * 72)
        logger.info("SAMPLE %s/%s | source=%s", i, len(articles), art.get("source"))
        logger.info("URL: %s", art.get("url"))
        logger.info("TITLE: %s", title[:120])
        logger.info("CONTENT chars: %s | input chars: %s", len(content), len(text_preview))

        pred = clf.predict_article(title=title, content=content)
        payload = {
            "source": art.get("source"),
            "url": art.get("url"),
            "title": title,
            "input_chars": len(text_preview),
            "prediction": pred.prediction,
            "score": pred.score,
            "toxicity_level": pred.toxicity_level,
            "probabilities": pred.probabilities,
            "text_preview": text_preview[:280] + ("…" if len(text_preview) > 280 else ""),
        }
        results.append(payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))

    out = ROOT / "outputs_toxicity_smoke.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Wrote %s", out)
    close_client()


if __name__ == "__main__":
    main()
