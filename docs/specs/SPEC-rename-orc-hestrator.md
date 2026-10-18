# SPEC — F7: renomeação para orc-hestrator-server

Status: especificada. Executa depois de F1 fechar o G5 (evita corrida nos mesmos arquivos).
Decisão registrada em `docs/adr/ADR-006-rename-orc-hestrator.md`.

## Requisitos (EARS)

R1. `pyproject.toml` DEVE declarar `name = "orc-hestrator-server"`, manter a versão corrente do pacote e
    remover a afirmação de "port" das descrições de metadados.
R2. Os scripts de console DEVEM incluir `orc` (servidor MCP) e `orc-ui` (UI), além de
    `orc-mcp` como alias explícito de stdio. Os scripts legados `task-orchestrator-py` e
    `task-orchestrator-ui` DEVEM continuar existindo como alias e DEVEM emitir aviso de
    deprecação em stderr ao serem usados.
    R2.1 (acréscimo do G0). `orc-hestrator` DEVE ser também um console script, em stdio e SEM
    aviso: `uvx <distribuição>` só funciona com script homônimo à distribuição, e o README promete
    `uvx orc-hestrator-server`. Sem ele o quick-start publicado quebra.
R3. As variáveis de ambiente primárias passam a ser `ORC_DB`, `ORC_CONFIG` e `ORC_LANG`. As
    antigas (`TASK_ORCHESTRATOR_DB`, `TASK_ORCHESTRATOR_CONFIG`) DEVEM continuar funcionando como
    fallback, com as novas tendo precedência e um aviso único de deprecação no log.
R4. O servidor FastMCP DEVE reportar `name = "orc"` em `initialize`, mantendo a versão vinda de
    `importlib.metadata` (R6 da F1).
R5. `docs/TOOLS.md` DEVE ser gerado por script a partir de `tools/list` do servidor, de modo que
    contagem e nomes de tools nunca sejam digitados à mão. O script DEVE falhar com código de
    saída diferente de zero se o arquivo em disco divergir do servidor.
R6. O README DEVE apresentar o lockup `Orc[hestrator]`, a distribuição `orc-hestrator-server`, o comando
    `orc`, e uma única linha de origem: "formerly published as task-orchestrator-py".
R7. `CHANGELOG.md` DEVE registrar a renomeação em uma entrada própria; nenhuma entrada histórica
    DEVE ser reescrita.
R8. O texto de onboarding (F1) DEVE ensinar os comandos novos: `uv run orc` (stdio) e `orc-serve`
    (streamable-http). O nome da DISTRIBUIÇÃO (`orc-hestrator-server`) não é comando e não deve ser
    ensinado como tal — `uv run <nome>` só funciona para console scripts. Correção do G5.
R9. CI DEVE rodar com o nome novo de distribuição; o workflow não pode depender do nome antigo.
R10. O transporte DEVE ser escolhido pelo ponto de entrada, não pela variável de ambiente
     (ADR-007): `orc` abre em stdio, `orc-serve` abre em `streamable-http` usando `MCP_PORT`.
     `MCP_TRANSPORT` permanece como override para testes e casos de borda.
R11. O repositório DEVE versionar o deploy em `deploy/`: unit systemd de usuário cujo `ExecStart`
     chama `orc-serve`, e um `orc.env.example` com as variáveis necessárias. Nenhum artefato de
     deploy DEVE continuar existindo apenas numa máquina.
R12. A versão de release DEVE ser **2.0.0** para `orc-hestrator-server`, e a última release do nome antigo
     DEVE ser **1.5.1**, publicada no mesmo ato e nunca antes. Justificativa: nome de distribuição,
     comando, precedência de variáveis e nome do servidor MCP são quebra de contrato para quem já
     usa — 1.6.0 subestimaria isso, e 0.x negaria a continuidade. A 1.5.1 leva apenas metadados
     (mesmo código) cuja descrição aponta para o nome novo.
R13. `pyproject.toml` DEVE ir a 2.0.0 na mesma fatia em que o nome muda, e `CHANGELOG.md` DEVE abrir
     a seção 2.0.0 listando as quebras; `uv.lock` DEVE ser regenerado com a mesma versão de `uv`
     usada no CI.

## Critérios de aceite

AC1. `pip install -e .` (ou `uv sync`) instala e expõe `orc` e `orc-ui`; `orc --help` responde e
     `which orc` aponta para o venv/ambiente ativo.
AC2. `orc-mcp` e `task-orchestrator-py` sobem o servidor em stdio; o segundo imprime aviso de
     deprecação em stderr e o primeiro não.
AC3. `ORC_DB` vence `TASK_ORCHESTRATOR_DB` quando ambos estão definidos (provado por execução, com
     dois bancos distintos e verificação de qual arquivo foi criado).
AC4. `tools/list` via cliente MCP real devolve `serverInfo.name == "orc"` e
     `serverInfo.version == importlib.metadata.version("orc-hestrator-server")`.
AC5. `docs/TOOLS.md` gerado bate com `tools/list`; adulterar o arquivo à mão faz o script falhar.
AC6. `pytest -q` verde, `ruff check` e `ruff format --check` limpos.
AC7 (escopo ajustado no G0). `grep -rn "task-orchestrator-py"` em código (`src/`, `tests/`,
     `pyproject.toml`), `README.md`, `llms.txt` e `site/` devolve apenas: a linha "formerly
     published as" do README, `llms.txt`, o alias de script e o teste do aviso de deprecação.
     Documentos datados — `CHANGELOG.md`, `docs/adr/`, `docs/specs/`, `docs/rfc/` — ficam fora do
     escopo: são registro histórico e reescrevê-los violaria R7 no espírito. Na leitura estrita
     anterior a AC era insatisfazível (27 ocorrências legítimas em docs históricos).
AC8. `orc` sobe em stdio (provado por cliente MCP que spawna o comando) e `orc-serve` sobe em
     `streamable-http` na porta de `MCP_PORT` (provado por cliente HTTP real). Nenhum dos dois
     exige `MCP_TRANSPORT`.
AC9. `deploy/orc.service` existe, referencia `orc-serve` e é válido segundo `systemd-analyze verify`
     (ou justificativa registrada se a verificação não puder rodar no host de desenvolvimento).

## Não escopo

- Renomear o pacote de importação `task_orchestrator` (decisão da ADR-006).
- Publicar no PyPI (passo de release, exige credencial e é feito pelo Claudio).
- Renomear o repositório no GitHub (ação manual, com redirecionamento automático).
- Traduções: F7 é nomes, não idioma; i18n é a F8.

## Diário de gate

Decisões fixadas (não reabrir):
- Ordem de execução corrigida: G3 RED → G4 GREEN (pyproject, aliases, env, servidor, gerador de TOOLS, docs, CI) → G4.2 metadados da 1.5.1 → regenerar `uv.lock` com o `uv` do CI → G5 review → G6 validação → atos manuais do Claudio (renomear repo no GitHub; publicar 2.0.0 e 1.5.1 no mesmo ato) → atualizar links do site → G7 revisão de release.
- Regenerar `uv.lock` é pré-requisito de publicação (R13 + dívida P2-3 da F1).
- Renomear repositório no GitHub e publicar no PyPI permanecem fora da fatia de código: são atos manuais do Claudio, posicionados depois do G6.
- R5 (`docs/TOOLS.md` gerado de `tools/list`), R8 (onboarding ensina `uv run orc-hestrator-server` e `orc`) e R9 (CI com nome novo) fazem parte do G4, não são "urls".

### G4.2 — a 1.5.1 fecha até a publicação

- A 1.5.1 sai de um commit PRÓPRIO, ANTERIOR à renomeação: apenas metadados (versão 1.5.1 e descrição apontando para `orc-hestrator-server`), sem nenhuma renomeação de distribuição, comando, env ou servidor. Tag `v1.5.1` nesse commit; o commit de renomeação vem depois e leva a tag `v2.0.0`.
- O `[Unreleased]` do CHANGELOG DEVE ser fechado como seção `[1.5.1]` antes do build — publicar com `[Unreleased]` aberto é proibido, e R7 proíbe reescrever entrada histórica.
- Registro explícito: por sair do estado pré-renomeação, a 1.5.1 carrega as correções de UI acumuladas. Ela não é "1.5.0 + metadados"; é "código da 2.0.0 sem a renomeação". A nota da release DEVE dizer isso.
- Ordem de publicação: 2.0.0 primeiro, 1.5.1 em seguida, nunca o inverso (R12).

Comandos canônicos: `uv run pytest -q` · `uv run ruff check` · `uv run ruff format --check` · `uv lock --check` (ou regeneração com a versão de uv do CI).

| Gate | Entrega | Resultado |
|------|---------|-----------|
| G2 Spec | este arquivo + ADR-006 | pronto |
| G0 Architect | mapa de arquivos/interfaces da renomeação | em curso |
| G3 RED | testes de nome, precedência de env e geração de TOOLS | feito — 14 failed / 253 passed, revisado |
| G4 GREEN | núcleo de código (pyproject, env, servidor, gerador) | feito — 267 passed |
| G4 docs/CI/deploy | README, llms.txt, CHANGELOG, pin de uv, deploy/ | em curso |
| G4.2 | metadados 1.5.1 + CHANGELOG fechado + tag `v1.5.1` (antes da renomeação) | pendente |
| G5 Review | reviewer reproduz AC1–AC4 por execução | pendente |
| G6 Validação | artefatos em venv limpo | feito — 2 defeitos achados |
| G6.1 Revalidação | wheel + venv limpo após `mcp<2` e guard do extra | GO |
| Commits | cinco commits por caminho explícito na main | feito (1877624, f17fe9f, 8dcf81b, e80477b, 4aced04) |
| G7 Release | revisão de publicacao: workflow, trusted publisher, projetos PyPI | pendente |

## G0 — achados e decisões (18/out, dois architect)

Estado medido: `uv run pytest -q` = 255 passed; `ruff check` limpo; `uv lock --check` exit 0 (uv 0.9.18).
`ruff format --check` na raiz falha por vírgula ausente em bloco Python de `docs/WORKSPACE-GUIDE.md:65`
(o CI só checa `src/ tests/`).

Fatos que a SPEC não previa e que ficam decididos:

- **`docs/TOOLS.md` já existe e já mente**: cabeçalho diz "generated from tools/list", contém 31 tools e
  declara 3 resources, mas o servidor registra 6 (3 base + 3 `/pt-br`). `llms.txt:30` repete 3. Não há
  gerador. O gerador do R5 deve contar 31 tools, 7 prompts e 6 resources, e ter modo `--check`.
- **Prompts só são registrados dentro de `main()`** (`server.py:1029`); o gerador não pode depender de
  `main()` — deve importar `server` e chamar `register_prompts(mcp)`.
- **`DB_PATH` é constante de módulo** (`db.py:14`, lida no import) e `workspace.py:8` congela o valor com
  `from .db import DB_PATH`. Todos os 255 testes isolam por mutação de `db.DB_PATH` (`conftest.py`).
  O resolvedor `ORC_DB → TASK_ORCHESTRATOR_DB → default` deve ficar num ponto único e a mutação de
  `db.DB_PATH` deve continuar funcionando, senão a suíte inteira cai.
- **`--db` da UI é inerte** (`ui/app.py:542` escreve env depois do import). Corrigir junto.
- **`importlib.metadata` em editable**: sem `uv sync` após o rename, o `.venv` mantém
  `task_orchestrator_py-1.5.0.dist-info` e `version("orc-hestrator-server")` levanta `PackageNotFoundError`,
  que o try/except da F1 disfarça em `"0.0.0"`. Ordem obrigatória: pyproject → `uv sync`/`uv lock` → testes.
- **Transporte**: hoje decidido por `MCP_TRANSPORT` em `main()`; os scripts novos decidem pelo entry point
  (ADR-007) e `MCP_TRANSPORT` fica como override.
- **Nenhum teste cobre `serverInfo.name`** — AC4 exige RED novo.
- **CI usa `setup-uv` sem pin de versão**; "regenerar uv.lock com o uv do CI" é alvo móvel. Decidido:
  pinar `version:` do `setup-uv` (0.9.18) no `ci.yml` e no `publish.yml` nesta fatia, para R13 ser verificável.
- **Docs já estão no estado-alvo, código não**: README/AGENTS/llms.txt/CONFIGURATION prometem `ORC_DB`,
  `orc`, `uvx orc-hestrator-server` e default `~/.orc/tasks.db`; o código usa `~/.task-orchestrator/tasks.db`.
- **Repositório GitHub renomeado em 18/out** (por mim, com `gh repo rename`): `filhocf/task-orchestrator-py`
  agora é `filhocf/orc-hestrator`, com 301 do nome antigo. Remote local atualizado. Consequência: o claim
  OIDC passa a usar o nome novo, então os trusted publishers do PyPI DEVEM ser registrados com
  Repository = `orc-hestrator`. O rename foi antecipado ao G3 de propósito, para o registro no PyPI ser
  feito uma vez só.
- **Default do banco decidido por Claudio (18/out): `~/.orc/tasks.db`**, com guarda de continuidade — se o
  caminho antigo existir e o novo não, usa o antigo e avisa uma vez. README/AGENTS/llms.txt deixam de estar
  adiantados em relação ao código.
- **`deploy/` só tem `nginx/`**: `orc.service` e `orc.env.example` (R11/AC9) não existem.
- **Testes e2e spawnam `uv run task-orchestrator-py`** (`test_onboarding.py:318,668`) e
  `pkg_version("task-orchestrator-py")` (`:344`): migrar para `orc`/`orc-serve` e manter um teste dedicado
  ao alias legado, senão a suíte passa a validar o alias em vez do script novo.


Mecânica da 1.5.1 (decidida antes de executar): a árvore de trabalho do main já contém a renomeação, então
a 1.5.1 não pode sair dela. Será criado um worktree a partir do HEAD pré-F7 (56b5818) em branch
`release/1.5.1`, com commit próprio contendo apenas metadados (versão 1.5.1, descrição apontando para
`orc-hestrator-server`, seção `[1.5.1]` do CHANGELOG com os itens que hoje estão em `[Unreleased]`), e a tag
`v1.5.1` nesse commit. A tag fica em um irmão do main, não em ancestral — o que importa para R12 é a ordem de
publicação (2.0.0 antes de 1.5.1), não a ancestralidade. Nada é mergeado de volta: o branch existe para o
build. Push do branch e da tag só no G7, porque tag `v*` dispara a publicação.

### Nome de distribuição — decisão de 18/out (não reabrir)

`orc-hestrator` é **impossível** no PyPI. A checagem do warehouse é
`ultranormalize(name) == ultranormalize(project.name)`, com `ultranormalize` removendo `. _ -`, trocando
`l|i` por `1` e `o` por `0`. Assim `orc-hestrator` → `0rchestrat0r`, idêntico ao projeto existente
`orchestrator`. Não há pending publisher nem upload que passe: é bloqueio duro.

Medido contra os 916.467 nomes do índice SIMPLE, também colidem: `orc-hestrator-mcp` (com
`orchestrator-mcp`), `orc-hestrator-mcp-server` (com `orchestrator-mcp-server`), `orc-hestrator-core`
(com `orchestrator-core`), `orc-hestrator-api` (com `orchestratorapi`).

Decidido por Claudio: distribuição = **`orc-hestrator-server`** (ultranormalizado `0rchestrat0rserver`,
sem colisão). O repositório GitHub permanece `orc-hestrator` e o site permanece `orc-hestrator.dev` —
a regra de ultranormalização é só do PyPI. Os comandos não mudam (`orc`, `orc-mcp`, `orc-serve`,
`orc-ui`, `orc-hestrator`); muda apenas o nome da distribuição.

## G5 — revisão adversarial (veredito CHANGES-REQUESTED, 18/out)

AC1–AC9 reproduzidos por execução: todos PASSAM. Nenhum P0. Dois P1 com causa raiz comum — o nome da
distribuição usado como se fosse comando executável — e um P2 aceito como defeito real:

- **P1-1 — onboarding ensina comando inexistente.** `uv run orc-hestrator-server` falha (exit 2, "Failed
  to spawn"); o stdio que funciona é `uv run orc`. Origem: erro nesta SPEC, que aprovou a string errada em
  R8. Ciclo curto: teste corrigido primeiro (RED), depois o texto.
- **P1-2 — `uvx orc-hestrator-server` não resolve.** O `uvx <nome>` procura console script homônimo; os
  scripts criados foram `orc-hestrator`, `orc`, `orc-mcp`, `orc-serve`, `orc-ui` — nenhum com o nome da
  distribuição. Correção escolhida: ACRESCENTAR o script `orc-hestrator-server` em stdio (é o que R2.1 já
  mandava: "só funciona com script homônimo à distribuição"), em vez de reescrever README/llms.txt/site
  para `uvx --from orc-hestrator-server orc`. Uma linha de pyproject resolve os três documentos.
- **P2-1 — guarda de continuidade dispara no import.** `scripts/generate_tools_doc.py` emite o aviso de
  banco legado só por importar `server`→`db`. Correção: a guarda passa a rodar no primeiro uso do banco
  (`init_db`/primeira conexão), não na carga do módulo; `DB_PATH` mantém o valor resolvido puro.
- **P2-2 (`orc --help` sem help)** e **P2-3 (`ruff format --check` na raiz falha em
  docs/WORKSPACE-GUIDE.md:65)** — o primeiro fica como está (entry stdio puro, sem argparse); o segundo é
  dívida pré-existente que será corrigida junto, porque AC6 fala de "limpo" e não de "limpo em src/ tests/".

Confirmado como correto por execução, apesar de teste verde não provar: aviso de deprecação de env único em
múltiplas conexões; `--db` da UI realmente troca o banco; `uv.lock` sem nomes legados; onboarding sem typo de
transporte; nenhuma asserção enfraquecida em `git diff tests/`; nenhum resíduo no repo.

## G6 — validação em ambiente limpo (18/out): dois defeitos de artefato

Os dois artefatos compilam, instalam fora do checkout e têm entry points/metadados corretos, mas o teste em
venv limpo encontrou o que o checkout escondia:

- **P0 — `mcp>=1.0.0` resolve mcp 2.x e mata todos os entry points.** Em instalação limpa, `mcp` virou 2.3.0,
  onde `mcp.server.fastmcp` não existe (FastMCP renomeado para MCPServer). `import` falha com
  ModuleNotFoundError em qualquer script. No checkout nada aparece porque o `uv.lock` pinou 1.27.0 — e o pin do
  lock NÃO entra no METADATA do wheel. Correção: teto de major, `mcp>=1.0.0,<2`, nos DOIS artefatos (a 1.5.1
  publicada sofreria o mesmo defeito; no worktree o commit aebbb46 é local, então será emendado e a tag
  `v1.5.1` reapontada).
- **P1 — `orc-serve` exige `fastapi`, que vive no extra `ui`.** Instalação só-core instala os scripts mas o
  transporte streamable-http morre no import de `fastapi`. Decisão: manter o extra (não inflar quem só usa
  stdio), documentar o caminho HTTP como `uvx --from 'orc-hestrator-server[ui]' orc-serve` e fazer `orc-serve`
  falhar com mensagem clara quando o extra faltar, em vez de traceback cru.
- P2 aceito: `pydantic_settings` emite IncompleteFieldDefinitionWarning no stderr de todos os entry points.
  Terceiro, fora do nosso controle; AC2 continua válida (1 linha de deprecação no legado, 0 no orc-mcp).

Provado como correto no limpo: wheel sem tests/.venv/docs, 8 scripts na 2.0.0 e 2 na 1.5.1, versões 2.0.0 e
1.5.1 nos metadados, `serverInfo.name` = 'orc' na 2.0.0 e 'task-orchestrator' na 1.5.1, entry points da 1.5.1
sem nenhum nome novo, descrição da 1.5.1 apontando para `orc-hestrator-server`.

## G7 — revisão de release (depois da fatia fechada)

Objetivo: fechar o que falta para publicar sem improviso. Levantamento feito em 18/out sobre o estado real:

Já existe:
- `.github/workflows/publish.yml` dispara em tag `v*`, roda `uv build` e `uv publish --trusted-publishing always`, com `permissions: id-token: write`. Ou seja, OIDC já está no caminho; não há token secreto.
- `gh` autenticado como `filhocf` com escopos `repo`, `workflow`, `write:packages`.

Pendências a resolver nesta revisão:
1. Projeto `orc-hestrator-server` no PyPI não existe (o nome `orc-hestrator` é impossível: colide por
   ultranormalização com `orchestrator`). Criar um *pending trusted publisher* (conta → Publishing → Create a new pending publisher) com repositório, workflow `publish.yml` e ambiente. Atenção: pending publisher NÃO reserva o nome; se outro usuário registrar `orc-hestrator` antes do primeiro upload, o publisher é invalidado.
2. Registrar/ajustar o trusted publisher do projeto antigo `task-orchestrator-py` para publicar a 1.5.1. Se o repositório GitHub for renomeado antes, os claims do OIDC passam a refletir o nome novo — verificar por execução qual nome o PyPI espera, e usar a 1.5.1 como canário (é a release de menor risco para descobrir `invalid-publisher`).
3. `publish.yml` usa `actions/checkout@v7` e `astral-sh/setup-uv@v7` em tag flutuante, enquanto `ci.yml` fixa SHA. Padronizar por SHA no workflow de release.
4. O workflow não valida que a tag corresponde à versão do `pyproject.toml`, não usa `environment:` de proteção e não anexa atestação de proveniência. Avaliar `pypa/gh-action-pypi-publish` (suporta atestação) ou manter `uv publish` e justificar.
5. Qualquer tag `v*` publica. Definir se 1.5.1 e 2.0.0 saem por tag manual (recomendado) e documentar a sequência no `docs/SITE.md`/release notes.