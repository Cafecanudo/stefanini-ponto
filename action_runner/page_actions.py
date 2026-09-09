from datetime import datetime
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


def wait_app_ready(page: Page) -> None:
    page.wait_for_selector(
        config.require_selector("app_ready"),
        state="attached",
        timeout=config.APP_READY_TIMEOUT_MS,
    )


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
