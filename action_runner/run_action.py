import argparse
import logging
import sys
from datetime import datetime

import config
import guards
import page_actions
from browser import persistent_chrome
from exit_codes import ExitCode


def _setup_logging() -> logging.Logger:
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    logger = logging.getLogger("action_runner")
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%Y-%m-%d %H:%M:%S")

    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(fmt)
    logger.addHandler(stream)

    file_handler = logging.FileHandler(config.LOGS_DIR / f"run-{stamp}.log", encoding="utf-8")
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)
    return logger


def cmd_login(log: logging.Logger) -> ExitCode:
    with persistent_chrome() as (_, page):
        log.info("profile: %s", config.USER_DATA_DIR)
        log.info("navegando para %s", config.TARGET_URL)
        page_actions.goto_target(page)
        print("")
        print("=" * 70)
        print(" 1. Se aparecer aviso de cookies/LGPD, aceite.")
        print(" 2. Clique em 'Entrar no portal'.")
        print(" 3. Complete o login Microsoft (Entra ID) e o MFA.")
        print(" 4. Se perguntar 'Continuar conectado?' / 'Stay signed in?',")
        print("    responda SIM: e isso que grava o cookie persistente.")
        print(" 5. So pressione ENTER aqui QUANDO o portal ja estiver carregado.")
        print("=" * 70)
        print("")
        input(" ENTER para finalizar > ")
        if not page_actions.is_alive(page):
            log.error("janela do Chrome foi fechada antes do ENTER")
            log.error("a sessao pode ter sido gravada mesmo assim - rode 'check' para validar")
            return ExitCode.UNEXPECTED_ERROR
        page_actions.settle(page)
        url, title = page_actions.describe(page)
        log.info("url final: %s", url)
        log.info("titulo: %s", title)
        if guards.is_login_screen(page):
            log.warning("ainda em tela de login - sessao NAO gravada")
            return ExitCode.SESSION_EXPIRED
        log.info("sessao gravada em %s", config.USER_DATA_DIR)
        return ExitCode.OK_NOOP


def cmd_check(log: logging.Logger, dump_name: str | None) -> ExitCode:
    with persistent_chrome() as (_, page):
        log.info("profile: %s", config.USER_DATA_DIR)
        log.info("alvo: %s", config.APP_URL)
        page_actions.goto_app(page)
        page_actions.settle(page)
        url, title = page_actions.describe(page)
        log.info("url: %s", url)
        log.info("titulo: %s", title)

        log.info("landing detectada: %s", guards.is_portal_landing(page))
        log.info("botao SSO visivel: %s", guards.sso_button_visible(page))

        if guards.is_login_screen(page):
            log.error("nao autenticado - landing/login detectado")
            if dump_name:
                html, png = page_actions.dump_state(page, dump_name)
                log.info("dump: %s | %s", html, png)
            return ExitCode.SESSION_EXPIRED

        log.info("sessao valida")
        if dump_name:
            html, png = page_actions.dump_state(page, dump_name)
            log.info("dump: %s | %s", html, png)
        return ExitCode.OK_NOOP


def cmd_dump(log: logging.Logger, dump_name: str) -> ExitCode:
    with persistent_chrome() as (_, page):
        page_actions.goto_app(page)
        page_actions.settle(page)
        log.info("url: %s", page.url)
        print("")
        print("=" * 70)
        print(" Navegue ate o estado que voce quer capturar.")
        print(f" Pressione ENTER para salvar o DOM como '{dump_name}'.")
        print("=" * 70)
        print("")
        input(" ENTER para capturar > ")
        if not page_actions.is_alive(page):
            log.error("janela do Chrome foi fechada antes do ENTER - nada capturado")
            return ExitCode.UNEXPECTED_ERROR
        html, png = page_actions.dump_state(page, dump_name)
        log.info("dump: %s", html)
        log.info("shot: %s", png)
        return ExitCode.OK_NOOP


def main() -> int:
    parser = argparse.ArgumentParser(prog="run_action")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("login", help="abre o Chrome persistente para login manual unico")
    check = sub.add_parser("check", help="valida se a sessao persistida ainda esta ativa")
    check.add_argument("--dump", dest="dump", default=None, metavar="NOME")
    dump = sub.add_parser("dump", help="captura DOM e screenshot do estado atual")
    dump.add_argument("nome", help="nome do arquivo em _mapeamento")

    args = parser.parse_args()
    log = _setup_logging()

    try:
        if args.command == "login":
            code = cmd_login(log)
        elif args.command == "check":
            code = cmd_check(log, args.dump)
        else:
            code = cmd_dump(log, args.nome)
    except KeyboardInterrupt:
        log.warning("interrompido pelo usuario")
        code = ExitCode.UNEXPECTED_ERROR
    except Exception:
        log.exception("erro nao previsto")
        code = ExitCode.UNEXPECTED_ERROR

    log.info("exit %d (%s)", code.value, code.name)
    return int(code)


if __name__ == "__main__":
    sys.exit(main())
