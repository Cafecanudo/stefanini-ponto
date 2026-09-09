# Action Runner — Portal Horas Stefanini

Automação de um único run: abre o portal, verifica se a marcação de ponto do horário
esperado já existe e, se não existir, registra. Não agenda, não faz loop, não fica vivo.
O agendamento é responsabilidade de quem chama o script.

Alvo: Apdata Global Antares (frontend ExtJS) atrás de SSO SAML com Entra ID.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r action_runner\requirements.txt
```

`playwright install` não é necessário. O script usa o Chrome real já instalado na máquina
via `channel="chrome"`, nunca o Chromium empacotado do Playwright.

## Variáveis de ambiente

Credenciais nunca ficam no fonte.

| Variável | Conteúdo |
|---|---|
| `USER_STEFANINI` | e-mail corporativo usado no login Microsoft |
| `PASS_STEFANINI` | senha |

```powershell
setx USER_STEFANINI "usuario@latam.stefanini.com"
setx PASS_STEFANINI "senha"
```

`setx` grava permanentemente para o usuário, mas **não afeta terminais já abertos**. Para a
sessão atual:

```powershell
$env:USER_STEFANINI = "usuario@latam.stefanini.com"
$env:PASS_STEFANINI = "senha"
```

Se a senha contiver `$`, use aspas simples para evitar interpolação do PowerShell.

Com qualquer uma das duas ausente, o script informa no log e não tenta autenticar — não
submete campo vazio, o que evitaria bloqueio de conta por tentativas inválidas.

## Uso

```powershell
.venv\Scripts\python.exe action_runner\entrypoint.py --current-exe 2
```

### Parâmetros

| Parâmetro | Default | Descrição |
|---|---|---|
| `--current-exe` | obrigatório | Qual das quatro marcações do dia verificar: `1`, `2`, `3` ou `4` |
| `--show` | `false` | Mostra a janela do Chrome. Sem a flag, roda headless |
| `--exp-windows` | ver abaixo | Janelas de horário, formato `N=HH:MM-HH:MM` separadas por vírgula |

Aceita também as variantes com underscore (`--current_exe`, `--exp_windows`).

### Janelas padrão

```
1=08:45-09:15,2=12:45-13:15,3=13:45-14:15,4=17:45-18:15
```

Uma marcação dentro da janela do `--current-exe` significa "ponto já batido" → o script
encerra sem agir. Limites são inclusivos.

### Exemplos

```powershell
# entrada da manhã, headless
.venv\Scripts\python.exe action_runner\entrypoint.py --current-exe 1

# volta do almoço, com janela do Chrome visível
.venv\Scripts\python.exe action_runner\entrypoint.py --current-exe 3 --show

# janelas customizadas
.venv\Scripts\python.exe action_runner\entrypoint.py --current-exe 1 --exp-windows "1=08:00-09:30,2=12:00-13:30"
```

`--exp-windows` **substitui** o dicionário inteiro, não faz merge. Se a janela do
`--current-exe` escolhido não estiver na lista, o script para no argparse com mensagem
explícita, antes de abrir o Chrome.

Valores malformados são rejeitados na entrada: `HH:MM` fora de faixa, início depois do fim,
índice não numérico, item sem `=` ou sem `-`.

## Fluxo

```
abre o portal
  └ aceita "Confirmar preferências" (só na primeira vez do profile)
  └ clica "Entrar no portal" (SSO)
  └ [autenticação, se necessária — ver abaixo]
  └ WorkArea
  └ Apontamento Diário
  └ marca o checkbox da linha do dia corrente
  └ Calcular dias selecionados
  └ confirma o dialog "Ok"
  └ fecha a janela "Calcular Dias"
  └ lê as marcações da linha do dia
       ├ existe marcação na janela do --current-exe → encerra com exit 1
       └ não existe → volta à tela inicial
                    → Relógio de Ponto Virtual
                    → Efetuar Marcação
```

A linha do dia é localizada pelo texto `dd/mm` na célula de data, não por índice ou por
`data-recordid` — ambos mudam conforme o período carregado. Os horários são extraídos por
regex `\b\d{2}:\d{2}\b` sobre o texto da linha inteira, sem depender de qual coluna
(`E1`/`S1`/`E2`/`S2`...) está preenchida.

## Autenticação

O script entra sempre pelo botão SSO da landing. Depois disso, detecta qual tela apareceu e
segue o caminho correspondente:

| Estado | Ação |
|---|---|
| `portal` | já autenticado, segue direto |
| `tile` | tela "Escolha uma conta" → clica na conta de `USER_STEFANINI` |
| `email` | tela "Entrar" → preenche e-mail → Avançar |
| `password` | tela "Insira a senha" → preenche senha → Entrar |
| `nenhum` | nada reconhecido, segue e falha adiante com mensagem própria |

`tile` e `email` desembocam em `password`, então a etapa de senha não é duplicada.

Após a senha, aguarda a confirmação **manual** do MFA no Authenticator e trata:

- **"Verifique sua identidade"** (falha de verificação ou escolha de método): clica em
  "Aprovar uma solicitação em meu aplicativo Microsoft Authenticator" para reenviar o push.
  Limitado a 3 tentativas — rajada de solicitações é tratada pelo Entra como MFA fatigue
  attack e pode bloquear a conta.
- **"Continuar conectado?"**: marca "Não mostrar isso novamente" e clica em "Sim". É o que
  grava o cookie persistente no profile e faz esta tela não aparecer nas próximas vezes.

O profile do Chrome fica em `action_runner/chrome_profile`, isolado do Chrome do dia a dia
e fora do versionamento.

## Exit codes

| Code | Nome | Significado | Estado |
|---|---|---|---|
| 1 | `OK_NOOP` | Marcação já existia na janela → nenhuma ação | implementado |
| 0 | — | Fim normal de qualquer outro caminho | implementado |
| 0 | `OK_REGISTRED` | Marcação registrada e confirmada | pendente |
| 10 | `SESSION_EXPIRED` | Login/MFA detectado | pendente |
| 20 | `SANITY_FAILED` | Página inesperada / HTML mudou | pendente |
| 30 | `LOCK_ACTIVE` | Outro run em execução | pendente |
| 40 | `UNEXPECTED_ERROR` | Erro não previsto | pendente |

Hoje só `OK_NOOP` é emitido deliberadamente. Todos os outros desfechos — inclusive falhas —
terminam em `0`. Um scheduler ainda não consegue distinguir sucesso de erro por exit code.

## Seletores

Todos ficam no topo de `entrypoint.py`, como constantes. Nenhum seletor no meio da lógica.

| Elemento | Âncora | Por quê |
|---|---|---|
| Entrar no portal | `input.btOK[lang="btLoginEntrar"]` | `lang` aqui é chave de i18n, independe de idioma |
| WorkArea | `a.sidebarButtons.workarea` | classes da aplicação, não do framework |
| Voltar à tela inicial | `button.headerButtons.homeButton` | idem |
| Calcular dias | `a.toolbar-footer-button:has(span[style*="img201.png"])` | botão sem texto e sem `data-qtip` no DOM; o ícone é o único discriminante |
| Ok do dialog | `.x-message-box:visible a[role="button"]:has(span.x-btn-inner:text-is("Ok"))` | o MessageBox instancia Ok/Sim/Não/Cancelar e esconde os não usados |
| Fechar janela | `.x-window:not(.x-message-box):visible div.x-tool[aria-label="Close panel"]` | exclui o message box para evitar corrida durante o fade-out |
| Linha do dia | `tr.x-grid-row` filtrado por `td` com texto `dd/mm` | data é a única identidade estável da linha |

**IDs gerados pelo ExtJS não são usados.** `button-1005`, `ext-533`, `tool-1434`,
`data-componentid` são contadores de runtime: o mesmo `button-1005` aparece ora no botão
WorkArea, ora no Ok do message box, conforme a ordem de instanciação dos componentes.

Cuidado com `lang`: no botão "Entrar no portal" ele vale `btLoginEntrar` (chave de i18n
legítima), mas no botão home vale `ext-171` (contador). O Apdata usa o mesmo atributo para
as duas coisas — não é confiável como regra geral.

Baseline do alvo: **Apdata Global Antares 5.59.5.76**, versão no rodapé do portal. Quando um
seletor quebrar, a primeira verificação é se essa versão mudou.

## Limitações conhecidas

1. **`punch.click()` está comentado.** O bloco imprime `marcacao efetuada` sem bater ponto.
   Descomentar é o que ativa a ação real.
2. **`input("ENTER para fechar")` no fim.** Em headless o processo fica parado esperando um
   ENTER sem janela visível. Bloqueia uso agendado.
3. **`APP_READY_TIMEOUT_MS = 0`** desabilita o timeout da espera do WorkArea — o Playwright
   interpreta `0` como "sem limite". Se a app não carregar, o script espera indefinidamente.
4. **Sem lock de execução.** Dois runs simultâneos operam sobre o mesmo profile do Chrome.
5. **Sem trace, sem log em arquivo, sem screenshot.** Toda a saída é `print` no stdout.
6. **A guarda de idempotência é a janela de horário.** Uma marcação fora dela — bateu 08:28
   com a janela começando 08:45 — é lida como ausente, e o script bate de novo. A dupla
   verificação imediatamente antes do clique, prevista na spec, não existe: há dois cliques
   e uma navegação entre a leitura e a ação.
