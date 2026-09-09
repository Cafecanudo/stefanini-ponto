# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Como trabalhar neste repositório

Implementação passo a passo, sob comando explícito. Entregue o menor artefato que responde
ao pedido literal da mensagem atual. **Não** crie módulos, comandos, flags ou guardrails
"que vão ser precisos depois", e não antecipe fases de `action_runner_spec.md` — a spec
descreve o destino final, não o próximo passo. Uma implementação anterior que construiu
tudo de uma vez a partir dela foi descartada inteira.

Ao identificar um risco técnico real, diga em uma ou duas linhas e siga com o que foi
pedido. Não implemente a mitigação por conta própria.

Testes são manuais, um de cada vez, contra o portal real. Não existe suíte automatizada.

## Comandos

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r action_runner\requirements.txt
.venv\Scripts\python.exe action_runner\entrypoint.py --current-exe 2 --show
```

`playwright install` não é necessário — o runner usa o Chrome real via `channel="chrome"`.

Credenciais vêm de `USER_STEFANINI` e `PASS_STEFANINI` (variáveis de ambiente do usuário).
`action_runner/README.md` tem a documentação de uso completa: parâmetros, fluxo, seletores
e limitações conhecidas.

Validação rápida após editar:

```powershell
.venv\Scripts\python.exe -W error::SyntaxWarning -c "import py_compile; py_compile.compile('action_runner/entrypoint.py', doraise=True)"
```

## Arquitetura

Tudo em `action_runner/entrypoint.py`: constantes no topo (seletores, timeouts, janelas de
horário), funções auxiliares, e um `main()` linear dentro de um `with sync_playwright()`.
Não há `config.py` — a spec menciona um, mas o código vigente concentra os seletores como
constantes de módulo no próprio entrypoint. Nenhum seletor no meio da lógica.

Cada passo do fluxo segue a mesma forma: localizar → `wait_for(state="visible")` com timeout
explícito → agir dentro do `else` → `print` → `page.wait_for_timeout(CLICK_DELAY_MS)`. Um
seletor que não casa imprime a própria mensagem e o fluxo continua; não há aborto.

Esperas por estado ambíguo (login, MFA) usam funções de poll que devolvem uma string de
estado — `wait_for_login_state`, `wait_for_kmsi_or_portal`. Elas testam várias condições em
paralelo porque a tela seguinte não é determinística.

### Divergências deliberadas em relação à spec

Não "corrija" estas por conta própria — foram decisões do usuário:

1. A spec proíbe digitar credenciais (`exit 10` em login/MFA). O código **autentica**:
   e-mail, senha, reenvio de MFA e "Continuar conectado". Só a aprovação no Authenticator
   é manual.
2. Dos exit codes da spec, apenas `OK_NOOP = 1` é emitido. Todo o resto termina em `0`,
   inclusive falhas.
3. Não há lock, trace, log em arquivo nem screenshot de evidência.
4. `punch.click()` está comentado — o clique que registra o ponto de fato.

## Alvo: Portal Horas Stefanini (Apdata)

- `https://portalhoras.stefanini.com/` → app em `/main.html`.
- **Apdata Global Antares 5.59.5.76** (rodapé). Seletor quebrado: cheque essa versão antes.
- Frontend **ExtJS**. IDs gerados (`button-1005`, `ext-533`, `tool-1434`, `data-componentid`)
  são contadores de runtime — o mesmo `button-1005` já apareceu no WorkArea e no Ok de um
  message box. Nunca use como âncora. Prefira classes da aplicação (`sidebarButtons`,
  `headerButtons`, `toolbar-footer-button`), `aria-label`, `data-value`.
- `lang` é ambíguo no Apdata: em "Entrar no portal" vale `btLoginEntrar` (chave de i18n
  legítima), no botão home vale `ext-171` (contador). Verifique caso a caso.
- Botões de toolbar podem não ter texto nem `data-qtip` no DOM — o tooltip vem da config do
  componente ExtJS e só materializa no hover. Nesses casos o `background-image` do ícone é o
  único discriminante disponível.
- Prontidão da app não é `networkidle`, é `body:not(.x-masked)`. Na prática, esperar o
  elemento-alvo ficar visível resolve, porque o `click()` do Playwright já checa
  actionability e espera a máscara sair.
- Modais: `.x-window` é janela comum, `.x-message-box` é o `Ext.MessageBox` — que é
  singleton e permanece no DOM oculto entre usos. Sempre escope com `:visible`, e use
  `:not(.x-message-box)` ao mirar a janela de baixo para evitar corrida no fade-out.

## Autenticação Entra ID

SAML 2.0 federado, tenant `d8bde65a-3ded-4346-9518-670204e6e184`. Entrada sempre pelo botão
SSO da landing, nunca por URL direta. O `NTLMLogin=true` no HTML da landing é legado.

Campos estáveis há anos: `input[name="loginfmt"]`, `input[name="passwd"]`,
`input[type="submit"]` (o "Não" do KMSI é `type="button"`, então não colide).
`#KmsiCheckboxField` só existe na tela "Continuar conectado" — é o sinal confiável dela.
`data-value="PhoneAppNotification"` identifica o método do Authenticator.

Reenvio de MFA é limitado a 3 tentativas: rajada de push é tratada pelo Entra como MFA
fatigue attack e pode bloquear a conta.

O profile fica em `action_runner/chrome_profile` (gitignored), isolado do Chrome diário.

## Armadilhas de ferramenta já encontradas

1. **Heredoc do Bash engole um nível de backslash.** Escrever `"\\b"` num payload de
   heredoc resultou no byte `0x08` dentro do arquivo — regex que nunca casaria, sem erro
   visível. Para conteúdo com backslash (regex, caminhos Windows), use a ferramenta de
   escrita de arquivo, ou construa com `chr(92)` dentro do Python.
2. **`:text-is()` e `:text()` casam o menor elemento** que contém o texto. Em ExtJS o texto
   fica num `<span>` interno, então `a[role="button"]:text-is("Ok")` casa **zero**
   elementos. Use `a:has(span.x-btn-inner:text-is("Ok"))`.
3. **Antes de aplicar um seletor novo, teste-o.** Salvar o HTML que o usuário mandou num
   arquivo e rodar `page.set_content()` com `channel="chrome", headless=True` dá o número
   de matches e os ids casados em segundos, e já pegou vários erros antes de irem para o
   portal real.
4. **Substituições por texto precisam de `assert`.** Uma substituição que não casou passou
   silenciosamente e produziu `NameError` só em runtime, porque o usuário havia editado a
   constante-âncora entre uma mensagem e outra. Ele edita o arquivo — releia antes de
   ancorar.

## Segredos e dados sensíveis

Credenciais só em variável de ambiente, nunca no fonte. O repositório tem remote no GitHub.

Dumps de página autenticada (`_mapeamento/`) carregam token e dado pessoal — gitignored,
não versionar nem colar em resposta.

## Código

Sem comentários no código; explicar no chat. Erros tratados explicitamente, nada de
`except: pass` silencioso. Mensagens de log em português sem acentos (console Windows);
documentação em markdown pode usar acentos.
