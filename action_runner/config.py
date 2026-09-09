import os
from pathlib import Path

BASE_DIR: Path = Path(__file__).resolve().parent
PROJECT_DIR: Path = BASE_DIR.parent


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} deve ser inteiro, recebido: {raw!r}") from exc


def _env_path(name: str, default: Path) -> Path:
    raw = os.environ.get(name)
    return Path(raw).expanduser().resolve() if raw else default


TARGET_URL: str = os.environ.get("TARGET_URL", "https://portalhoras.stefanini.com/")
APP_URL: str = os.environ.get("APP_URL", "https://portalhoras.stefanini.com/main.html")
CHROME_CHANNEL: str = os.environ.get("CHROME_CHANNEL", "chrome")
AUTH_SERVER_ALLOWLIST: str = os.environ.get("AUTH_SERVER_ALLOWLIST", "")

USER_DATA_DIR: Path = _env_path("USER_DATA_DIR", BASE_DIR / "chrome_profile")
LOCK_PATH: Path = _env_path("LOCK_PATH", BASE_DIR / "run.lock")
LOGS_DIR: Path = _env_path("LOGS_DIR", BASE_DIR / "logs")
TRACES_DIR: Path = _env_path("TRACES_DIR", BASE_DIR / "traces")
DUMP_DIR: Path = _env_path("DUMP_DIR", PROJECT_DIR / "_mapeamento")

HEADLESS: bool = _env_bool("HEADLESS", False)
WINDOW_WIDTH: int = _env_int("WINDOW_WIDTH", 1600)
WINDOW_HEIGHT: int = _env_int("WINDOW_HEIGHT", 1050)
WINDOW_X: int = _env_int("WINDOW_X", 0)
WINDOW_Y: int = _env_int("WINDOW_Y", 0)
DRY_RUN: bool = _env_bool("DRY_RUN", True)

NAV_TIMEOUT_MS: int = _env_int("NAV_TIMEOUT_MS", 60000)
ACTION_TIMEOUT_MS: int = _env_int("ACTION_TIMEOUT_MS", 15000)
SETTLE_TIMEOUT_MS: int = _env_int("SETTLE_TIMEOUT_MS", 20000)
APP_READY_TIMEOUT_MS: int = _env_int("APP_READY_TIMEOUT_MS", 90000)
POLL_INTERVAL_MS: int = _env_int("POLL_INTERVAL_MS", 250)

LOGIN_URL_MARKERS: tuple[str, ...] = (
    "login.microsoftonline.com",
    "login.live.com",
    "sts.stefanini.com",
    "adfs",
)

SELECTORS: dict[str, str | None] = {
    "page_anchor": None,
    "login_anchor": None,
    "record_present": None,
    "record_absent": None,
    "action_button": None,
    "post_click_anchor": None,
    "landing_sso_form": "form.singleSignOn",
    "landing_sso_button": "form.singleSignOn input.btOK",
    "landing_password_form": "form.fields",
    "lgpd_modal": ".x-window:visible",
    "lgpd_accept_button": ".x-window:visible a.btnPrimary[role=button]",
    "app_ready": "body:not(.x-masked)",
    "error_modal": ".x-window:visible",
    "session_expired_modal": ".x-window:visible:has-text('expirou')",
    "modal_ok_button": ".x-window:visible a[role=button]:has-text('Ok')",
    "sidebar_workarea": "a.sidebarButtons.workarea",
    "app_loading_mask": ".x-mask-msg.loading",
}


NAV_STEPS: list[tuple[str, str]] = [
    ("workarea", "sidebar_workarea"),
]


def require_selector(key: str) -> str:
    value = SELECTORS.get(key)
    if not value:
        raise RuntimeError(
            f"Seletor '{key}' nao mapeado. Fase 0 incompleta - preencha SELECTORS em config.py."
        )
    return value
