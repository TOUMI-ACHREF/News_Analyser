"""Shared HTML title/body extraction helpers."""

from __future__ import annotations

from bs4 import BeautifulSoup, Tag

DEFAULT_TITLE_SELECTORS = [
    "h1",
    "meta[property='og:title']",
    "article h1",
]

DEFAULT_CONTENT_SELECTORS = [
    "[itemprop='articleBody']",
    ".article__content",
    ".article-content",
    ".article__body",
    ".entry-content",
    ".post-content",
    ".wysiwyg",
    ".article-body",
    "article",
    "main",
]

NOISE_SELECTORS = (
    "script, style, nav, aside, figure, figcaption, "
    ".share, .tags, .newsletter, .advertisement, .ad, "
    ".social, .related, .comments"
)


def extract_title(soup: BeautifulSoup, selectors: list[str] | None = None) -> str:
    for sel in selectors or DEFAULT_TITLE_SELECTORS:
        el = soup.select_one(sel)
        if not el:
            continue
        if el.name == "meta":
            text = (el.get("content") or "").strip()
        else:
            text = el.get_text(" ", strip=True)
        if text:
            return " ".join(text.split())
    return ""


def _paragraphs_from(node: Tag) -> str:
    clone = BeautifulSoup(str(node), "lxml")
    root = clone.body or clone
    for bad in root.select(NOISE_SELECTORS):
        bad.decompose()
    paras = [p.get_text(" ", strip=True) for p in root.find_all("p")]
    return "\n".join(p for p in paras if len(p) > 40)


def extract_content(
    soup: BeautifulSoup,
    selectors: list[str] | None = None,
    min_chars: int = 200,
) -> str:
    for sel in selectors or DEFAULT_CONTENT_SELECTORS:
        el = soup.select_one(sel)
        if not el:
            continue
        text = _paragraphs_from(el)
        if len(text) >= min_chars:
            return text

    # Last resort: all long paragraphs on the page
    paras = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
    text = "\n".join(p for p in paras if len(p) > 40)
    return text if len(text) >= min_chars else ""
