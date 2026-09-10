import json
import random
import sys
import time
from datetime import date, datetime, time as clock, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
STATE_FILE = BASE_DIR / "scheduler_state.json"

#BASE_TIMES = ("09:00", "13:00", "14:00", "18:00")
BASE_TIMES = ("21:56", "21:57", "21:58", "21:59")
#JITTER_MINUTES = 15
JITTER_MINUTES = 1
MAX_SLEEP_S = 60
MAX_WORK = timedelta(hours=8, minutes=15)

DATE_FORMAT = "%d-%m-%Y"
TIME_FORMAT = "%H:%M:%S"

INTERRUPTED = 130


def log(mensagem: str) -> None:
    print(f"{datetime.now().strftime(TIME_FORMAT)} {mensagem}")


def load_raw() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        log(f"estado ilegivel ({exc}) - recomecando")
        return {}


def save_state(dia: date, execucoes: dict[str, str], anterior: dict) -> None:
    conteudo = {
        "data": dia.strftime(DATE_FORMAT),
        "esperado": list(BASE_TIMES),
        "execucoes": execucoes,
        "anterior": anterior,
    }
    STATE_FILE.write_text(
        json.dumps(conteudo, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def missing_executions(registro: dict) -> list[str]:
    esperado = registro.get("esperado") or list(BASE_TIMES)
    feitas = registro.get("execucoes", {})
    return [base for base in esperado if base not in feitas]


def report_previous_day(anterior: dict) -> None:
    if not anterior or not anterior.get("data"):
        return
    dia = anterior["data"]
    faltando = missing_executions(anterior)
    feitas = anterior.get("execucoes", {})
    if faltando:
        log(f"ATENCAO: dia {dia} incompleto - faltaram {len(faltando)}: {', '.join(faltando)}")
    else:
        log(f"dia {dia} completo: {len(feitas)} execucoes")


def last_execution(dia: date, execucoes: dict[str, str]) -> datetime | None:
    momentos = []
    for texto in execucoes.values():
        try:
            hora, minuto, segundo = (int(parte) for parte in texto.split(":"))
        except ValueError:
            log(f"execucao registrada em formato invalido: {texto!r} - ignorada")
            continue
        momentos.append(datetime.combine(dia, clock(hora, minuto, segundo)))
    return max(momentos) if momentos else None


def target_datetime(dia: date, texto: str) -> datetime:
    hora, minuto = (int(parte) for parte in texto.split(":"))
    return datetime.combine(dia, clock(hora, minuto))


def parse_execution(dia: date, texto: str) -> datetime | None:
    try:
        hora, minuto, segundo = (int(parte) for parte in texto.split(":"))
    except ValueError:
        log(f"execucao registrada em formato invalido: {texto!r} - ignorada")
        return None
    return datetime.combine(dia, clock(hora, minuto, segundo))


def worked_before(bases: list[str], conhecidos: dict[str, datetime], indice: int) -> timedelta:
    total = timedelta()
    for par in range(0, min(indice - 1, len(bases) - 1), 2):
        entrada = conhecidos.get(bases[par])
        saida = conhecidos.get(bases[par + 1])
        if entrada is not None and saida is not None:
            total += saida - entrada
    return total


def build_schedule(
    dia: date, agora: datetime, execucoes: dict[str, str]
) -> list[tuple[str, datetime]]:
    bases = sorted(BASE_TIMES)
    conhecidos: dict[str, datetime] = {}
    for base, texto in execucoes.items():
        momento = parse_execution(dia, texto)
        if momento is not None:
            conhecidos[base] = momento

    piso = agora
    if conhecidos:
        ultima = max(conhecidos.values())
        if ultima > piso:
            piso = ultima

    agenda = []
    for indice, texto in enumerate(bases):
        if texto in execucoes:
            continue
        alvo = target_datetime(dia, texto)
        inicio = max(alvo - timedelta(minutes=JITTER_MINUTES), piso + timedelta(seconds=1))
        limite = alvo + timedelta(minutes=JITTER_MINUTES)

        if indice % 2 == 1:
            entrada = conhecidos.get(bases[indice - 1])
            if entrada is not None:
                restante = MAX_WORK - worked_before(bases, conhecidos, indice)
                teto = entrada + restante
                if teto < limite:
                    log(f"slot {texto}: teto de {MAX_WORK} limita a saida a {teto.strftime(TIME_FORMAT)}")
                    limite = teto

        if inicio > limite:
            log(f"slot {texto} descartado: nenhum horario possivel dentro da tolerancia")
            continue

        momento = inicio + timedelta(seconds=random.randint(0, int((limite - inicio).total_seconds())))
        conhecidos[texto] = momento
        agenda.append((texto, momento))
        piso = momento

    total = worked_before(bases, conhecidos, len(bases) + 1)
    log(f"jornada projetada: {total} (teto {MAX_WORK})")
    return agenda


def main() -> int:
    dia_atual = None
    pendentes: list[tuple[str, datetime]] = []
    execucoes: dict[str, str] = {}
    anterior: dict = {}
    encerrado = False

    while True:
        agora = datetime.now()

        if dia_atual != agora.date():
            dia_atual = agora.date()
            hoje = dia_atual.strftime(DATE_FORMAT)
            bruto = load_raw()
            if bruto.get("data") == hoje:
                execucoes = bruto.get("execucoes", {})
                anterior = bruto.get("anterior", {})
            else:
                anterior = bruto if bruto.get("data") else bruto.get("anterior", {})
                anterior.pop("anterior", None)
                execucoes = {}
            report_previous_day(anterior)
            save_state(dia_atual, execucoes, anterior)
            pendentes = build_schedule(dia_atual, agora, execucoes)
            encerrado = False
            if execucoes:
                feitas = ", ".join(f"{base} as {hora}" for base, hora in sorted(execucoes.items()))
                log(f"ja executado hoje: {feitas}")
            planejado = ", ".join(f"{base}->{m.strftime(TIME_FORMAT)}" for base, m in pendentes)
            log(f"agenda de {hoje}: {planejado or 'nada pendente'}")

        while pendentes and pendentes[0][1] <= agora:
            base, previsto = pendentes.pop(0)
            tolerancia = target_datetime(dia_atual, base) + timedelta(minutes=JITTER_MINUTES)
            if agora > tolerancia:
                log(
                    f"slot {base} fora da tolerancia (limite {tolerancia.strftime(TIME_FORMAT)}, "
                    f"agora {agora.strftime(TIME_FORMAT)}) - nao registrado"
                )
                continue
            log(f"disparo de {base} previsto para {previsto.strftime(TIME_FORMAT)}")
            print("Execute")
            execucoes[base] = datetime.now().strftime(TIME_FORMAT)
            save_state(dia_atual, execucoes, anterior)
            log(f"registrado: {base} executado as {execucoes[base]}")

        if pendentes:
            espera = (pendentes[0][1] - datetime.now()).total_seconds()
        else:
            amanha = datetime.combine(dia_atual + timedelta(days=1), clock(0, 0))
            if not encerrado:
                encerrado = True
                registro = {"esperado": list(BASE_TIMES), "execucoes": execucoes}
                faltando = missing_executions(registro)
                resumo = f"{len(execucoes)}/{len(BASE_TIMES)} execucoes"
                if faltando:
                    resumo += f", faltaram {', '.join(faltando)}"
                log(f"jornada encerrada: {resumo} - aguardando {amanha.strftime(DATE_FORMAT)}")
            espera = (amanha - datetime.now()).total_seconds()

        time.sleep(max(0.0, min(espera, MAX_SLEEP_S)))


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log("interrompido pelo usuario")
        sys.exit(INTERRUPTED)
