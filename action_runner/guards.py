from playwright.sync_api import Page

import config


def is_login_screen(page: Page) -> bool:
    url = (page.url or "").lower()
    if any(marker in url for marker in config.LOGIN_URL_MARKERS):
        return True
    anchor = config.SELECTORS.get("login_anchor")
    if not anchor:
        return False
    return page.locator(anchor).count() > 0
