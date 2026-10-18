# Fábrica agêntica → funcionalidades do Orc

Consolidação de três fontes: o curso TLC IA First (23 aulas em `conhecimentos-de-ia/cursos/`),
os resumos do workshop TLC avançado (onde o termo "fábrica agêntica" aparece, no bloco do
Waldemar), o painel de 13 papéis do próprio Orc, e as medições que fiz como cliente do produto.
Cada featur tem a origem marcada para não confundir autoridade de evidência.

## O que as fontes sustentam

| Origem | Afirmação que decide produto |
|---|---|
| Curso, aula 11 e 13 | "não é a IA que julga se terminou": gate com saída binária de comando, não julgamento do modelo |
| Curso, aula 21 | "o agente principal não decide o que fazer a seguir — o harness decide"; agentes leem e escrevem estado compartilhado, não conversam entre si |
| Curso, aula 12 | Sweet spot de subagentes: 3 workers para 17 tasks; agrupar por fase, nunca por task; baseline sem subagente consome 74% da janela |
| Curso, aula 10 e 12 | Janela como métrica: Smart Zone até 40%, Dumb Zone acima de 60% |
| Curso, aula 20 | "pequenas o suficiente para um agente terminar sozinho sem pisar no pé de outro"; arrastar para "in progress" dispara agente |
| Workshop, d1t | "A entrada da fábrica é um problema, a saída é software funcionando com testes"; "o Jira/task tracker quase morreu e voltou" como ponto de entrada |
| Workshop, d2m | "WIP limit não é mais sobre capacidade do humano, é sobre a atenção dele" |
| Painel Orc, síntese §73-79 | Kanban nativo; Scrum/SAFe como perfil opcional; XP como gates + co-claim |
| Painel Orc, voz 11 | WIP por tipo de ator e métricas de fluxo emitidas por evento |
| Medição própria (18/out) | Uma listagem default custa 7.483 tokens; `get_context` custa 1.690; item carrega 22 campos e 598 caracteres |

## Funcionalidades

Numeração contínua com as fatias já abertas. Prioridade por impacto sobre o agente consumidor,
não por facilidade.

| ID | Funcionalidade | Origem | Impacto | Custo | Versão |
|---|---|---|---|---|---|
| F9.1 | Projeção nas leituras (`compact` default, `fields`) | medição própria | −75% por listagem | baixo | 2.1.0 |
| F9.2 | `session_brief(session_id, since)` ≤1.500 chars | própria + aula 21 (estado compartilhado) | −60% no início de sessão | médio | 2.1.0 |
| F9.3 | `updated_since` nas leituras | própria | custo constante ao retomar | baixo | 2.1.0 |
| F10.1 | Trilha como tipo de primeira classe; fim da convenção por tag | conceito do dono + código atual | o agente pode pedir a trilha | médio | 2.2.0 |
| F10.2 | Guarda de pai terminal: pai não fecha com filho aberto | medição própria (furo comprovado) | `done` vira fato verificável | baixo | 2.2.0 |
| F10.3 | `track_brief`, `next_in_track`, `track_graph(compact)` | conceito do dono + aula 21 | substitui leitura do board inteiro | médio | 2.2.0 |
| F11.1 | WIP limite por coluna **e por tipo de ator**, imposto pelo servidor | painel voz 11 + workshop d2m | impede agente entupir a revisão humana | baixo | 2.3.0 |
| F11.2 | Métricas de fluxo derivadas de evento (lead, cycle, CFD) | painel voz 11 | board honesto sem digitação | baixo | 2.3.0 |
| F11.3 | Scrum/SAFe como perfil de política e lente, nunca campo do item | painel §73-79 | evita cerimônia sem conteúdo | médio | 2.3.0 |
| F11.4 | XP como co-claim e gate de revisão por papel | painel §77 | par humano+agente nativo | baixo | 2.3.0 |
| F12.1 | Gate por **evidência** (arquivo:linha ou saída de comando), re-checável | curso 11, 13, 21 | o relato do agente deixa de ser prova | médio | 2.4.0 |
| F12.2 | Veredito de validador independente gravado como evidência do gate | curso 16, 17 + workshop d1t | separa quem faz de quem julga | médio | 2.4.0 |
| F12.3 | Triagem com limiar de confiança na entrada da fábrica | workshop d1t (fábrica V2) | humano só acima do limiar | alto | 2.5.0 |
| F12.4 | Claim como gatilho de evento de primeira classe | curso 20 | automação substitui disciplina | médio | 2.4.0 |
| F13.1 | Orçamento de contexto por item/agente, com zona (≤40% / >60%) | curso 10, 12 | evita o colapso silencioso da sessão | médio | 2.5.0 |
| F13.2 | Peso de leitura estimado por item, para o orquestrador decidir subagente | curso 12 (150k tokens) | delegação dimensionada por dado | médio | 2.5.0 |
| F13.3 | Guarda de dimensionamento: item acima do limiar não avança sem plano escrito | workshop d1t (~1,5 semana-pessoa) | evita "chutar solução" | baixo | 2.4.0 |
| F13.4 | Parâmetros nativos em vez de `*_json`; verbos pequenos em vez de tool-deus | própria | menos erro e menos schema lido | baixo | 2.1.0 |
| F13.5 | Endpoint `/mcp-read` para subagente | aula 12 + própria | −70% de catálogo no worker | médio | 2.2.0 |

## O que as fontes não tratam — e onde o Orc já está à frente

Não encontrado em nenhuma fonte: custo de catálogo de tools em tokens, resolução de conflito de
escrita entre agentes concorrentes, presença multi-máquina, atribuição por request, e gate como
nota estruturada do produto. São diferenciais do Orc, e por isso não têm respaldo externo — o que
também significa que não devem ser vendidos como consenso da indústria.

## Divergência honesta com o curso

O curso questiona o TDD RED-first obrigatório: "não faz sentido forçar o agente a escrever teste
antes (gasta tokens, ele dá skip)". A nossa prática hoje impõe RED antes do GREEN, e ela pegou
defeitos reais nesta sessão. A reconciliação que proponho: o gate não é "existiu um teste vermelho",
é "existe prova que falha sem a correção e passa com ela". O RED continua sendo o caminho mais
barato de obter essa prova, mas o critério vira a prova, não o ritual.

## Ordem de execução

2.1.0 = F9 (ergonomia, primeiro porque muda o default de leitura e barateia tudo o resto).
2.2.0 = F10 (trilha e guarda de pai terminal) + F13.5.
2.3.0 = F11 (perfis de método).
2.4.0 = F12.1, F12.2, F12.4, F13.3 (gate por evidência e validador independente).
2.5.0 = F12.3 e F13.1-2 (triagem por confiança e orçamento de contexto) — os dois mais caros e
os que dependem de instrumentação já existir.
