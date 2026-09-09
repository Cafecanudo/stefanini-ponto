from playwright.sync_api import Page

import config


def is_login_screen(page: Page) -> bool:
    url = (page.url or "").lower()
    if any(marker in url for marker in config.LOGIN_URL_MARKERS):
        return True
    anchor = config.SELECTORS.get("login_anchor")
    if anchor and page.locator(anchor).count() > 0:
        return True
    return is_portal_landing(page)


def is_portal_landing(page: Page) -> bool:
    sso = config.SELECTORS.get("landing_sso_form")
    pwd = config.SELECTORS.get("landing_password_form")
    for selector in (sso, pwd):
        if not selector:
            continue
        if page.locator(selector).count() > 0:
            return True
    return False


def sso_button_visible(page: Page) -> bool:
    selector = config.SELECTORS.get("landing_sso_button")
    if not selector:
        return False
    locator = page.locator(selector)
    return locator.count() > 0 and locator.first.is_visible()
