"""
Compute % lightly / highly toxic per source, save to Mongo, write chart.

Usage:
  python scripts/compute_stats.py
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import get_settings  # noqa: E402
from src.analysis import (  # noqa: E402
    compute_source_stats,
    plot_toxicity_chart,
    render_stats_table,
    save_stats_to_mongo,
)
from src.db import close_client, ensure_indexes, ping  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("compute_stats")


def main() -> None:
    settings = get_settings()
    ping(settings)
    ensure_indexes(settings)

    stats = compute_source_stats(settings)
    if not stats:
        logger.error("No predictions found. Run: python scripts/predict_all.py")
        sys.exit(1)

    saved = save_stats_to_mongo(stats, settings)
    table = render_stats_table(stats)
    print(table)

    out_json = ROOT / "outputs_toxicity_stats.json"
    out_json.write_text(
        json.dumps([s.to_dict() for s in stats], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    chart_path = plot_toxicity_chart(stats, ROOT / "outputs_toxicity_stats.png")

    logger.info("Saved %s source stats to Mongo collection `%s`", saved, settings.stats_collection)
    logger.info("Wrote %s", out_json)
    logger.info("Wrote chart %s", chart_path)
    close_client()


if __name__ == "__main__":
    main()
