# SPEC — F7: renomeação para orc-hestrator

Status: especificada. Executa depois de F1 fechar o G5 (evita corrida nos mesmos arquivos).
Decisão registrada em `docs/adr/ADR-006-rename-orc-hestrator.md`.

## Requisitos (EARS)

R1. `pyproject.toml` DEVE declarar `name = "orc-hestrator"`, manter a versão corrente do pacote e
    remover a afirmação de "port" das descrições de metadados.
R2. Os scripts de console DEVEM incluir `orc` (servidor MCP) e `orc-ui` (UI), além de
    `orc-mcp` como alias explícito de stdio. Os scripts legados `task-orchestrator-py` e
    `task-orchestrator-ui` DEVEM continuar existindo como alias e DEVEM emitir aviso de
    deprecação em stderr ao serem usados.
R3. As variáveis de ambiente primárias passam a ser `ORC_DB`, `ORC_CONFIG` e `ORC_LANG`. As
    antigas (`TASK_ORCHESTRATOR_DB`, `TASK_ORCHESTRATOR_CONFIG`) DEVEM continuar funcionando como
    fallback, com as novas tendo precedência e um aviso único de deprecação no log.
R4. O servidor FastMCP DEVE reportar `name = "orc"` em `initialize`, mantendo a versão vinda de
    `importlib.metadata` (R6 da F1).
R5. `docs/TOOLS.md` DEVE ser gerado por script a partir de `tools/list` do servidor, de modo que
    contagem e nomes de tools nunca sejam digitados à mão. O script DEVE falhar com código de
    saída diferente de zero se o arquivo em disco divergir do servidor.
R6. O README DEVE apresentar o lockup `Orc[hestrator]`, a distribuição `orc-hestrator`, o comando
    `orc`, e uma única linha de origem: "formerly published as task-orchestrator-py".
R7. `CHANGELOG.md` DEVE registrar a renomeação em uma entrada própria; nenhuma entrada histórica
    DEVE ser reescrita.
R8. O texto de onboarding (F1) DEVE ensinar os comandos novos (`uv run orc-hestrator`, `orc`).
R9. CI DEVE rodar com o nome novo de distribuição; o workflow não pode depender do nome antigo.
R10. O transporte DEVE ser escolhido pelo ponto de entrada, não pela variável de ambiente
     (ADR-007): `orc` abre em stdio, `orc-serve` abre em `streamable-http` usando `MCP_PORT`.
     `MCP_TRANSPORT` permanece como override para testes e casos de borda.
R11. O repositório DEVE versionar o deploy em `deploy/`: unit systemd de usuário cujo `ExecStart`
     chama `orc-serve`, e um `orc.env.example` com as variáveis necessárias. Nenhum artefato de
     deploy DEVE continuar existindo apenas numa máquina.

## Critérios de aceite

AC1. `pip install -e .` (ou `uv sync`) instala e expõe `orc` e `orc-ui`; `orc --help` responde e
     `which orc` aponta para o venv/ambiente ativo.
AC2. `orc-mcp` e `task-orchestrator-py` sobem o servidor em stdio; o segundo imprime aviso de
     deprecação em stderr e o primeiro não.
AC3. `ORC_DB` vence `TASK_ORCHESTRATOR_DB` quando ambos estão definidos (provado por execução, com
     dois bancos distintos e verificação de qual arquivo foi criado).
AC4. `tools/list` via cliente MCP real devolve `serverInfo.name == "orc"` e
     `serverInfo.version == importlib.metadata.version("orc-hestrator")`.
AC5. `docs/TOOLS.md` gerado bate com `tools/list`; adulterar o arquivo à mão faz o script falhar.
AC6. `pytest -q` verde, `ruff check` e `ruff format --check` limpos.
AC7. `grep -rn "task-orchestrator-py"` no repositório devolve apenas: CHANGELOG histórico, a linha
     "formerly published as" do README, o alias de script e o teste do aviso de deprecação.
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

| Gate | Entrega | Resultado |
|------|---------|-----------|
| G2 Spec | este arquivo + ADR-006 | pronto |
| G3 RED | testes de nome, precedência de env e geração de TOOLS | pendente |
| G4 GREEN | pyproject, compat shims, gerador, docs | pendente |
| G5 Review | reviewer reproduz AC1–AC4 por execução | pendente |
| G6 Validação | suíte + instalação limpa em venv novo | pendente |
