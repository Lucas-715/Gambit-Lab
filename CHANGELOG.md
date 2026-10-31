# Changelog — Gambit Lab

Todas as mudanças relevantes deste projeto são documentadas neste arquivo.

## [2.3.1-traceability] — 2026-10-31

### Adicionado
- **Rastreabilidade Ponta a Ponta no Painel 'Lance Selecionado'**:
  - População automática do painel no carregamento da partida (`loadMatchAndPieces`) com o último lance do timeline, eliminando o painel em branco.
  - Sincronização estrita de todos os lances (`selectMoveByPly`), exibindo número do lance, notação SAN, peça ativa, coordenadas, tese, citação literal, status de verificação e captura física.
  - Estado inicial pré-jogo limpo e informativo quando o cursor de replay está no início (`ply = 0`), com desativação apropriada dos botões de recuo.
- **Alinhamento Matemático de Coordenadas em 2D e Projeção em 3D**:
  - **Modo 2D**: Reestruturação completa com CSS Grid (`.board-2d-inner`) de alinhamento 1:1 entre as células do tabuleiro e os rótulos de fileiras (`8..1`) e colunas (`a..h` no Xadrez, `A..J` sem `I` no Go 9×9).
  - **Modo 3D**: Overlay em HTML5 Canvas (`#stageCoordsOverlay`) sincronizado com o WebGL através da projeção geométrica da matriz de visualização e perspectiva (`vp`).
- **Inspeção Interativa por Clique na Casa**:
  - Clique em qualquer casa do tabuleiro abre modal de inspeção com busca no histórico da partida e botão direto para inspecionar o lance correspondente no painel "Lance Selecionado".
- **Esquema de Estado e Sequenciamento de Eventos**:
  - Campo `status` (`NOT_STARTED`, `IN_PROGRESS`, `COMPLETED`, `BUDGET_EXHAUSTED`) integrado a `ResearchMatchStateSchema`.
  - Campo `move_event_seq` persistido em `MatchPlyRecordSchema` e `MoveAuditPayloadSchema` para mapeamento bidirecional exato com o `EventStore`.

### Corrigido
- **Honestidade Científica nas Citações e Vereditos**:
  - Distinção transparente entre citação verificada no arquivo ("✓ Citação verificada no arquivo") e citação anexada sem verificação ("⚠️ Citação anexada; relevância semântica pendente").
  - Capturas físicas nunca falsificam veredito factual como `REFUTED`, mantendo `INCONCLUSIVE` ou `NOT_ASSESSED`.
- **Prevenção de Erros de Referência nula no DOM**:
  - Proteção de todos os acessos a elementos do DOM removidos ou reestruturados no redesign v2.3 (`topModeBadge`, `countChat`, `countAudit`, `countHistory`), garantindo que o ciclo de 7 estágios execute sem interrupções.

## [2.3.0-focus] — 2026-10-31

### Adicionado
- **Workspace Nocturne Focus ("Xadrez/Go primeiro, lance e evidência depois")**:
  - Painel contextual único **LANCE SELECIONADO** sincronizado instantaneamente ao cursor de replay, seleção no tabuleiro ou término de lance.
  - Exibição de movimento auditável: SAN/UCI (`20...Nxd3`), peça ativa, papel tático, tese, fonte documental, trecho literal, contestação do oponente (em capturas), status físico (`Captura`, `Xeque`, `Mate`) e avaliação factual do árbitro.
  - Moldura com rótulos externos visíveis em 2D e 3D: Xadrez `a–h` e `1–8`; Go 9×9 `A B C D E F G H J` (sem a letra `I`) e `1–9`.
  - Topbar minimalista e menu modal **⚙ Diagnóstico & Estado** reunindo métricas globais, telemetria Gemini, status da Pesquisa Web e verificação de cadeia SHA-256.
  - Sidebar retrátil (`.rail.collapsed`) no desktop e drawer responsivo com navegação por teclado (ESC) no mobile.
- **Payload de Lance Auditável (`MoveAuditPayloadSchema`)**:
  - Estrutura padronizada no timeline contendo `session_id`, `ply`, `game`, `move`, `piece`, `opponent`, `evidence`, `argument_verdict`, `board_outcome`, `event_seq` e `event_hash`.
- **Privacidade Estrita de Dossiês Não Jogados (`C12` / `SEC01`)**:
  - `GET /api/v1/sessions/{id}/pieces` aplica controle por papéis (`owner`, `white`, `black`, `observer`). Dossiês de peças que ainda não jogaram no tabuleiro permanecem reservados como `[reservada — ainda não jogada no tabuleiro]`, protegendo o isolamento de estratégias.
- **Suíte de Testes Epistêmicos v2.3 (`tests/integration/test_v23_epistemic_audit.py`)**:
  - Cobertura automatizada para os achados C01 a C12 e cenários UX01 a UX07. Total da suíte do repositório elevado para **90 testes aprovados (`90 PASSED, 0 FAILED`)**.

### Corrigido
- **Separação entre Trecho Localizado e Suporte Epistêmico (`C01`)**:
  - A localização literal de uma citação em um documento atribui `SOURCE_VERIFIED`, e **NÃO** `SUPPORTED` automático. Uma definição (ex.: "propriedade privada") não é promovida a prova de teses normativas fortes (ex.: "superioridade universal") sem avaliação semântica.
- **Desacoplamento entre Captura Física e Refutação Factual (`C02`)**:
  - Capturar uma peça no tabuleiro (`PIECE_CAPTURED` / `STONES_CAPTURED`) não altera o veredito da alegação para `REFUTED`. Registra honestamente `NOT_ASSESSED` ou `INCONCLUSIVE`.
- **Deduplicação de Fontes e Eliminação de Multiplicadores de Verdade por Peça (`C03`)**:
  - Remoção de multiplicadores de verdade (`ROLE_EPISTEMIC_WEIGHTS` onde Rei valia 2.6x e Dama 2.3x). A unidade epistêmica é a alegação independente deduplicada por DOI/URL/hash de conteúdo. Múltiplos peões repetindo a mesma fonte pontuam de forma unitária.
- **Resignação Automática Desabilitada por Padrão no Xadrez (`C04`)**:
  - Resignação automática após 800cp por 3 turnos desabilitada por padrão (`DEFAULT_AUTO_RESIGN = False`). O motor segue as regras FIDE oficiais (xeque-mate formal, afogamento, tripla repetição, regra dos 50 lances e material insuficiente). Quando resignação explícita ocorre, é rotulada estritamente como `resignation`, jamais como xeque-mate.
- **Legalidade Estrita FIDE sem Bloqueio de Capturas no Modo Padrão (`C05`)**:
  - O portão epistêmico de bloqueio foi desativado no modo FIDE padrão (`epistemic_gating_enabled = False`), garantindo que capturas legais permaneçam legais e que o confronto epistêmico ocorra em paralelo.
- **Estados Epistêmicos Discretos e Remoção de Probabilidades Arbitrárias (`C09`)**:
  - Eliminação de pontuações arbitrárias flutuantes (`.82`, `.88`). Adoção de estados discretos calibrados: `UNVERIFIED`, `SOURCE_VERIFIED`, `EVIDENCE_REVIEWED`, `SUPPORTED`, `REFUTED`, `INCONCLUSIVE`.

## [2.1.0-nocturne] — 2026-10-31

### Adicionado
- **Endpoint de Capacidades (`GET /api/v1/capabilities`)**: Expõe disponibilidade real do Google Gemini, status da Pesquisa Web pública, políticas suportadas (`OWN_ONLY`, `WEB_ONLY`, `HYBRID`), modos de execução (`DEMO_OFFLINE`, `LIVE_DOCUMENTS`, `LIVE_WEB`, `LIVE_HYBRID`) e orçamento padrão de etapas.
- **Adaptador de Pesquisa Web Auditável com Anti-SSRF (`services/api/agents/web_search_adapter.py`)**:
  - Busca pública HTTPS via Wikimedia/Wikipedia e OpenAlex + endpoint manual `POST /api/v1/sessions/{id}/artifacts/web-snapshot`.
  - Validação anti-SSRF estrita bloqueando esquemas não-HTTPS, portas diferentes de `443`, `localhost`, loopback, IPs privados RFC 1918, CGNAT, link-local, endpoint de metadados em nuvem (`169.254.169.254`) e redirecionamentos maliciosos.
  - Persistência de `SourceRecord` no `DocumentVault` com URL canônica, domínio, timestamp UTC e hash `SHA-256`.
- **Orquestração Contínua de Turnos (`POST /api/v1/sessions/{id}/advance`)**:
  - Suporte a investigações contínuas de 10+ lances legais tanto em Xadrez 8×8 quanto em Go 9×9 (orçamento configurável `max_steps`, padrão `12`, até `60`).
  - Suporte a `Idempotency-Key` e controle de concorrência otimista via `expected_version` (`HTTP 409 Conflict`).
  - Controles operacionais de sessão: `POST /pause`, `POST /resume` e `POST /cancel`.
  - Método `GoEngine9x9.get_legal_moves()` para geração determinística de interseções válidas respeitando proibição de suicídio e superko posicional.
- **Replay Histórico Parcial Determinístico (`GET /api/v1/sessions/{id}/replay?up_to_seq=N`)**: Reconstrói tabuleiro, contadores (`ply_count`, `investigation_step_index`), claims e julgamentos em qualquer ponto da cadeia de eventos com **zero chamadas ao LLM**.
- **Interface Visual Gambit Lab Nocturne (`apps/web/index.html`)**:
  - Nova identidade de alto contraste (`--bg: #040405`, `--panel: #0B0C0F`, `--accent: #A68DFF`) com alternância opcional para o tema `Cosmic`, preservando 100% da renderização WebGL 3D procedural nativa e o tabuleiro 2D Acessível (WCAG AA).
  - Separação clara entre barra de execução (**`▶ Continuar investigação`**, **`⏭ +3 etapas`**) e barra de **`Replay histórico`** (**`⏮ Início`**, **`← Anterior`**, **`Próximo →`**, **`⏭ Atual`**).
  - 4 cartões de métricas independentes (`Lances do jogo`, `Etapas de análise`, `Fontes no cofre`, `Telemetria Gemini`) e 4 abas analíticas (`Conversa`, `Fontes`, `Auditoria`, `Histórico`).
- **Suíte Completa de Aceite (`AT-01`..`AT-24`) e Teste Live Web (`LIVE_WEB`)**: 25 novos testes automatizados totalizando **66 testes aprovados**.
- **Documentação de Auditoria e Engenharia**: `AUDIT_REPORT.md`, `MIGRATION_PLAN.md`, `TEST_MATRIX.md` e capturas reais verificadas em Chromium (`docs/screenshots/`).

### Corrigido
- **Eliminado o limite artificial de 3 lances (`AUD-02`)**: Removido o buffer estático de 3 movimentos iniciais no cliente; o progresso da partida agora reflete os ciclos reais executados no backend.
- **Eliminado o fallback silencioso `LIVE → DEMO` (`AUD-03A`)**: Falhas `HTTP 429` / `503` ou timeout no Gemini executam *bounded retries* e lançam `ProviderUnavailableError` honesto, sem mascarar respostas sintéticas como execução real.
- **Telemetria Real e Honesta (`AUD-03B`)**: Extração direta de `usageMetadata` (`promptTokenCount`, `candidatesTokenCount`, `totalTokenCount`) e `latency_ms` real; remoção de valores estáticos fictícios (`12ms`, `$0.0000`), exibindo `Não medido` / `DEMO_OFFLINE` quando aplicável.
- **Verificação Literal de Citação e Citação Vazia (`AUD-04`)**: Corrigido defeito em que string vazia passava na checagem de substring; `DocumentVault.find_verified_quote_offset()` exige trecho normalizado mínimo e valida offsets exatos antes de permitir `SOURCE_VERIFIED` / `SUPPORTED`.
- **Perguntas Prospectivas / Eventos Futuros (`AUD-04`)**: Consultas sobre eventos futuros (ex.: eleições de 2030) são classificadas com `uncertainty_level="PROJECTION"` e veredito `HYPOTHESIS` / `INSUFFICIENT`, sem fabricar certeza factual.
- **Exportação Fiel de Relatórios**: Corrigidos fallbacks otimistas em `services/api/routes/reports.py` para `NO_SOURCES_ATTACHED` e `NOT_ASSESSED`.

## [2.0.0] — 2026-10-30

### Adicionado
- Arquitetura base da matriz 3×2 (Pesquisa, Debate, Auditoria × Xadrez 8×8, Go 9×9), motores determinísticos `python-chess` e `GoEngine9x9`, `EventStore` com hash SHA-256 encadeado, `DocumentVault` com isolamento de cofres privados, `FusionOrchestrator` e visualização WebGL 3D + 2D WCAG.

