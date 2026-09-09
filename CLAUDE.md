# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Estado atual do repositório

`action_runner/` **não existe no working tree**. Os arquivos ainda estão no HEAD do git
(`git show HEAD:action_runner/run_action.py`) porque foram apagados de propósito em
2026-09-09: a implementação anterior antecipou fases inteiras da spec de uma só vez e foi
descartada. O que existe hoje é apenas `action_runner_spec.md`.

Consequência prática: **não reconstrua a árvore a partir da spec**. A spec descreve o
destino final, não o próximo passo. Entregue o menor artefato que responde ao pedido
literal da mensagem atual; não crie módulos, comandos, flags ou guardrails "que vão ser
precisos depois". O código no HEAD serve como referência de seletores e do fluxo já
mapeado, não como base para restaurar.

## Regra de fases e testes

A spec (§6 e §7) define o processo: implementação passo a passo sob comando do usuário, e
testes um de cada vez — apresentar o roteiro, o usuário executa o primeiro, reporta, e só
então segue o próximo. Não existe suíte automatizada; toda validação é manual contra o
portal real.

## Comandos

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r action_runner\requirements.txt
.venv\Scripts\python.exe action_runner\entrypoint.py <comando>
```

`playwright install` **não** é necessário: o runner usa o Chrome real da máquina via
`channel="chrome"`, nunca o Chromium empacotado, nunca headless.

## Arquitetura alvo (spec)

Script Python **stateless**: um único run, sem loop, sem agendamento. Comunica resultado
exclusivamente por exit code e tira screenshot em cada situação.

- `entrypoint.py` — todo o código: máquina de estados, lock, trace, logging, exit codes.
- `config.py` — **único** lugar onde vive seletor, URL, timeout e path. O alvo é software
  de terceiro e vai mudar; o conserto precisa ser em um arquivo só.
- `logs/`, `traces/`, `evidencies/<mm-yyyy>/<dd-MM-yyyy HH.mm.ss.jpg>` — todos gitignored.

| Code | Nome | Significado |
|---|---|---|
| 0 | `OK_REGISTRED` | Registro não existia → clicou e confirmou |
| 1 | `OK_NOOP` | Registro existia → nenhuma ação |
| 10 | `SESSION_EXPIRED` | Login Microsoft / MFA detectado |
| 20 | `SANITY_FAILED` | Página inesperada / HTML mudou |
| 30 | `LOCK_ACTIVE` | Outro run em execução |
| 40 | `UNEXPECTED_ERROR` | Erro não previsto |

Atenção: a semântica de 0/1 foi **invertida** em relação ao código do HEAD (lá era
`OK_NOOP=0`, `OK_CLICKED=2`). A tabela acima é a vigente.

Invariantes que não se negociam: assertion que falha **aborta** com o código específico
(nunca "adapta e continua"); nunca digitar credencial ou resolver MFA — só detectar e sair
com 10; todo caminho de saída passa por `finally` que fecha o contexto, salva o trace e
libera o lock; timeout explícito em toda espera.

## Alvo: Portal Horas Stefanini (Apdata)

- URL: `https://portalhoras.stefanini.com/` → app em `/main.html`.
- Produto: **Apdata Global Antares 5.59.5.76** (versão no rodapé, verificada em
  2026-09-09). Quando um seletor quebrar, a primeira coisa a checar é se essa versão mudou.
- Auth: SAML 2.0 federado com Entra ID, tenant `d8bde65a-3ded-4346-9518-670204e6e184`.
  O `NTLMLogin=true` no HTML da landing é legado e não reflete o fluxo real. A entrada é
  sempre pelo botão SSO da landing (`form.singleSignOn input.btOK`), nunca por URL direta.
- Frontend **ExtJS**. IDs gerados (`button-1005`, `data-componentid`) são contadores de
  runtime e mudam conforme a ordem de instanciação dos componentes — inutilizáveis como
  seletor. Ancorar em texto, role ou classe estável.
- Prontidão da app não é `networkidle`: é `body:not(.x-masked)`. Enquanto a máscara está
  presente o DOM já existe mas não responde.
- Sessão expirada aparece como modal ExtJS (`.x-window` visível com texto "expirou"), não
  como redirect — precisa ser detectada durante a espera de prontidão, não só pela URL.
- Pode aparecer modal de LGPD/cookies antes da app carregar.

## Profile e dados sensíveis

O Chrome roda com `user_data_dir` dedicado (`action_runner/chrome_profile`), isolado do
Chrome diário. O login é manual e feito uma única vez; responder "sim" ao "Continuar
conectado?" é o que grava o cookie persistente.

Dumps de página autenticada (`_mapeamento/`) carregam token e dado pessoal — estão no
`.gitignore` e não devem ser versionados nem colados em resposta.

## Código

Sem comentários no código; explicar no chat. Erros tratados explicitamente, nada de
`except: pass` silencioso. Mensagens de log e docs em português sem acentos quando forem
para console Windows (o código anterior segue essa convenção).
