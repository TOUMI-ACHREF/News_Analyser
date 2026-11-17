"""Per-source toxicity statistics from Mongo predictions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.db import PredictionRepository, StatsRepository
from config.settings import Settings, get_settings


@dataclass(slots=True)
class SourceToxicityStats:
    source: str
    total_count: int
    lightly_toxic_count: int
    highly_toxic_count: int
    lightly_toxic_pct: float
    highly_toxic_pct: float

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "total_count": self.total_count,
            "lightly_toxic_count": self.lightly_toxic_count,
            "highly_toxic_count": self.highly_toxic_count,
            "lightly_toxic_pct": self.lightly_toxic_pct,
            "highly_toxic_pct": self.highly_toxic_pct,
        }


def _pct(count: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(100.0 * count / total, 2)


def compute_source_stats(
    settings: Settings | None = None,
) -> list[SourceToxicityStats]:
    """
    Aggregate predictions by source.

    Uses `toxicity_level` when present:
      - lightly-toxic
      - highly-toxic
    Falls back to prediction == toxic → highly-toxic.
    """
    cfg = settings or get_settings()
    repo = PredictionRepository(settings=cfg)
    rows = repo.find_all(limit=100_000)

    buckets: dict[str, dict[str, int]] = {}
    for row in rows:
        source = (row.get("source") or "unknown").strip() or "unknown"
        bucket = buckets.setdefault(
            source,
            {"total": 0, "lightly": 0, "highly": 0},
        )
        bucket["total"] += 1

        level = (row.get("toxicity_level") or "").strip().lower()
        if level == "lightly-toxic":
            bucket["lightly"] += 1
        elif level == "highly-toxic":
            bucket["highly"] += 1
        elif (row.get("prediction") or "").strip().lower() == "toxic":
            # Older rows without toxicity_level
            bucket["highly"] += 1

    stats = [
        SourceToxicityStats(
            source=source,
            total_count=vals["total"],
            lightly_toxic_count=vals["lightly"],
            highly_toxic_count=vals["highly"],
            lightly_toxic_pct=_pct(vals["lightly"], vals["total"]),
            highly_toxic_pct=_pct(vals["highly"], vals["total"]),
        )
        for source, vals in sorted(buckets.items())
    ]
    return stats


def save_stats_to_mongo(
    stats: list[SourceToxicityStats],
    settings: Settings | None = None,
) -> int:
    cfg = settings or get_settings()
    repo = StatsRepository(settings=cfg)
    for item in stats:
        repo.upsert_source_stats(
            source=item.source,
            lightly_toxic_pct=item.lightly_toxic_pct,
            highly_toxic_pct=item.highly_toxic_pct,
            total_count=item.total_count,
            lightly_toxic_count=item.lightly_toxic_count,
            highly_toxic_count=item.highly_toxic_count,
        )
    return len(stats)


def render_stats_table(stats: list[SourceToxicityStats]) -> str:
    headers = ("source", "n", "lightly_%", "highly_%", "lightly_n", "highly_n")
    lines = [" | ".join(headers), "-+-".join("-" * len(h) for h in headers)]
    for s in stats:
        lines.append(
            " | ".join(
                [
                    f"{s.source:<12}",
                    f"{s.total_count:>3}",
                    f"{s.lightly_toxic_pct:>8.2f}",
                    f"{s.highly_toxic_pct:>7.2f}",
                    f"{s.lightly_toxic_count:>8}",
                    f"{s.highly_toxic_count:>7}",
                ]
            )
        )
    return "\n".join(lines)


def plot_toxicity_chart(
    stats: list[SourceToxicityStats],
    output_path: str | Path,
) -> Path:
    """Grouped bar chart: lightly vs highly toxic % per source."""
    import matplotlib.pyplot as plt
    import numpy as np

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    sources = [s.source for s in stats]
    lightly = [s.lightly_toxic_pct for s in stats]
    highly = [s.highly_toxic_pct for s in stats]

    x = np.arange(len(sources))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(x - width / 2, lightly, width, label="Lightly toxic %", color="#f0a202")
    ax.bar(x + width / 2, highly, width, label="Highly toxic %", color="#c1121f")
    ax.set_ylabel("% of articles")
    ax.set_title("Toxicity rate per news source")
    ax.set_xticks(x)
    ax.set_xticklabels(sources, rotation=30, ha="right")
    ax.set_ylim(0, max(100, max(lightly + highly + [1]) * 1.15))
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path
