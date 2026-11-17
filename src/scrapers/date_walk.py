"""Walk archive dates day-by-day until we have enough unique article URLs."""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable
from datetime import date

from src.scrapers.archive_urls import as_date, step_back
from src.scrapers.normalize import normalize_url

logger = logging.getLogger(__name__)

# Return list[str] for a real listing fetch.
# Return None to skip the day without counting it as an empty failure
# (e.g. monthly archive URL already fetched on a previous day).
FetchDayLinks = Callable[[date], list[str] | None]
# Optional: fetch_day(day, remaining_needed) for paginated day listings.
FetchDayLinksWithRemaining = Callable[[date, int], list[str] | None]


def _accepts_remaining(fn: Callable) -> bool:
    try:
        params = list(inspect.signature(fn).parameters.values())
    except (TypeError, ValueError):
        return False
    # Bound methods: skip `self`. Positional-or-keyword / VAR_POSITIONAL.
    if params and params[0].name == "self":
        params = params[1:]
    if any(p.kind == inspect.Parameter.VAR_POSITIONAL for p in params):
        return True
    return len(params) >= 2


def walk_archive_dates(
    fetch_day_links: FetchDayLinks | FetchDayLinksWithRemaining,
    *,
    limit: int,
    max_days: int = 120,
    empty_streak_max: int = 5,
    start: date | None = None,
    source_name: str = "",
) -> list[str]:
    """
    Walk backwards one calendar day at a time:
      today -> yesterday -> ... until `limit` unique URLs.

    - `fetch_day_links(day)` or `fetch_day_links(day, remaining)`
    - return None: skip quietly (same listing already done)
    - empty list / error: increments empty streak
    """
    seen: dict[str, str] = {}
    empty_streak = 0
    day = as_date(start)
    label = source_name or "archive"
    with_remaining = _accepts_remaining(fetch_day_links)

    for _ in range(max_days):
        if len(seen) >= limit:
            break

        remaining = limit - len(seen)
        try:
            if with_remaining:
                links = fetch_day_links(day, remaining)  # type: ignore[call-arg]
            else:
                links = fetch_day_links(day)  # type: ignore[call-arg]
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] %s failed: %s", label, day.isoformat(), exc)
            links = []

        # Same monthly archive already processed — keep walking day-by-day, no penalty.
        if links is None:
            logger.info(
                "[%s] %s: skip (same archive listing already fetched) (total %s/%s)",
                label,
                day.isoformat(),
                len(seen),
                limit,
            )
            day = step_back(day, unit="day")
            continue

        new = 0
        for url in links:
            canon = normalize_url(url)
            if not canon or canon in seen:
                continue
            seen[canon] = url.split("#")[0]
            new += 1
            if len(seen) >= limit:
                break

        logger.info(
            "[%s] %s: +%s unique (total %s/%s)",
            label,
            day.isoformat(),
            new,
            len(seen),
            limit,
        )

        if new == 0:
            empty_streak += 1
            if empty_streak >= empty_streak_max:
                logger.info("[%s] stopping after %s empty days", label, empty_streak)
                break
        else:
            empty_streak = 0

        day = step_back(day, unit="day")

    return list(seen.values())[:limit]
