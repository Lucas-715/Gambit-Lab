# Changelog — Gambit Lab

Todas as mudanças relevantes deste projeto são documentadas neste arquivo.

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
