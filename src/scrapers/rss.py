"""RSS helpers used by site scrapers for stable article discovery."""

from __future__ import annotations

import re
from dataclasses import dataclass
from html import unescape

from bs4 import BeautifulSoup

from src.scrapers.exceptions import FetchError


@dataclass(slots=True)
class RssItem:
    title: str
    url: str
    summary: str = ""


def _strip_html(html: str) -> str:
    text = BeautifulSoup(html or "", "lxml").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", unescape(text)).strip()


def parse_rss_items(xml_text: str) -> list[RssItem]:
    """Parse RSS/Atom XML into normalized items."""
    soup = BeautifulSoup(xml_text, "lxml-xml")
    items: list[RssItem] = []

    for item in soup.find_all("item"):
        title = item.find("title").get_text(strip=True) if item.find("title") else ""
        link_el = item.find("link")
        url = (link_el.get_text(strip=True) if link_el else "") or ""
        if not url and item.find("guid"):
            url = item.find("guid").get_text(strip=True)

        summary = ""
        encoded = item.find(lambda t: t.name and str(t.name).endswith("encoded"))
        if encoded:
            summary = _strip_html(encoded.decode_contents())
        elif item.find("description"):
            summary = _strip_html(item.find("description").decode_contents())

        if url:
            items.append(RssItem(title=title, url=url.split("#")[0], summary=summary))

    for entry in soup.find_all("entry"):
        title = entry.find("title").get_text(strip=True) if entry.find("title") else ""
        link_el = entry.find("link")
        url = ""
        if link_el:
            url = link_el.get("href") or link_el.get_text(strip=True)
        summary = ""
        if entry.find("content"):
            summary = _strip_html(entry.find("content").decode_contents())
        elif entry.find("summary"):
            summary = _strip_html(entry.find("summary").decode_contents())
        if url:
            items.append(RssItem(title=title, url=url.split("#")[0], summary=summary))

    return items


def fetch_rss_items(scraper, feed_url: str) -> list[RssItem]:
    """Fetch and parse an RSS/Atom feed using the scraper's HTTP client."""
    try:
        response = scraper.client.get(
            feed_url,
            headers={"Accept": "application/rss+xml, application/xml, text/xml, */*"},
        )
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        raise FetchError(f"Failed to fetch RSS {feed_url}: {exc}") from exc

    items = parse_rss_items(response.text)
    if not items:
        raise FetchError(f"No items found in RSS feed: {feed_url}")
    return items
