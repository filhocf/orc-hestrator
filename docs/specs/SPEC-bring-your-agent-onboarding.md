# SPEC — Bring Your Agent, fatia F1: servidor que se explica

Status: especificada, aguardando RED.
Escopo: `src/task_orchestrator/onboarding.py` (novo), `src/task_orchestrator/server.py`,
`src/task_orchestrator/prompts.py`, testes em `tests/`.

## Contexto

O Hermes não injeta `initialize.instructions` no contexto do modelo e não consome `prompts/*`
sozinho (verificado no cliente MCP do Hermes em 18/out). Um agente recém-instalado, portanto, não
sabe como usar o Orc. O mms resolve isso com `get_onboarding_guide`; o Orc precisa do equivalente.

## Requisitos (EARS)

R1. O servidor DEVE expor a tool `orc_onboarding(client_type: str = "hermes")`, somente leitura,
    que devolve texto em português com as seções: `modelo`, `ciclo_de_sessao`, `verbos`,
    `gates`, `antipadroes`, `exemplos`.
R2. `client_type` DEVE aceitar `hermes`, `kiro` e `cli`. Valor desconhecido DEVE cair no genérico
    sem erro, e o texto DEVE informar qual variante foi servida.
R3. O texto DEVE conter, no mínimo: os quatro status (`queue`, `work`, `review`, `done`); os seis
    triggers (`start`, `complete`, `block`, `resume`, `cancel`, `reopen`); a regra "registre a
    sessão antes de trabalhar"; a regra "faça claim antes de pegar um item"; a proibição de criar
    item sem buscar antes por título semelhante.
R4. O texto DEVE caber em 6.000 caracteres. Custo de contexto é requisito, não estética.
R5. O servidor DEVE expor três resources MCP estáticos: `orc://onboarding`, `orc://workflow`,
    `orc://glossary`, cujo conteúdo DEVE ser legível por `resources/read` e coerente com R3.
R6. `initialize` DEVE reportar em `serverInfo.version` a versão do pacote
    (`importlib.metadata.version("task-orchestrator-py")`), e não a versão do SDK MCP.
R7. A variante `hermes` DEVE incluir as instruções de conexão relevantes ao Hermes: identidade por
    `identity_header` (`X-Agent-ID`, `value_from: profile`), auth por header e recorte de tools
    (`nucleo`/`leitura`/`completo`), remetendo a `docs/BRING-YOUR-AGENT.md`.
R8. Nenhuma das rotas novas DEVE exigir banco populado: com banco vazio a tool e os resources
    respondem normalmente.
R9. Internacionalização (decisão de Claudio, 18/out): o produto é i18n desde a fundação, com
    inglês como idioma canônico e português do Brasil como segundo. A tool DEVE aceitar
    `lang` (`"en"` padrão, `"pt-BR"`), e a resolução de idioma DEVE seguir a precedência:
    argumento explícito → env `ORC_LANG` → header `Accept-Language` (só transporte HTTP) →
    `en`. Idioma não suportado DEVE cair em `en` sem erro.
R10. A **estrutura** do texto é invariante de idioma; a **prosa** é localizada. Os marcadores de
     seção são identificadores fixos em inglês nas duas línguas: `model`, `session_cycle`,
     `verbs`, `gates`, `antipatterns`, `examples`. Os marcadores `variant: <nome>` e
     `lang: <código>` também são invariantes e DEVEM declarar o que foi servido.
R11. Cada combinação de variante × idioma DEVE respeitar o teto de 6.000 caracteres.
R12. Os resources DEVEM oferecer o idioma canônico e o segundo idioma:
     `orc://onboarding`, `orc://onboarding/pt-br`, e o mesmo par para `workflow` e `glossary`.
     O URI sem sufixo serve o idioma resolvido pela precedência do R9 (padrão `en`).

## Critérios de aceite (verificáveis)

AC1. `tests/test_onboarding.py::test_tool_returns_sections` — chamada direta devolve as seis seções.
AC2. `test_client_types` — `hermes`, `kiro`, `cli` e `desconhecido` retornam sem exceção; a
     variante servida aparece no texto.
AC3. `test_length_budget` — `len(texto) <= 6000` para as três variantes.
AC4. `test_required_terms` — status, triggers, sessão, claim e a regra antiburrice estão presentes.
AC5. `test_resources_registered` — `list_resources` devolve os três URIs e `read_resource` devolve
     conteúdo não vazio para cada um.
AC6. `test_server_version` — `serverInfo.version == importlib.metadata.version(...)`, provado por
     cliente MCP real em subprocesso (não por leitura de atributo).
AC7. `test_empty_db` — com `TASK_ORCHESTRATOR_DB` em `tmp_path`, tool e resources respondem.
AC8. Suíte existente continua verde (`pytest -q`), `ruff check` e `ruff format --check` limpos.
AC9. O teste do AC6 DEVE usar `tmp_path` para o banco do subprocesso e não deixar nenhum
     artefato (`*.db`) no diretório do repositório após a execução.
AC10. `test_i18n_sections` — as seis seções aparecem com os mesmos marcadores invariantes
      (`model`, `session_cycle`, `verbs`, `gates`, `antipatterns`, `examples`) tanto em `en`
      quanto em `pt-BR`.
AC11. `test_lang_resolution` — precedência completa: argumento vence env; env vence o default;
      idioma desconhecido cai em `en`; o texto declara `lang: <código>` servido.
AC12. `test_len_budget_all_langs` — variante × idioma (4 × 2) dentro de 6.000 caracteres.
AC13. `test_resources_per_lang` — os seis URIs (`orc://onboarding`, `/pt-br`, e o par para
      `workflow` e `glossary`) listados e legíveis, com prosa no idioma certo.
AC14. `test_prose_is_localized` — a prosa difere entre idiomas enquanto os marcadores são
      idênticos (prova de que a localização não vazou para a estrutura).
AC15. O header `Accept-Language` DEVE ser coberto por teste de transporte HTTP real (subprocesso +
      cliente MCP ou requisição direta): com `Accept-Language: pt-BR` e sem `lang` nem `ORC_LANG`,
      a variante servida declara `lang: pt-BR`. In-process esse caminho não existe.
AC16. Os resources de URI base (`orc://onboarding`, `orc://workflow`, `orc://glossary`) DEVEM
      honrar o `Accept-Language` no transporte HTTP, servindo a prosa do idioma resolvido; sem
      header, servem inglês. Provado por cliente MCP real com headers. Adicionalmente: `ORC_LANG`
      vence o header, e em contexto não-HTTP o header é ignorado sem erro.

## Refinamentos pós-G5 (2ª rodada)

- **R7 exige o recorte de tools apenas na variante `hermes`**, e como **configuração do cliente**,
  não do servidor: o servidor não filtra tools. As variantes `kiro`, `cli` e `generic` NÃO DEVEM
  mencionar `nucleo`/`leitura`/`completo`.
- A variante `cli` DEVE avisar que o transporte `streamable-http` exige o extra `ui`
  (`uv sync --extra ui`); sem `fastapi` o processo morre com `ModuleNotFoundError`. A guarda com
  mensagem amigável no `main()` pertence à F4.
- A variante `hermes` DEVE distinguir os dois esquemas de credencial: `Bearer` quando o OAuth2 do
  servidor está ligado, `Basic` na borda do proxy reverso.

## Resoluções do G3.1 (validar com o RED atual)

1. AC3 (3 variantes, ≤6.000) PASSA contra a implementação pré-i18n por ser caso particular do
   AC12 — o RED do teto vive no AC12. Não force AC3 a falhar artificialmente.
2. AC12 só é RED se cada célula da grade 4×2 declarar `variant:` e `lang:` corretos; um teste que
   apenas meça comprimento passaria devolvendo o mesmo texto em todas as células.
3. AC13 usa a regra de sessão como discriminador de idioma em **todos os seis** URIs —
   `before working` em inglês, `antes de trabalhar` em pt-BR — logo workflow e glossary DEVEM
   conter essa regra nos dois idiomas.
4. Discriminadores de prosa usam substring de frase; identificadores (status, triggers) usam
   fronteira de palavra.
5. AC7 verifica a presença do URI em `list_resources` antes de `read_resource`, para falhar por
   asserção limpa e não por `Unknown resource`.

## Interface fixada no G3 (após revisão do RED)

O worker de testes assumiu itens de contrato; ficam fixados para o GREEN implementar sem margem
de interpretação:

- Marcadores de seção, `variant:` e `lang:` são invariantes de idioma e ficam em inglês nas duas
  línguas (R10). Isto substitui a decisão anterior de tokens em português, tomada antes da
  decisão de i18n.
- A variante servida aparece como `variant: <nome>`; valor desconhecido é servido como
  `generic`.
- Regras do R3 são checadas por semântica de cada idioma: em `en`, `session` + `before working`,
  `claim`, `search before` + `title`; em `pt-BR`, `sessão` + `antes de trabalhar`, `claim`,
  `buscar antes` + `título`. Status e triggers são identificadores e não se traduzem, checados
  com fronteira de palavra (case insensível).
- AC4 é verificado na variante padrão (`hermes`) e no idioma canônico (`en`).
- AC6 usa deadline de 45 s para o handshake, dentro do orçamento de 60 s do teste.

## Não escopo desta fatia

- Hook/provedor de injeção de contexto (F5).
- Auth de produção e credencial da VPS (F0).
- Qualquer escrita em banco; nenhuma tool nova além de `orc_onboarding`.

## Diário de gate

| Gate | Entrega | Resultado |
|------|---------|-----------|
| G2 Spec | este arquivo | pronto |
| G3 RED | testes AC1–AC7 (7) | 7 failed, 242 passed — RED correto |
| G4 GREEN | onboarding PT-only, 3 resources (superado pela decisão de i18n) | 249 passed; 1º parecer G5 aprovou com nits |
| G3.1 RED | contrato i18n (AC10–AC14) | 10 failed, 2 passed (AC3 e AC6 passam legitimamente) |
| G4.1 GREEN | i18n en/pt-BR, 6 resources, `-> str`, versão resistente | 254 passed |
| G4.2 Fix | resources de URI base honravam o header? não — corrigido | 255 passed |
| G4.3 Fix | recorte de tools só na hermes, aviso de extra `ui`, Bearer/Basic | 255 passed |
| G5 Review | parecer adversarial independente (2ª rodada) | **APPROVED-WITH-NITS**, sem P0/P1 |
| G6 Validação | verificações do gerente: suíte, ruff, cliente real HTTP, matriz 4×2 | 255 passed; 8 células entre 2.016 e 2.293 chars |
| G7 Publicação | commit + push | pendente de aval |

### Dívida registrada nesta fatia

- P2-1 → F4: mensagem amigável no `main()` quando o transporte HTTP é pedido sem `fastapi`.
- P2-3 → F7: regenerar `uv.lock` com a versão de `uv` do CI (o local escreve `revision = 3`).
- P2-4 parcial: AC7 discrimina pouco contra R8; `claim`/`session` como substring casariam sozinhos.
  Os discriminadores fortes são `before working` / `search before`.

## Decisões fixadas (não reabrir)

- Texto do onboarding tem inglês como idioma canônico e pt-BR como segundo (R9, decisão de
  18/out); a redação anterior em PT-BR foi superada pela decisão de i18n e não deve ser reaberta.
- Resources estáticos (sem DB) para não acoplar onboarding a estado.
- Versão vem de `importlib.metadata`, não de constante no código.
