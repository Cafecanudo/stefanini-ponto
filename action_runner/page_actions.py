import time
from datetime import datetime
from enum import Enum
from pathlib import Path

from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

import config


def goto_target(page: Page) -> None:
    page.goto(config.TARGET_URL, wait_until="domcontentloaded", timeout=config.NAV_TIMEOUT_MS)


def goto_app(page: Page) -> None:
    page.goto(config.APP_URL, wait_until="domcontentloaded", timeout=config.NAV_TIMEOUT_MS)


def settle(page: Page) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=config.SETTLE_TIMEOUT_MS)
    except PlaywrightTimeoutError:
        pass


class AppState(Enum):
    READY = "ready"
    SESSION_EXPIRED = "session_expired"
    TIMEOUT = "timeout"


def _visible(page: Page, selector_key: str) -> bool:
    selector = config.SELECTORS.get(selector_key)
    if not selector:
        return False
    try:
        return page.locator(selector).count() > 0
    except Exception:
        return False


def wait_app_ready(page: Page) -> AppState:
    ready = config.require_selector("app_ready")
    deadline = time.monotonic() + config.APP_READY_TIMEOUT_MS / 1000
    while time.monotonic() < deadline:
        if _visible(page, "session_expired_modal"):
            return AppState.SESSION_EXPIRED
        try:
            if page.locator(ready).count() > 0:
                return AppState.READY
        except Exception:
            pass
        page.wait_for_timeout(config.POLL_INTERVAL_MS)
    return AppState.TIMEOUT


def enter_app(page: Page) -> AppState:
    page.goto(config.TARGET_URL, wait_until="domcontentloaded", timeout=config.NAV_TIMEOUT_MS)
    settle(page)
    sso = config.SELECTORS.get("landing_sso_button")
    if sso and page.locator(sso).count() > 0:
        page.locator(sso).first.click()
        try:
            page.wait_for_url("**/main.html", timeout=config.NAV_TIMEOUT_MS)
        except PlaywrightTimeoutError:
            return AppState.SESSION_EXPIRED
        settle(page)
    return wait_app_ready(page)


def click_step(page: Page, selector: str) -> None:
    locator = page.locator(selector)
    locator.first.wait_for(state="visible", timeout=config.ACTION_TIMEOUT_MS)
    locator.first.click()


def is_alive(page: Page) -> bool:
    if page.is_closed():
        return False
    try:
        page.evaluate("1")
        return True
    except Exception:
        return False


def describe(page: Page) -> tuple[str, str]:
    if not is_alive(page):
        return ("<janela fechada>", "<janela fechada>")
    try:
        return (page.url, page.title())
    except Exception:
        return (page.url or "<indisponivel>", "<indisponivel>")


def dump_state(page: Page, name: str) -> tuple[Path, Path]:
    config.DUMP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%H%M%S")
    html_path = config.DUMP_DIR / f"{name}-{stamp}.html"
    png_path = config.DUMP_DIR / f"{name}-{stamp}.png"
    html_path.write_text(page.content(), encoding="utf-8")
    page.screenshot(path=str(png_path), full_page=False)
    return html_path, png_path
