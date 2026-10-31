# Matriz de Rastreabilidade e Testes de Aceite — Gambit Lab Nocturne (R1.0)

**Comando Executado:** `.\.venv\Scripts\python.exe -m pytest tests/unit tests/integration tests/live -v`  
**Resultado Consolidado:** **`66 PASSED, 0 FAILED, 0 SKIPPED`**

---

## 1. Testes de Aceite da Reengenharia Nocturne (`AT-01` a `AT-24`)

Arquivo: `tests/integration/test_nocturne_reengineering.py`

| ID | Requisito / Critério Auditado | Função de Teste | Resultado |
| :--- | :--- | :--- | :---: |
| **AT-01** | `GET /api/v1/capabilities` expõe disponibilidade real de Gemini, Web Search, políticas e modos | `test_at01_capabilities_endpoint` | **PASS** |
| **AT-02** | Com Web desabilitada (`GAMBIT_WEB_SEARCH_ENABLED=0`), `capabilities` informa motivo e `WEB_ONLY` retorna `HTTP 503` | `test_at02_web_disabled_cleanly_reports_reason_and_blocks_web_only` | **PASS** |
| **AT-03** | Com Web habilitada, `WEB_ONLY` e `HYBRID` criam sessões válidas e auditáveis | `test_at03_web_enabled_allows_web_only_and_hybrid` | **PASS** |
| **AT-04** | Política `OWN_ONLY` realiza **zero** chamadas externas de rede | `test_at04_own_only_makes_zero_external_web_calls` | **PASS** |
| **AT-05** | Política `WEB_ONLY` recupera `SourceRecord` com URL canônica HTTPS, domínio, timestamp UTC e SHA-256 | `test_at05_web_only_retrieves_auditable_source_records` | **PASS** |
| **AT-06** | Política `HYBRID` combina documentos locais do Cofre e fontes públicas da Web na mesma investigação | `test_at06_hybrid_combines_local_vault_and_web_sources` | **PASS** |
| **AT-07** | Progressão contínua em **Xadrez 8×8** supera **10+ lances legais** consecutivos (fim do limite `Lance 3 / 3`) | `test_at07_chess_progression_exceeds_10_legal_moves` | **PASS** |
| **AT-08** | Progressão contínua em **Go 9×9** supera **10+ jogadas legais** e encerra formalmente com 2 passes consecutivos | `test_at08_go_progression_exceeds_10_moves_and_terminates_on_two_passes` | **PASS** |
| **AT-09** | Replay determinístico (`?up_to_seq=N` e integral) reconstrói qualquer lance histórico com **zero chamadas ao LLM** | `test_at09_deterministic_replay_after_10_moves_zero_llm_calls` | **PASS** |
| **AT-10** | Pipeline **FUSION** executa 3 ramos com tabuleiros isolados e deduplica fontes idênticas por SHA-256 | `test_at10_fusion_three_branches_isolated_and_deduplicated` | **PASS** |
| **AT-11** | Modo `DEMO_OFFLINE` é rotulado explicitamente e reporta telemetria `null` (sem inventar `12ms` ou `$0.0000`) | `test_at11_demo_offline_honest_labeling_no_fake_telemetry` | **PASS** |
| **AT-12** | Modos `LIVE_*` extraem `usageMetadata` real (`promptTokenCount`, `candidatesTokenCount`, `totalTokenCount`) e `latency_ms` | `test_at12_live_mode_extracts_real_usage_metadata_and_latency` | **PASS** |
| **AT-13** | Falhas `HTTP 429` / `503` do provedor executam retry limitado e retornam erro honesto (**jamais** caem silenciosamente para `DEMO`) | `test_at13_provider_failure_429_503_retries_and_never_fakes_success` | **PASS** |
| **AT-14** | Citação adulterada ou ausente no documento é reprovada com `QUOTE_MISMATCH` e nunca recebe `SUPPORTED` | `test_at14_adulterated_quote_detected_as_quote_mismatch` | **PASS** |
| **AT-15** | Sessão sem fontes anexadas (`0` artefatos) mantém `NO_SOURCES_ATTACHED` e `HYPOTHESIS` (nunca `SUPPORTED`) | `test_at15_session_without_sources_never_supported` | **PASS** |
| **AT-16** | Documento irrelevante ao claim não concede `SUPPORTED` quando não há trecho literal correspondente | `test_at16_irrelevant_document_does_not_support_claim` | **PASS** |
| **AT-17** | Pergunta sobre evento futuro (Eleições 2030) é tratada como projeção incerta (`PROJECTION` / `HYPOTHESIS`), sem fabricar vencedor | `test_at17_future_election_2030_treated_as_uncertain_projection` | **PASS** |
| **AT-18** | Proteção **Anti-SSRF** bloqueia `localhost`, `127.0.0.1`, RFC 1918, `169.254.169.254` (cloud metadata), `http://` e redirects maliciosos | `test_at18_ssrf_protection_blocks_localhost_private_and_metadata_ips` | **PASS** |
| **AT-19** | Isolamento de Cofres Privados em Debate bloqueia acesso cruzado com `HTTP 403 Forbidden` | `test_at19_private_vault_direct_access_returns_403` | **PASS** |
| **AT-20** | Prompt Injection embutido em fonte documental/web é neutralizado e não subverte o árbitro determinístico | `test_at20_prompt_injection_in_source_neutralized_in_advance` | **PASS** |
| **AT-21** | Concorrência otimista (`expected_version` divergente → `HTTP 409`) e `Idempotency-Key` funcionam em `/advance` | `test_at21_optimistic_concurrency_409_and_idempotency_on_advance` | **PASS** |
| **AT-22** | UI **Gambit Lab Nocturne** serve tokens `#040405`, WebGL 3D + 2D WCAG, controles separados de Avanço vs Replay e 4 abas ARIA | `test_at22_nocturne_ui_accessibility_and_honest_controls` | **PASS** |
| **AT-23** | Ciclo operacional `/pause`, `/resume` e `/cancel` governa transições válidas de estado | `test_at23_pause_resume_cancel_lifecycle` | **PASS** |
| **AT-24** | Exportação de relatório (`JSON` e `Markdown`) reflete exatamente os contadores, fontes e status epistêmicos reais | `test_at24_report_export_reflects_exact_session_state` | **PASS** |

---

## 2. Testes Ponta a Ponta Ao Vivo (`LIVE` Gemini + Web Pública)

Arquivo: `tests/live/test_gemini_live.py`

| ID | Cenário Validado ao Vivo | Função de Teste | Resultado |
| :--- | :--- | :--- | :---: |
| **LIVE-01** | Chamada real ao Google Gemini com resolução epistêmica de conflito documental (`NOT_COMPARABLE` / `INCONCLUSIVE`) | `test_live_gemini_research_and_conflict_resolution` | **PASS** |
| **LIVE-02** | Fluxo completo FastAPI `LIVE_WEB` (`GET /capabilities` → `POST /sessions` → `POST /advance`) com busca HTTPS real, SHA-256 e `usageMetadata` real | `test_live_web_advance_and_real_telemetry` | **PASS** |

---

## 3. Suítes Unitárias e de Integração Preservadas (`v2.0`)

| Arquivo | Escopo | Testes | Resultado |
| :--- | :--- | :---: | :---: |
| `tests/unit/test_chess_engine.py` | Regras FIDE, roque, *en passant*, promoção (`AC-21`), bloqueio epistêmico de captura e Impasse da Variante | 9 | **9 PASS** |
| `tests/unit/test_go_engine.py` | Tabuleiro Go 9×9, captura por liberdades, proibição de suicídio, superko posicional e término por 2 passes | 6 | **6 PASS** |
| `tests/unit/test_event_store.py` | Cadeia SHA-256 append-only, conflito de versão otimista e replay determinístico Xadrez/Go | 4 | **4 PASS** |
| `tests/unit/test_fusion_pipeline.py` | FUSION multi-estratégia em Xadrez e Go com deduplicação de fontes | 2 | **2 PASS** |
| `tests/integration/test_api_endpoints.py` | Matriz completa de 6 aplicações (`AC-01` a `AC-06`), FUSION (`AC-07`), concorrência e replay REST | 10 | **10 PASS** |
| `tests/integration/test_cosmic_flow.py` | Fluxo conversacional inicial, ausência de fontes em prompt livre e ciclo completo | 3 | **3 PASS** |
| `tests/integration/test_security_isolation.py` | Isolamento Lado A vs Lado B, contenção de prompt injection e ausência de vazamento de `GEMINI_API_KEY` | 3 | **3 PASS** |
| `tests/integration/test_verification_tiers.py` | Separação estrita entre `integrity_status`, `source_status` e `evidence_assessment` | 3 | **3 PASS** |
