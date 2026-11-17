"""Dated archive listing URLs."""

from __future__ import annotations

from datetime import date, datetime, timedelta

_MONTHS_FR = {
    1: "janvier",
    2: "fevrier",
    3: "mars",
    4: "avril",
    5: "mai",
    6: "juin",
    7: "juillet",
    8: "aout",
    9: "septembre",
    10: "octobre",
    11: "novembre",
    12: "decembre",
}


def as_date(value: date | datetime | str | None = None) -> date:
    if value is None:
        return date.today()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value), "%Y-%m-%d").date()


def step_back(day: date, *, unit: str = "day") -> date:
    if unit == "month":
        first = day.replace(day=1)
        return first - timedelta(days=1)
    return day - timedelta(days=1)


def humanite_archive_url(day: date | datetime | str | None = None) -> str:
    d = as_date(day)
    return f"https://www.humanite.fr/toutes-les-archives/{d.strftime('%Y')}/{d.strftime('%d-%m-%Y')}"


def marianne_archive_url(day: date | datetime | str | None = None) -> str:
    d = as_date(day)
    return f"https://www.marianne.net/archives/{d.strftime('%Y')}/{d.strftime('%m')}/{d.strftime('%d')}"


def france3_archive_url(day: date | datetime | str | None = None) -> str:
    d = as_date(day)
    return (
        f"https://france3-regions.franceinfo.fr/archives/"
        f"{d.strftime('%Y')}/{d.strftime('%d')}-{_MONTHS_FR[d.month]}-{d.strftime('%Y')}"
    )


def lemonde_archive_url(day: date | datetime | str | None = None) -> str:
    d = as_date(day)
    return f"https://www.lemonde.fr/archives-du-monde/{d.strftime('%d-%m-%Y')}/"


def lepoint_archive_url(day: date | datetime | str | None = None) -> str:
    d = as_date(day)
    return f"https://www.lepoint.fr/archives/{d.strftime('%m-%Y')}/{d.strftime('%d')}.php"


def france24_archive_url(day: date | datetime | str | None = None) -> str:
    d = as_date(day)
    return f"https://www.france24.com/fr/archives/{d.strftime('%Y')}/{d.strftime('%m')}/"
