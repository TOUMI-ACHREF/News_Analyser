"""Playwright helpers: browser context + automatic popup / cookie dismissal."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator

from config.settings import Settings, get_settings
from src.scrapers.exceptions import FetchError

logger = logging.getLogger(__name__)

BOT_MARKERS = (
    "client challenge",
    "access denied",
    "captcha",
    "automatis",
    "verify you are human",
    "attention required",
)

STEALTH_INIT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
"""

CONSENT_ROOT_SELECTORS = [
    "#didomi-host",
    "#didomi-notice",
    ".didomi-popup-container",
    "#onetrust-banner-sdk",
    "#onetrust-consent-sdk",
    ".fc-consent-root",
    "#sp_message_container_*, .sp_choice_type_11",
    "[id*='sp_message_container']",
    ".qc-cmp2-container",
    "#qc-cmp2-ui",
    ".poool-widget",
    "[class*='cookie-banner']",
    "[id*='cookie-banner']",
    "[class*='consent-banner']",
    "[id*='consent']",
]

POPUP_SELECTORS = [
    "#didomi-notice-agree-button",
    ".didomi-continue-without-agreeing",
    "button#didomi-notice-agree-button",
    "#onetrust-accept-btn-handler",
    ".onetrust-close-btn-handler",
    ".qc-cmp2-summary-buttons button",
    "button.sp_choice_type_11",
    "button[aria-label='Tout accepter']",
    "button[aria-label='Accepter et fermer']",
]

POPUP_BUTTON_TEXTS = [
    "Tout accepter",
    "Accepter et continuer",
    "Accepter tout",
    "Accepter et fermer",
    "J'accepte",
    "J’accepte",
    "Accept all",
    "Accept All",
    "I agree",
    "Agree and close",
    "Continuer sans accepter",
]


@contextmanager
def browser_page(
    settings: Settings | None = None,
    *,
    headed: bool | None = None,
) -> Iterator:
    """
    Yield a Playwright page with browser-like defaults.

    `headed=True` opens a visible Chromium window. Required for some sites
    (e.g. Le Point) that serve an empty shell to headless browsers.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise FetchError(
            "Playwright is not installed. Run: pip install playwright && playwright install chromium"
        ) from exc

    cfg = settings or get_settings()
    use_headed = cfg.scrape_headed if headed is None else headed

    playwright_cm = sync_playwright()
    playwright = playwright_cm.__enter__()
    browser = None
    context = None
    try:
        browser = playwright.chromium.launch(
            headless=not use_headed,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent=cfg.scrape_user_agent,
            locale="fr-FR",
            viewport={"width": 1365, "height": 900},
        )
        context.add_init_script(STEALTH_INIT_SCRIPT)
        page = context.new_page()
        page.set_default_timeout(min(cfg.scrape_timeout_seconds, 25) * 1000)
        yield page
    finally:
        for label, closer in (
            ("context", getattr(context, "close", None)),
            ("browser", getattr(browser, "close", None)),
        ):
            if closer is None:
                continue
            try:
                closer()
            except BaseException as exc:  # noqa: BLE001 — include KeyboardInterrupt
                logger.warning("Browser %s cleanup ignored: %s", label, exc)
        try:
            playwright_cm.__exit__(None, None, None)
        except BaseException as exc:  # noqa: BLE001
            logger.warning("Playwright stop ignored: %s", exc)


def dismiss_popups(page, *, rounds: int = 2) -> int:
    """Detect and dismiss cookie / consent banners only (CMP-scoped)."""
    clicked = 0

    for _ in range(rounds):
        round_hits = 0
        before_url = page.url

        for sel in POPUP_SELECTORS:
            try:
                loc = page.locator(sel)
                if loc.count() <= 0:
                    continue
                target = loc.first
                if not target.is_visible():
                    continue
                target.click(timeout=1200)
                clicked += 1
                round_hits += 1
                page.wait_for_timeout(300)
            except Exception:  # noqa: BLE001
                continue

        for root_sel in CONSENT_ROOT_SELECTORS:
            try:
                root = page.locator(root_sel)
                if root.count() <= 0:
                    continue
                for text in POPUP_BUTTON_TEXTS:
                    try:
                        btn = root.get_by_role("button", name=text, exact=False)
                        if btn.count() <= 0:
                            btn = root.locator(f"button:has-text('{text}'), a:has-text('{text}')")
                        if btn.count() <= 0:
                            continue
                        target = btn.first
                        if not target.is_visible():
                            continue
                        target.click(timeout=1200)
                        clicked += 1
                        round_hits += 1
                        page.wait_for_timeout(300)
                    except Exception:  # noqa: BLE001
                        continue
            except Exception:  # noqa: BLE001
                continue

        try:
            page.keyboard.press("Escape")
            page.wait_for_timeout(150)
        except Exception:  # noqa: BLE001
            pass

        try:
            if page.url.split("#")[0] != before_url.split("#")[0]:
                logger.warning(
                    "Popup dismiss changed URL (%s -> %s); going back",
                    before_url,
                    page.url,
                )
                page.go_back(wait_until="domcontentloaded")
                page.wait_for_timeout(500)
        except Exception:  # noqa: BLE001
            pass

        if round_hits == 0:
            break

    if clicked:
        logger.info("Dismissed %s popup/consent control(s)", clicked)
    return clicked


def fetch_with_cookies(page, url: str, *, timeout_ms: int = 20000) -> str:
    """
    Fast HTML fetch using the browser context cookies (no full navigation).

    Prefer this for article pages after the archive listing already warmed the session.
    """
    try:
        response = page.context.request.get(
            url,
            timeout=timeout_ms,
            headers={"Accept-Language": "fr-FR,fr;q=0.9"},
        )
    except Exception as exc:  # noqa: BLE001
        raise FetchError(f"Context request failed for {url}: {exc}") from exc

    if response.status >= 400:
        raise FetchError(f"HTTP {response.status} for {url}")

    html = response.text()
    sample = html[:1200].lower()
    if any(marker in sample for marker in BOT_MARKERS):
        raise FetchError(f"Bot/CAPTCHA challenge detected on {url}")
    return html


def open_url(
    page,
    url: str,
    *,
    wait_ms: int = 1500,
    dismiss: bool = True,
    timeout_ms: int = 25000,
) -> str:
    """
    Navigate to URL, optionally dismiss popups, return HTML.
    """
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
    except Exception as exc:  # noqa: BLE001
        raise FetchError(f"Playwright failed to open {url}: {exc}") from exc

    if dismiss:
        dismiss_popups(page, rounds=2)
        page.wait_for_timeout(wait_ms)
        dismiss_popups(page, rounds=1)
    else:
        page.wait_for_timeout(wait_ms)

    html = page.content()
    title = (page.title() or "").lower()
    sample = ""
    try:
        if page.query_selector("body"):
            sample = (page.inner_text("body") or "")[:800].lower()
    except Exception:  # noqa: BLE001
        sample = ""

    if any(marker in title or marker in sample for marker in BOT_MARKERS):
        raise FetchError(f"Bot/CAPTCHA challenge detected on {url}")
    return html


def goto(page, url: str, wait_ms: int = 1500) -> str:
    """Backward-compatible alias for open_url()."""
    return open_url(page, url, wait_ms=wait_ms, dismiss=True)


def looks_like_challenge(html: str, title: str = "") -> bool:
    blob = f"{title}\n{html[:2000]}".lower()
    return any(marker in blob for marker in BOT_MARKERS)
