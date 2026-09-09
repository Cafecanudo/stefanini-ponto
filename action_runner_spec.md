# Spec: Action Runner (automação Chrome — script de execução da ação)

> Documento de handoff para agente. Implemente **exatamente** o que está aqui. Não infira funcionalidades além do escopo. Onde houver `[PENDENTE]`, pare e pergunte antes de codar.

---

## 1. Objetivo

Script Python **stateless** que executa **um único run** de uma automação de browser e termina com um **exit code** que comunica o resultado. Não agenda, não faz loop, não fica vivo. O agendamento é responsabilidade de outro script (fora deste escopo).

Regra de negócio central:

- Ler uma página web autenticada.
- Verificar se um **registro existe**.
- Se existe → **não faz nada** (no-op).
- Se não existe → **clica** em um botão/elemento e confirma o efeito.

O clique é irreversível, porém **não gera danos**. Mesmo assim, aplicar verificação dupla antes de clicar (custo baixo, evita clique por leitura instável).

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

Definir como enum em `exit_codes.py`. O script **sempre** sai com um destes códigos:

| Code | Nome | Significado |
|---|---|---|
| 0 | `OK_NOOP` | Registro existia → nenhuma ação |
| 1 | `OK_CLICKED` | Registro não existia → clicou e confirmou |
| 10 | `SESSION_EXPIRED` | Caiu em `login.microsoftonline.com` / tela de MFA |
| 20 | `SANITY_FAILED` | Assertion de sanidade falhou (página inesperada / HTML mudou) |
| 30 | `LOCK_ACTIVE` | Outro run já em execução |
| 40 | `UNEXPECTED_ERROR` | Erro não previsto |

Regras:
- `0` e `1` são **ambos sucesso**; só diferem em ter ou não clicado.
- Em `10`: **nunca** tentar logar, digitar credencial ou resolver MFA. Apenas detectar, logar e sair.
- Todo caminho de saída passa por um bloco `finally` que fecha o contexto, salva o trace e libera o lock.

---

## 4. Máquina de estados do run

Implementar nesta ordem exata em `run_action.py`:

1. **Adquire lock** (`guards.py`). Se lock ativo e processo vivo → `exit 30`. Se lock órfão (PID morto) → limpa e prossegue.
2. **Lança Chrome persistente** headful (`browser.py`).
3. **Inicia trace** do Playwright.
4. **Navega** até `TARGET_URL`.
5. **Sanity assertion #1**:
   - Se URL/DOM indica `login.microsoftonline.com` ou tela de MFA → `exit 10`.
   - Se página não é a esperada (âncora ausente) → `exit 20`.
6. **Lê estado**: o registro existe? (seletor resiliente, leitura determinística).
7. **Decisão**:
   - Existe → `exit 0` (fim, sem tocar em nada).
   - Não existe → prossegue.
8. **Verificação dupla**: reconfirma a ausência do registro imediatamente antes de clicar.
9. **Clica** no elemento alvo.
10. **Pós-assertion**: confirma que o clique produziu o efeito esperado. Se não → `exit 40` + trace.
11. `exit 1`.
12. **`finally`** (sempre executa): fecha contexto, salva trace, libera lock.

---

## 5. Guardrails (obrigatórios)

1. Qualquer assertion que falhar → **aborta com o exit code específico**. NUNCA "adapta e continua". Falha silenciosa é o inimigo neste sistema.
2. Idempotência: garantida pela regra "clica só se não existe" + verificação dupla.
3. **Lock de execução**: arquivo contendo PID + timestamp. Detectar e limpar lock órfão (processo inexistente).
4. **Nunca** digitar credenciais. Login/MFA → `exit 10`.
5. **Trace por run** (Playwright) para replay visual de falhas não-assistidas.
6. Timeouts explícitos em toda navegação/espera. Nada de espera infinita.

---

## 6. Estrutura de arquivos

```
action_runner/
  run_action.py        # entrypoint: máquina de estados + exit codes
  browser.py           # lança/fecha launch_persistent_context
  page_actions.py      # navegar, ler "existe?", clicar, pós-assertion
  guards.py            # lock, detecção de MFA/login, sanity assertions
  config.py            # user_data_dir, URL, SELETORES, timeouts (via env)
  exit_codes.py        # IntEnum dos códigos
  logs/                # log estruturado por run (criar se não existir)
  traces/              # traces do Playwright (criar se não existir)
  requirements.txt
  README.md            # como fazer o login manual inicial + como rodar
```

Regra crítica: **todos os seletores ficam isolados em `config.py`**, nunca espalhados no código. O alvo é de terceiro e vai mudar — o conserto deve ser em um lugar só. Seletores por **texto / role / data-attribute**, evitar XPath frágil.

Config via variáveis de ambiente com defaults sensatos: `USER_DATA_DIR`, `TARGET_URL`, `HEADLESS=false` (sempre false nesta fase), `NAV_TIMEOUT_MS`, `LOCK_PATH`.

---

## 7. Implementação por fases (respeitar a ordem)

### Fase 1 — Profile + login manual
- Criar `user_data_dir` dedicado.
- Um modo/comando que abre o Chrome persistente headful para o usuário **logar manualmente uma única vez** (incluindo MFA).
- Validar que a sessão persiste após fechar e reabrir o script.
- Documentar o passo no `README.md`.

### Fase 2 — Núcleo determinístico (DRY-RUN, não clica)
- Implementar: navegar + sanity assertions + leitura "registro existe?".
- **Não clicar.** Em vez de clicar, **logar a decisão** que seria tomada ("no-op" ou "clicaria").
- Objetivo: calibrar seletores sem risco de disparar a ação irreversível.

### Fase 3 — Ação real
- Habilitar o clique + verificação dupla + pós-assertion.
- Um flag de config separa dry-run de execução real (`DRY_RUN=true/false`), default `true` até validação.

### Fase 4 — Robustez
- Lock (com limpeza de órfão), exit codes finais conforme tabela, trace, log estruturado.

> Notificação e scheduler são scripts separados, **fora deste escopo**. Não implementar aqui.

---

## 8. Roteiro de testes (executar ao fim de cada fase, um a um)

**Fase 1**
1. Login manual persiste após matar e relançar o script.
2. Sessão sobrevive a reboot da máquina.

**Fase 2 (dry-run — não clica)**
1. Registro existe → log = "no-op".
2. Registro não existe → log = "clicaria" (não clica).
3. Sessão expirada → detecta MFA → `exit 10`.
4. Âncora ausente / HTML alterado → `exit 20`.

**Fase 3**
1. Registro não existe → clica → pós-assertion confirma → `exit 1`.
2. Verificação dupla: cenário de leitura instável → não clica indevidamente.
3. Pós-assertion falha → `exit 40` + trace.
4. Registro existe → `exit 0` sem clique.

**Fase 4**
1. Lock ativo (processo vivo) → segundo run → `exit 30`.
2. Lock órfão (processo morto) → limpo → run prossegue.
3. Trace gravado e abrível em todos os cenários.
4. Todos os exit codes batem com a tabela da seção 3.

---

## 9. Restrições de segurança (não violar)

- Não digitar senha, token, MFA ou qualquer credencial em campo. Login → `exit 10`.
- Não tentar bypass de CAPTCHA / bot-detection. A sessão persistente logada é o mecanismo — se ela falhar, é `exit 10`, não workaround.
- Não completar formulários/ações além do único clique especificado na regra de negócio.

---

## 10. Padrão de código

- Código profissional, sem atalhos didáticos.
- **Sem comentários no código.** Se algo precisar de explicação, colocar no `README.md`.
- Type hints em todas as assinaturas.
- Erros tratados explicitamente; nada de `except: pass` silencioso.
- Timeouts e paths sempre configuráveis, nunca hardcoded no meio da lógica.

---

## 11. Itens `[PENDENTE]` — pare e pergunte antes de implementar

- `TARGET_URL` real.
- Seletor de "registro existe".
- Seletor do elemento a clicar.
- Âncora de página válida (sanity #1).
- Âncora da tela de MFA/login.
- Âncora de pós-clique (o que confirma que o clique funcionou).

Estes seis serão fornecidos na **Fase 0 (mapeamento)**. Não invente seletores.
