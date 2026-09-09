# Action Runner — Portal Horas

Automação stateless de um único run. Não agenda, não faz loop.

## Estado atual: Fase 1

Implementado: profile persistente, login manual, verificação de sessão, captura de DOM.
Não implementado: leitura de estado, clique, lock, trace.

## Setup

```
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r action_runner\requirements.txt
```

Não é necessário `playwright install` — o script usa o Chrome real já instalado
na máquina via `channel="chrome"`.

## Login manual (executar uma única vez)

```
.venv\Scripts\python.exe action_runner\run_action.py login
```

Abre uma janela do Chrome usando um profile dedicado em `action_runner/chrome_profile`,
isolado do Chrome do dia a dia. Faça o login completo, incluindo MFA. Quando o portal
estiver carregado, volte ao terminal e pressione ENTER.

O script nunca digita credenciais. Se ao final ainda estiver na tela de login,
sai com código 10.

## Validar persistência da sessão

```
.venv\Scripts\python.exe action_runner\run_action.py check
```

Exit 0 = sessão válida. Exit 10 = sessão expirada, refazer o login manual.

Com captura de DOM junto:

```
.venv\Scripts\python.exe action_runner\run_action.py check --dump estado_inicial
```

## Capturar um estado específico

```
.venv\Scripts\python.exe action_runner\run_action.py dump com_registro
```

Abre o portal, espera você navegar até a tela desejada e, ao ENTER, grava
`_mapeamento/com_registro.html` e `_mapeamento/com_registro.png`.

`_mapeamento/` está no `.gitignore`: dumps de página autenticada carregam tokens e
dados pessoais e não devem ser versionados.

## Exit codes

| Code | Nome | Significado |
|---|---|---|
| 0 | OK_NOOP | Registro existia → nenhuma ação |
| 2 | OK_CLICKED | Registro não existia → clicou e confirmou |
| 10 | SESSION_EXPIRED | Login / MFA detectado |
| 20 | SANITY_FAILED | Página inesperada / HTML mudou |
| 30 | LOCK_ACTIVE | Outro run em execução |
| 40 | UNEXPECTED_ERROR | Erro não previsto |

Faixa `< 10` é sucesso, `>= 10` é falha. Isso permite que qualquer scheduler use a
convenção padrão sem wrapper de tradução.

## Configuração via ambiente

| Variável | Default |
|---|---|
| `TARGET_URL` | `https://portalhoras.stefanini.com/main.html` |
| `USER_DATA_DIR` | `action_runner/chrome_profile` |
| `LOCK_PATH` | `action_runner/run.lock` |
| `LOGS_DIR` | `action_runner/logs` |
| `TRACES_DIR` | `action_runner/traces` |
| `DUMP_DIR` | `_mapeamento` |
| `HEADLESS` | `false` |
| `DRY_RUN` | `true` |
| `NAV_TIMEOUT_MS` | `60000` |
| `ACTION_TIMEOUT_MS` | `15000` |
| `SETTLE_TIMEOUT_MS` | `20000` |
| `CHROME_CHANNEL` | `chrome` |

## Seletores

Todos ficam em `config.py`, no dict `SELECTORS`. Nenhum seletor no meio da lógica.
Os que ainda estão `None` são da Fase 0 de mapeamento e fazem o run abortar com
mensagem explícita quando exigidos.

IDs gerados pelo ExtJS (`button-1005`, `data-componentid`) não são usados: são
contadores de runtime e mudam a cada mudança de ordem de instanciação dos componentes.
