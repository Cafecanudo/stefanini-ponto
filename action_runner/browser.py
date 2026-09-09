from contextlib import contextmanager
from typing import Iterator

from playwright.sync_api import BrowserContext, Page, sync_playwright

import config


def _launch_args() -> list[str]:
    args = ["--start-maximized"]
    if config.AUTH_SERVER_ALLOWLIST:
        args.append(f"--auth-server-allowlist={config.AUTH_SERVER_ALLOWLIST}")
        args.append(f"--auth-negotiate-delegate-allowlist={config.AUTH_SERVER_ALLOWLIST}")
    return args


@contextmanager
def persistent_chrome() -> Iterator[tuple[BrowserContext, Page]]:
    config.USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(
            user_data_dir=str(config.USER_DATA_DIR),
            channel=config.CHROME_CHANNEL,
            headless=config.HEADLESS,
            chromium_sandbox=True,
            no_viewport=True,
            args=_launch_args(),
        )
        context.set_default_timeout(config.ACTION_TIMEOUT_MS)
        context.set_default_navigation_timeout(config.NAV_TIMEOUT_MS)
        page = context.pages[0] if context.pages else context.new_page()
        try:
            yield context, page
        finally:
            context.close()
