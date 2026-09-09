## 1. Objetivo

Script Python **stateless** que executa **um único run** de uma automação de browser e termina com um **exit code** que comunica o resultado. Não agenda, não faz loop, não fica vivo. Tambem devera tirar uma foto da tela em cada situacao

---

## 2. Stack obrigatória

- **Python 3.11+**
- **Playwright** (API sync)
- **Chrome real** via `launch_persistent_context(channel="chrome")` — NÃO usar o Chromium empacotado do Playwright, NÃO usar headless.
- **Profile persistente dedicado** (`user_data_dir` próprio da automação, isolado do Chrome diário do usuário).
- Cross-platform: código único deve rodar em **Windows, macOS e Linux**.
- Sem LLM em runtime. A decisão é 100% determinística.

Dependências: `playwright`. Nada além disso nesta fase (notificação/scheduler são outros scripts).

---

## 3. Contrato de saída — Exit Codes (cidadão de primeira classe)

Todo projeto deve ficar uma unico arquivo **entrypoint.py** exceto seletores. O script **sempre** sai com um destes códigos:

| Code | Nome | Significado |
|---|---|---|
| 0 | `OK_REGISTRED` | Registro não existia → clicou e confirmou |
| 1 | `OK_NOOP` | Registro existia → nenhuma ação |
| 10 | `SESSION_EXPIRED` | Caiu em `login.microsoftonline.com` / tela de MFA |
| 20 | `SANITY_FAILED` | Assertion de sanidade falhou (página inesperada / HTML mudou) |
| 30 | `LOCK_ACTIVE` | Outro run já em execução |
| 40 | `UNEXPECTED_ERROR` | Erro não previsto |

Regras:
- `0` e `1` são **ambos sucesso**; só diferem em ter ou não clicado.
- Em `10`: **nunca** tentar logar, digitar credencial ou resolver MFA. Apenas detectar, logar e sair.
- Todo caminho de saída passa por um bloco `finally` que fecha o contexto, salva o trace e libera o lock.

---

## 4. Guardrails (obrigatórios)

1. Qualquer assertion que falhar → **aborta com o exit code específico**. NUNCA "adapta e continua". Falha silenciosa é o inimigo neste sistema.
2. Idempotência: garantida pela regra "clica só se não existe" + verificação dupla.
3. **Lock de execução**: arquivo contendo PID + timestamp. Detectar e limpar lock órfão (processo inexistente).
4. **Nunca** digitar credenciais. Login/MFA → `exit 10`.
5. **Trace por run** (Playwright) para replay visual de falhas não-assistidas.
6. Timeouts explícitos em toda navegação/espera. Nada de espera infinita.
7. Adicionar logs para identificar problemas

---

## 5. Estrutura de arquivos

```
action_runner/
  entrypoint.py        # entrypoint: máquina de estados + exit codes
  config.py            # user_data_dir, URL, SELETORES, timeouts (via env)
  logs/                # log estruturado por run (criar se não existir)
  traces/              # traces do Playwright (criar se não existir)
  evidencies           # Pasta que conterá screenshot de situações, dentro desta pasta deve ter uma pasta para cada mes no formato **mm-yyyy**, dentro desta pasta os screenshot salvos com **dd-MM-yyyy HH.mm.ss.jpg**
  requirements.txt
  README.md            # como fazer o login manual inicial + como rodar
```

Regra crítica: **todos os seletores ficam isolados em `config.py`**, nunca espalhados no código. O alvo é de terceiro e vai mudar — o conserto deve ser em um lugar só. Seletores por **texto / role / data-attribute**, evitar XPath frágil.

Config via variáveis constante na classe **config.py** com defaults sensatos: `USER_DATA_DIR`, `TARGET_URL`, `HEADLESS=false` (sempre false nesta fase), `NAV_TIMEOUT_MS`, `LOCK_PATH`.

---

## 6. Implementação por fases (respeitar a ordem)

Vamos fazer tudo passo a passo, eu digo o que preciso faze entao executa

---

## 7. Roteiro de testes (executar ao fim de cada fase, um a um)

Todas as vezes que iniciarmos testes, faça um roteiro, mas vamos fazer testes por teste, um de cada vez, eu testo o primeiro mando o resultado e seguimos para o proximo e assim por diante.

---

## 8. Padrão de código

- Código profissional, sem atalhos didáticos.
- **Sem comentários no código.** somente se algo precisar de explicação, mas seja breve.
- Erros tratados explicitamente; nada de `except: pass` silencioso.
