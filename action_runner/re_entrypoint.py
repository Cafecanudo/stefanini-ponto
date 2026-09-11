import argparse
import os
import re
import time
import sys
from datetime import datetime, timedelta
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).resolve().parent
USER_DATA_DIR = BASE_DIR / "chrome_profile"
LOGS_DIR = BASE_DIR / "logs"
EVIDENCE_DIR = BASE_DIR / "evidencias"
EVIDENCE_NAME_FORMAT = "%d-%m-%Y %H.%M.%S"
EVIDENCE_QUALITY = 80
LOG_NAME_FORMAT = "%d-%m-%Y %H.%M.%S"
LOG_LINE_FORMAT = "%H:%M:%S"
TARGET_URL = "https://portalhoras.stefanini.com/"

NAV_TIMEOUT_MS = 60000
HTTP_ERROR_STATUS = 400
ACTION_TIMEOUT_MS = 15000
WAIT_LOGIN_WINDOW_MS = 8000
MFA_TIMEOUT_MS = 60000
POLL_INTERVAL_MS = 500
CLICK_DELAY_MS = 800
APP_READY_TIMEOUT_MS = 60000

CONSENT_BUTTON = "text=Confirmar preferências"
ENTER_PORTAL_BUTTON = 'input.btOK[lang="btLoginEntrar"]'
LOGIN_EMAIL_PLACEHOLDER = "Email, telefone ou Skype"
LOGIN_EMAIL_INPUT = (
    'input[name="loginfmt"], '
    f'input[placeholder="{LOGIN_EMAIL_PLACEHOLDER}"]'
)
LOGIN_PASSWORD_INPUT = 'input[type="password"][name="passwd"]'
LOGIN_SUBMIT = 'input[type="submit"]'
LOGIN_USER_ENV = "USER_STEFANINI"
LOGIN_USER = os.environ.get(LOGIN_USER_ENV, "")
LOGIN_PASSWORD_ENV = "PASS_STEFANINI"
LOGIN_PASSWORD = os.environ.get(LOGIN_PASSWORD_ENV, "")
ACCOUNT_TILE = (
    f'[data-test-id="{LOGIN_USER}"], '
    f'#tileList [role="button"]:has-text("{LOGIN_USER}")'
)
APP_URL_PATTERN = "**/main.html"
APP_URL_MARK = "main.html"
MFA_RETRY_METHOD = (
    '#idDiv_SAOTCS_Proofs [role="button"][data-value="PhoneAppNotification"], '
    '[role="button"]:has-text("Microsoft Authenticator")'
)
MFA_RETRY_LIMIT = 3
KMSI_CHECKBOX = 'input[name="DontShowAgain"], #KmsiCheckboxField'
KMSI_YES_BUTTON = 'input[type="submit"]#idSIButton9, input[type="submit"][value="Sim"]'
WORKAREA_BUTTON = "a.sidebarButtons.workarea"
DAILY_ENTRY_BUTTON = "text=Apontamento Diário"
GRID_ROW = "tr.x-grid-row"
GRID_ROW_DATE_CELL = "td"
GRID_ROW_CHECKBOX = "div.x-grid-row-checker"
CALC_BUTTON_ICON = "img201.png"
CALC_BUTTON = f'a.toolbar-footer-button:has(span[style*="{CALC_BUTTON_ICON}"])'
DIALOG_OK_BUTTON = (
    '.x-message-box:visible '
    'a[role="button"]:has(span.x-btn-inner:text-is("Ok"))'
)
WINDOW_CLOSE_BUTTON = (
    '.x-window:not(.x-message-box):visible '
    'div.x-tool[aria-label="Close panel"]'
)
HOME_BUTTON = "button.headerButtons.homeButton"
CLOCK_BUTTON = "text=Relógio de Ponto Virtual"
PUNCH_BUTTON = "text=Efetuar Marcação"
PUNCH_CONFIRMATION = "text=MARCACAO EFETUADA"
PUNCH_SETTLE_MS = 5000

OK_NOOP = 1
SANITY_FAILED = 20
UNEXPECTED_ERROR = 40
INTERRUPTED = 130

MARK_PATTERN = re.compile(r"\b\d{2}:\d{2}\b")
EXPECTED_WINDOWS = {
    1: ("08:45", "09:15"),
    2: ("12:45", "13:15"),
    3: ("13:45", "14:15"),
    4: ("17:45", "18:15"),
}


def wait_for_login_state(page) -> str:
    alvos = [
        ("email", LOGIN_EMAIL_INPUT),
        ("password", LOGIN_PASSWORD_INPUT),
    ]
    if LOGIN_USER:
        alvos.insert(0, ("tile", ACCOUNT_TILE))
    deadline = time.monotonic() + WAIT_LOGIN_WINDOW_MS / 1000
    while True:
        if APP_URL_MARK in page.url:
            return "portal"
        for nome, seletor in alvos:
            try:
                visivel = page.locator(seletor).first.is_visible()
            except PlaywrightError:
                visivel = False
            if visivel:
                return nome
        if time.monotonic() >= deadline:
            return "nenhum"
        page.wait_for_timeout(POLL_INTERVAL_MS)


def wait_for_kmsi_or_portal(page) -> str:
    deadline = time.monotonic() + MFA_TIMEOUT_MS / 1000
    kmsi = page.locator(KMSI_CHECKBOX).first
    retry = page.locator(MFA_RETRY_METHOD).first
    tentativas = 0
    while time.monotonic() < deadline:
        if APP_URL_MARK in page.url:
            return "portal"
        try:
            kmsi_visivel = kmsi.is_visible()
            retry_visivel = retry.is_visible()
        except PlaywrightError:
            kmsi_visivel = False
            retry_visivel = False
        if kmsi_visivel:
            return "kmsi"
        if retry_visivel:
            if tentativas >= MFA_RETRY_LIMIT:
                return "mfa_falhou"
            tentativas += 1
            log(f"MFA nao verificado - reenviando ({tentativas}/{MFA_RETRY_LIMIT})")
            retry.click(timeout=ACTION_TIMEOUT_MS)
            page.wait_for_timeout(CLICK_DELAY_MS)
            continue
        page.wait_for_timeout(POLL_INTERVAL_MS)
    return "timeout"


LOG_HANDLE = None


def setup_log() -> Path:
    global LOG_HANDLE
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    caminho = LOGS_DIR / (datetime.now().strftime(LOG_NAME_FORMAT) + ".log")
    LOG_HANDLE = caminho.open("a", encoding="utf-8")
    return caminho


def close_log() -> None:
    global LOG_HANDLE
    if LOG_HANDLE is not None:
        LOG_HANDLE.close()
        LOG_HANDLE = None


def log(mensagem: str) -> None:
    linha = f"{datetime.now().strftime(LOG_LINE_FORMAT)} {mensagem}"
    print(linha)
    if LOG_HANDLE is not None:
        print(linha, file=LOG_HANDLE, flush=True)


def save_evidence(page, situacao: str) -> None:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    nome = f"{datetime.now().strftime(EVIDENCE_NAME_FORMAT)}-{situacao}.jpg"
    caminho = EVIDENCE_DIR / nome
    try:
        page.screenshot(
            path=str(caminho),
            type="jpeg",
            quality=EVIDENCE_QUALITY,
            full_page=True,
        )
    except PlaywrightError as exc:
        log(f"falha ao salvar evidencia {nome}: {exc}")
        return
    log(f"evidencia: {caminho}")


def response_status(resposta) -> int | None:
    return resposta.status if resposta is not None else None


def open_target(page) -> bool:
    resposta = page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
    status = response_status(resposta)
    if status is None or status < HTTP_ERROR_STATUS:
        log(f"aberto: {page.url}")
        return True

    log(f"portal indisponivel - HTTP {status} - tentando refresh")
    page.wait_for_timeout(CLICK_DELAY_MS)
    resposta = page.reload(wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
    status = response_status(resposta)
    if status is None or status < HTTP_ERROR_STATUS:
        log(f"portal respondeu apos o refresh: {page.url}")
        return True

    log(f"portal segue indisponivel apos o refresh - HTTP {status}")
    save_evidence(page, "erro-portal-indisponivel")
    return False


def missing_env_vars() -> list[str]:
    faltando = []
    if not LOGIN_USER:
        faltando.append(LOGIN_USER_ENV)
    if not LOGIN_PASSWORD:
        faltando.append(LOGIN_PASSWORD_ENV)
    return faltando


def parse_date(value: str) -> datetime:
    texto = value.strip()
    try:
        return datetime.strptime(texto, "%d/%m/%Y")
    except ValueError:
        pass
    try:
        return datetime.strptime(f"{texto}/{datetime.now().year}", "%d/%m/%Y")
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"data invalida: {value!r}, use dd/mm ou dd/mm/aaaa"
        ) from None


def window_center(inicio: str, fim: str) -> str:
    meio = (to_minutes(inicio) + to_minutes(fim)) // 2
    return f"{meio // 60:02d}:{meio % 60:02d}"


def plan_fill(marks: list[str], faltantes: list[tuple[str, str]]) -> list[tuple[int, str]]:
    plano = []
    proxima = len(marks)
    for inicio, fim in faltantes:
        plano.append((proxima, window_center(inicio, fim)))
        proxima += 1
    return plano


def previous_business_day(referencia: datetime) -> datetime:
    dia = referencia - timedelta(days=1)
    while dia.weekday() >= 5:
        dia -= timedelta(days=1)
    return dia


def join_pt(itens: list[str]) -> str:
    if len(itens) <= 1:
        return "".join(itens)
    return f"{', '.join(itens[:-1])} e {itens[-1]}"


def to_minutes(value: str) -> int:
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


def parse_hhmm(value: str) -> str:
    partes = value.split(":")
    if len(partes) != 2 or not all(x.isdigit() and len(x) == 2 for x in partes):
        raise argparse.ArgumentTypeError(f"horario invalido: {value!r}, esperado HH:MM")
    if int(partes[0]) > 23 or int(partes[1]) > 59:
        raise argparse.ArgumentTypeError(f"horario fora da faixa: {value!r}")
    return value


def format_windows(janelas: dict[int, tuple[str, str]]) -> str:
    return ",".join(f"{k}={v[0]}-{v[1]}" for k, v in sorted(janelas.items()))


def parse_windows(texto: str) -> dict[int, tuple[str, str]]:
    janelas: dict[int, tuple[str, str]] = {}
    for item in texto.split(","):
        item = item.strip()
        if not item:
            continue
        chave, sep, faixa = item.partition("=")
        if not sep:
            raise argparse.ArgumentTypeError(f"item sem '=': {item!r}")
        if not chave.strip().isdigit():
            raise argparse.ArgumentTypeError(f"indice invalido: {chave!r}")
        inicio, sep, fim = faixa.partition("-")
        if not sep:
            raise argparse.ArgumentTypeError(f"faixa sem '-': {faixa!r}")
        inicio = parse_hhmm(inicio.strip())
        fim = parse_hhmm(fim.strip())
        if to_minutes(inicio) > to_minutes(fim):
            raise argparse.ArgumentTypeError(f"inicio depois do fim: {item!r}")
        janelas[int(chave.strip())] = (inicio, fim)
    if not janelas:
        raise argparse.ArgumentTypeError("nenhuma janela informada")
    return janelas


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="re_entrypoint")
    parser.add_argument(
        "--show",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "--date",
        dest="date",
        type=parse_date,
        default=None,
        metavar="dd/mm[/aaaa]",
    )
    parser.add_argument(
        "--exp-windows",
        "--exp_windows",
        dest="exp_windows",
        type=parse_windows,
        default=EXPECTED_WINDOWS,
        metavar="N=HH:MM-HH:MM,...",
        help=f"padrao: {format_windows(EXPECTED_WINDOWS)}",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    caminho_log = setup_log()
    log(f"log em {caminho_log}")
    faltando = missing_env_vars()
    if faltando:
        log(f"variaveis de ambiente nao configuradas: {', '.join(faltando)}")
    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    modo = "visivel" if args.show else "headless"
    log(f"chrome {modo}")
    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(
            user_data_dir=str(USER_DATA_DIR),
            channel="chrome",
            headless=not args.show,
            no_viewport=True,
            args=["--start-maximized"],
        )
        page = None
        try:
            page = context.pages[0] if context.pages else context.new_page()
            open_target(page)
            consent = page.locator(CONSENT_BUTTON).first
            try:
                consent.wait_for(state="visible", timeout=ACTION_TIMEOUT_MS)
            except PlaywrightTimeoutError:
                log("banner de preferencias nao apareceu")
            else:
                consent.click()
                log("preferencias confirmadas")
                page.wait_for_timeout(CLICK_DELAY_MS)
            enter_portal = page.locator(ENTER_PORTAL_BUTTON).first
            try:
                enter_portal.wait_for(state="visible", timeout=ACTION_TIMEOUT_MS)
            except PlaywrightTimeoutError:
                log("botao Entrar no Portal nao encontrado")
                save_evidence(page, "erro-entrar-portal")
            else:
                enter_portal.click()
                log(f"entrou no portal: {page.url}")
                page.wait_for_timeout(CLICK_DELAY_MS)
            estado_login = wait_for_login_state(page)
            log(f"estado apos entrar no portal: {estado_login}")
            if estado_login == "tile":
                page.locator(ACCOUNT_TILE).first.click(timeout=ACTION_TIMEOUT_MS)
                log(f"conta selecionada: {LOGIN_USER}")
                page.wait_for_timeout(CLICK_DELAY_MS)
                estado_login = "password"
            if estado_login == "email" and not LOGIN_USER:
                log(f"{LOGIN_USER_ENV} nao definida - usuario nao informado")
                estado_login = "sem_usuario"
            if estado_login == "email":
                login_email = page.locator(LOGIN_EMAIL_INPUT).first
                try:
                    login_email.wait_for(state="visible", timeout=ACTION_TIMEOUT_MS)
                except PlaywrightTimeoutError:
                    log("campo de email nao apareceu")
                    save_evidence(page, "erro-campo-email")
                else:
                    login_email.fill(LOGIN_USER)
                    if login_email.input_value() != LOGIN_USER:
                        login_email.fill("")
                        login_email.click(timeout=ACTION_TIMEOUT_MS)
                        login_email.press_sequentially(LOGIN_USER, delay=50)
                    log(f"usuario informado: {login_email.input_value()}")
                    page.locator(LOGIN_SUBMIT).first.click(timeout=ACTION_TIMEOUT_MS)
                    page.wait_for_timeout(3000)
                    estado_login = "password"
            if estado_login in ("nenhum", "sem_usuario", "sem_senha"):
                log(f"autenticacao impossivel - estado: {estado_login}")
                save_evidence(page, "erro-login")
                return SANITY_FAILED
            if estado_login == "password" and not LOGIN_PASSWORD:
                log(f"{LOGIN_PASSWORD_ENV} nao definida - senha nao informada")
                estado_login = "sem_senha"
            if estado_login == "password":
                login_password = page.locator(LOGIN_PASSWORD_INPUT).first
                try:
                    login_password.wait_for(state="visible", timeout=ACTION_TIMEOUT_MS)
                except PlaywrightTimeoutError:
                    log("campo de senha nao apareceu")
                    save_evidence(page, "erro-campo-senha")
                else:
                    login_password.fill(LOGIN_PASSWORD)
                    page.locator(LOGIN_SUBMIT).first.click(timeout=ACTION_TIMEOUT_MS)
                    page.wait_for_timeout(CLICK_DELAY_MS)
                    espera = MFA_TIMEOUT_MS // 1000
                    log(f"aguardando confirmacao manual do MFA (ate {espera}s)")
                    estado = wait_for_kmsi_or_portal(page)
                    if estado == "timeout":
                        log("MFA nao confirmado dentro do prazo")
                        save_evidence(page, "erro-mfa-timeout")
                    elif estado == "mfa_falhou":
                        log(f"MFA falhou apos {MFA_RETRY_LIMIT} reenvios")
                        save_evidence(page, "erro-mfa-reenvios")
                    elif estado == "portal":
                        log(f"MFA confirmado - ja no portal: {page.url}")
                    else:
                        log("MFA confirmado - tela Continuar conectado")
                        page.locator(KMSI_CHECKBOX).first.check(timeout=ACTION_TIMEOUT_MS)
                        log("marcado: nao mostrar isso novamente")
                        page.wait_for_timeout(CLICK_DELAY_MS)
                        page.locator(KMSI_YES_BUTTON).first.click(timeout=ACTION_TIMEOUT_MS)
                        log("continuar conectado: Sim")
                        page.wait_for_timeout(CLICK_DELAY_MS)
                        try:
                            page.wait_for_url(APP_URL_PATTERN, timeout=NAV_TIMEOUT_MS)
                        except PlaywrightTimeoutError:
                            log("nao voltou ao portal apos Continuar conectado")
                            save_evidence(page, "erro-kmsi")
                        else:
                            log(f"de volta no portal: {page.url}")
            workarea = page.locator(WORKAREA_BUTTON).first
            try:
                workarea.wait_for(state="visible", timeout=APP_READY_TIMEOUT_MS)
            except PlaywrightTimeoutError:
                log("app nao carregou ou botao WorkArea nao encontrado")
                save_evidence(page, "erro-workarea")
                return SANITY_FAILED
            else:
                workarea.click(timeout=ACTION_TIMEOUT_MS)
                log("workarea aberta")
                page.wait_for_timeout(CLICK_DELAY_MS)
            daily_entry = page.locator(DAILY_ENTRY_BUTTON).first
            try:
                daily_entry.wait_for(state="visible", timeout=ACTION_TIMEOUT_MS)
            except PlaywrightTimeoutError:
                log("Apontamento Diario nao encontrado")
                save_evidence(page, "erro-apontamento-diario")
            else:
                daily_entry.click(timeout=ACTION_TIMEOUT_MS)
                log("apontamento diario aberto")
                page.wait_for_timeout(CLICK_DELAY_MS)
            alvo = args.date or previous_business_day(datetime.now())
            dia = alvo.strftime("%d/%m")
            log(f"verificando {dia} ({alvo.strftime('%A')})")
            dia_row = page.locator(GRID_ROW).filter(
                has=page.locator(GRID_ROW_DATE_CELL, has_text=re.compile(rf"^{dia}\s"))
            ).first
            try:
                dia_row.wait_for(state="visible", timeout=ACTION_TIMEOUT_MS)
            except PlaywrightTimeoutError:
                log(f"linha de {dia} nao encontrada na grid")
                save_evidence(page, "erro-linha-do-dia")
            else:
                marks = MARK_PATTERN.findall(dia_row.inner_text())
                log(f"marcacoes de {dia}: {marks or 'nenhuma'}")
                faltantes = []
                for indice in sorted(args.exp_windows):
                    inicio, fim_janela = args.exp_windows[indice]
                    presente = any(
                        to_minutes(inicio) <= to_minutes(marca) <= to_minutes(fim_janela)
                        for marca in marks
                    )
                    if not presente:
                        faltantes.append((inicio, fim_janela))
                if faltantes:
                    rotulos = [f"{ini}-{fim_j}" for ini, fim_j in faltantes]
                    log(f"Falta apontamentos: [{join_pt(rotulos)}]")
                    for posicao, valor in plan_fill(marks, faltantes):
                        log(f"preenchimento planejado: celula {posicao + 1} <- {valor}")
                else:
                    log(f"dia {dia} completo: {len(args.exp_windows)} apontamentos")

            
                

            input("Continuar")
        except Exception as exc:
            detalhe = str(exc).splitlines()[0] if str(exc) else ""
            log(f"erro nao previsto: {exc.__class__.__name__}: {detalhe}")
            if page is not None:
                save_evidence(page, "erro-inesperado")
            return UNEXPECTED_ERROR
        finally:
            try:
                context.close()
            except PlaywrightError as exc:
                log(f"falha ao fechar o contexto: {exc}")
            close_log()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log("interrompido pelo usuario")
        sys.exit(INTERRUPTED)
    except Exception as exc:
        detalhe = str(exc).splitlines()[0] if str(exc) else ""
        log(f"erro nao previsto: {exc.__class__.__name__}: {detalhe}")
        sys.exit(UNEXPECTED_ERROR)
