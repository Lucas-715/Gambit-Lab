# Matriz de Testes e Rastreabilidade — Gambit Lab Nocturne v2.2

Este documento estabelece o mapeamento formal de rastreabilidade entre os requisitos de engenharia, critérios de aceitação e testes automatizados executados no Gambit Lab Nocturne v2.2.

---

## 1. Suíte de Aceite Reengenharia Nocturne R1.0 (`AT-01` a `AT-24`)

| ID | Cenário de Teste | Arquivo / Função | Resultado |
| :--- | :--- | :--- | :---: |
| `AT-01` | Consulta de capacidades reais do servidor (`GET /api/v1/capabilities`) | `tests/integration/test_nocturne_reengineering.py::test_at01_capabilities_endpoint` | **PASS** |
| `AT-02` | Pesquisa Web desativada: relatório claro e bloqueio de `WEB_ONLY` com 400 | `tests/integration/test_nocturne_reengineering.py::test_at02_web_disabled_cleanly_reports_reason_and_blocks_web_only` | **PASS** |
| `AT-03` | Pesquisa Web ativada: permite `WEB_ONLY` e `HYBRID` | `tests/integration/test_nocturne_reengineering.py::test_at03_web_enabled_allows_web_only_and_hybrid` | **PASS** |
| `AT-04` | Política `OWN_ONLY`: zero requisições externas de rede | `tests/integration/test_nocturne_reengineering.py::test_at04_own_only_makes_zero_external_web_calls` | **PASS** |
| `AT-05` | Política `WEB_ONLY`: busca web e armazena registros de fonte auditáveis | `tests/integration/test_nocturne_reengineering.py::test_at05_web_only_retrieves_auditable_source_records` | **PASS** |
| `AT-06` | Política `HYBRID`: combina cofre local e fontes web | `tests/integration/test_nocturne_reengineering.py::test_at06_hybrid_combines_local_vault_and_web_sources` | **PASS** |
| `AT-07` | Xadrez 8×8 avança além de 3 lances (atinge ≥ 10 lances válidos) | `tests/integration/test_nocturne_reengineering.py::test_at07_chess_progression_exceeds_10_legal_moves` | **PASS** |
| `AT-08` | Go 9×9 avança além de 3 lances e encerra com 2 passes consecutivos | `tests/integration/test_nocturne_reengineering.py::test_at08_go_progression_exceeds_10_moves_and_terminates_on_two_passes` | **PASS** |
| `AT-09` | Replay determinístico após 10 lances: ZERO chamadas ao LLM | `tests/integration/test_nocturne_reengineering.py::test_at09_deterministic_replay_after_10_moves_zero_llm_calls` | **PASS** |
| `AT-10` | FUSION: 3 ramificações isoladas e deduplicadas | `tests/integration/test_nocturne_reengineering.py::test_at10_fusion_three_branches_isolated_and_deduplicated` | **PASS** |
| `AT-11` | Modo `DEMO_OFFLINE`: rotulado honestamente, zero telemetria falsa | `tests/integration/test_nocturne_reengineering.py::test_at11_demo_offline_honest_labeling_no_fake_telemetry` | **PASS** |
| `AT-12` | Modo `LIVE`: extrai contagem real de tokens e latência medida | `tests/integration/test_nocturne_reengineering.py::test_at12_live_mode_extracts_real_usage_metadata_and_latency` | **PASS** |
| `AT-13` | Falha do provedor (429/503): retentativa com backoff, sem simular sucesso | `tests/integration/test_nocturne_reengineering.py::test_at13_provider_failure_429_503_retries_and_never_fakes_success` | **PASS** |
| `AT-14` | Citação adulterada detectada como `QUOTE_MISMATCH` | `tests/integration/test_nocturne_reengineering.py::test_at14_adulterated_quote_detected_as_quote_mismatch` | **PASS** |
| `AT-15` | Sessão sem fontes anexadas jamais recebe status `SUPPORTED` | `tests/integration/test_nocturne_reengineering.py::test_at15_session_without_sources_never_supported` | **PASS** |
| `AT-16` | Documento irrelevante não sustenta alegação factual | `tests/integration/test_nocturne_reengineering.py::test_at16_irrelevant_document_does_not_support_claim` | **PASS** |
| `AT-17` | Tema futuro (Eleição 2030): tratado como projeção/incerteza | `tests/integration/test_nocturne_reengineering.py::test_at17_future_election_2030_treated_as_uncertain_projection` | **PASS** |
| `AT-18` | Proteção Anti-SSRF: bloqueia localhost, redes privadas e IPs de metadados | `tests/integration/test_nocturne_reengineering.py::test_at18_ssrf_protection_blocks_localhost_private_and_metadata_ips` | **PASS** |
| `AT-19` | Isolamento de Cofre Privado: acesso direto não autorizado retorna HTTP 403 | `tests/integration/test_nocturne_reengineering.py::test_at19_private_vault_direct_access_returns_403` | **PASS** |
| `AT-20` | Prompt Injection em documento: neutralizado via XML delimitado | `tests/integration/test_nocturne_reengineering.py::test_at20_prompt_injection_in_source_neutralized_in_advance` | **PASS** |
| `AT-21` | Concorrência Otimista (409) e idempotência no avanço de sessão | `tests/integration/test_nocturne_reengineering.py::test_at21_optimistic_concurrency_409_and_idempotency_on_advance` | **PASS** |
| `AT-22` | UI Nocturne: acessibilidade WCAG, contraste e métricas honestas | `tests/integration/test_nocturne_reengineering.py::test_at22_nocturne_ui_accessibility_and_honest_controls` | **PASS** |
| `AT-23` | Ciclo de vida: Pausar, Retomar e Cancelar sessão | `tests/integration/test_nocturne_reengineering.py::test_at23_pause_resume_cancel_lifecycle` | **PASS** |
| `AT-24` | Exportação de relatório: reflete exatamente o estado factual da sessão | `tests/integration/test_nocturne_reengineering.py::test_at24_report_export_reflects_exact_session_state` | **PASS** |

---

## 2. Suíte de Aceite Research Match v2.2 (`RM-01` a `RM-17`)

| ID | Cenário de Teste | Arquivo / Função | Resultado |
| :--- | :--- | :--- | :---: |
| `RM-01` | Pesquisa Pró e Contra estritamente isoladas em cofres privados | `tests/integration/test_research_match_v2.py::test_rm01_pro_and_contra_research_are_isolated_and_about_the_real_question` | **PASS** |
| `RM-02` | Contenção estrita de injeção em prompts (`<INERT_DOCUMENT_EVIDENCE>`) | `tests/integration/test_research_match_v2.py::test_rm02_documents_with_injection_stay_inert_in_prompts` | **PASS** |
| `RM-03` | Dossiê completo para cada peça com evidências verificadas do seu próprio cofre | `tests/integration/test_research_match_v2.py::test_rm03_every_piece_has_dossier_and_verified_artifacts_from_its_own_vault` | **PASS** |
| `RM-04` | Rastreamento determinístico de peças em cada lance de Xadrez | `tests/integration/test_research_match_v2.py::test_rm04_piece_tracking_matches_the_board_at_every_ply` | **PASS** |
| `RM-05` | Rastreamento determinístico de pedras em cada lance de Go 9×9 | `tests/integration/test_research_match_v2.py::test_rm05_go_stone_ownership_matches_the_board_at_every_ply` | **PASS** |
| `RM-06` | Jogo de Xadrez encerra estritamente por regras formais ou orçamento | `tests/integration/test_research_match_v2.py::test_rm06_chess_ends_only_by_rule_or_explicit_budget` | **PASS** |
| `RM-07` | Jogo de Go encerra por dois passes consecutivos e contagem de área | `tests/integration/test_research_match_v2.py::test_rm07_go_full_game_ends_by_two_passes_and_area_score` | **PASS** |
| `RM-08` | Jogadores são 100% determinísticos para o mesmo seed de ruído SHA-256 | `tests/integration/test_research_match_v2.py::test_rm08_players_are_deterministic_for_the_same_seed` | **PASS** |
| `RM-09` | Esgotamento de orçamento é explícito e retomável sem inventar vencedor | `tests/integration/test_research_match_v2.py::test_rm09_budget_exhaustion_is_explicit_and_resumable_without_inventing_a_winner` | **PASS** |
| `RM-10` | Resultados lúdico e epistêmico são formalmente independentes (desacoplamento) | `tests/integration/test_research_match_v2.py::test_rm10_ludic_and_epistemic_results_are_independent` | **PASS** |
| `RM-11` | Regras de honestidade epistêmica: sem fontes = nunca SUPPORTED | `tests/integration/test_research_match_v2.py::test_rm11_epistemic_honesty_rules` | **PASS** |
| `RM-12` | Modo `DEMO_OFFLINE` jamais afirma vencedor epistêmico (`OPEN_HYPOTHESIS`) | `tests/integration/test_research_match_v2.py::test_rm12_demo_offline_never_claims_an_epistemic_winner` | **PASS** |
| `RM-13` | Replay reproduz a partida inteira sem qualquer chamada ao LLM | `tests/integration/test_research_match_v2.py::test_rm13_replay_reproduces_the_whole_match_without_any_llm_call` | **PASS** |
| `RM-14` | Partida LIVE realiza chamadas controladas medindo tokens reais | `tests/integration/test_research_match_v2.py::test_rm14_live_match_uses_three_calls_and_measures_real_tokens` | **PASS** |
| `RM-15` | Falha do provedor preserva integridade dos estágios já produzidos | `tests/integration/test_research_match_v2.py::test_rm15_provider_failure_mid_pipeline_keeps_everything_already_produced` | **PASS** |
| `RM-16` | API com progresso estágio a estágio e redação de peças antes de jogar | `tests/integration/test_research_match_v2.py::test_rm16_api_stage_by_stage_progress_and_viewer_redaction` | **PASS** |
| `RM-17` | Payload de sessão permanece leve e oculta estado interno de orquestração | `tests/integration/test_research_match_v2.py::test_rm17_session_payload_stays_light_and_hides_internal_state` | **PASS** |

---

## 3. Suíte de Automação em Navegador Real Chromium CDP

| Cenário de Teste | Verificação Executada | Captura de Tela | Resultado |
| :--- | :--- | :--- | :---: |
| **Fundo Vivo e Parallax** | Canvas estelar em 3 camadas, drift cósmico contínuo, mouse parallax e botão `#motionBtn` | `nocturne_v2_home.png` | **PASS** |
| **Ciclo de 7 Estágios** | Orquestração completa, barra de progresso em tempo real e transição ao Workspace | `nocturne_v2_home.png` | **PASS** |
| **Conclusão Dual Desacoplada** | Exibição de Resultado Lúdico vs Veredito Epistêmico, Ponto de Virada e Síntese | `nocturne_v2_dual_conclusion.png` | **PASS** |
| **5ª Aba: Peças & Teses** | Listagem de 32 peças com glifos, papéis, teses, confiança e filtros de estado | `nocturne_v2_pieces_dossiers.png` | **PASS** |
| **Navegação no Ponto de Virada** | Salto do cursor de replay diretamente para o lance crítico identificado | `nocturne_v2_dual_conclusion.png` | **PASS** |
| **Inspeção de Casas e Tabuleiro 2D** | Clique em casas no tabuleiro WCAG abrindo dossiê argumentativo da peça | `nocturne_v2_board_inspection.png` | **PASS** |

---

## 4. Suítes Unitárias de Motores e Componentes

| Arquivo | Escopo | Testes | Resultado |
| :--- | :--- | :---: | :---: |
| `tests/unit/test_chess_engine.py` | Regras FIDE, roque, *en passant*, promoção (`AC-21`), bloqueio epistêmico de captura e Impasse da Variante | 9 | **9 PASS** |
| `tests/unit/test_go_engine.py` | Tabuleiro Go 9×9, captura por liberdades, proibição de suicídio, superko posicional e término por 2 passes | 6 | **6 PASS** |
| `tests/unit/test_event_store.py` | Cadeia SHA-256 append-only, conflito de versão otimista e replay determinístico Xadrez/Go | 4 | **4 PASS** |
| `tests/unit/test_fusion_pipeline.py` | FUSION multi-estratégia em Xadrez e Go com deduplicação de fontes | 2 | **2 PASS** |
| `tests/integration/test_api_endpoints.py` | Matriz completa de 6 aplicações (`AC-01` a `AC-06`), FUSION (`AC-07`), concorrência e replay REST | 10 | **10 PASS** |
| `tests/integration/test_cosmic_flow.py` | Fluxo conversacional inicial, ausência de fontes em prompt livre e ciclo completo | 3 | **3 PASS** |
| `tests/integration/test_security_isolation.py` | Isolamento Lado A vs Lado B, contenção de prompt injection e ausência de vazamento de credenciais | 3 | **3 PASS** |
| `tests/integration/test_verification_tiers.py` | Separação estrita entre `integrity_status`, `source_status` e `evidence_assessment` | 3 | **3 PASS** |

---

## 5. Resumo Global de Qualidade

- **Total de Testes Automatizados Unitários e de Integração**: **81 PASS** (100% de sucesso).
- **Total de Cenários Chromium CDP Verificados em Tela**: **6 Cenários PASS** (100% de sucesso).
- **Exceções ou Falhas de Regressão**: **0**.


## Matriz de Aceite e Verificação v2.3 (Nocturne Focus & Epistêmica)

| ID | Cenário / Critério | Tipo | Arquivo de Teste / Evidência | Resultado |
|---|---|---|---|:---:|
| **C01** | Trecho localizado marca `SOURCE_VERIFIED`, não `SUPPORTED` para claim forte | Unit / Epistêmico | `tests/integration/test_v23_epistemic_audit.py` | **PASS** |
| **C02** | Captura física marca `NOT_ASSESSED`/`INCONCLUSIVE`, nunca `REFUTED` | Unit / Epistêmico | `tests/integration/test_v23_epistemic_audit.py` | **PASS** |
| **C03** | Pesos de peças unitários e deduplicação de claims/fontes por hash/DOI | Unit / Epistêmico | `tests/integration/test_v23_epistemic_audit.py` | **PASS** |
| **C04** | Resignação automática 800cp desligada por default; regras FIDE oficiais | Unit / Game Engine | `tests/integration/test_v23_epistemic_audit.py` | **PASS** |
| **C05** | Capturas legais FIDE nunca bloqueadas no modo padrão | Unit / Game Engine | `tests/integration/test_v23_epistemic_audit.py` | **PASS** |
| **C06** | Rótulos externos visíveis a-h, 1-8 (Xadrez) e A-J, 1-9 (Go sem I) em 2D/3D | Browser / CDP | `scratch/verify_v23_nocturne_focus_cdp.py` | **PASS** |
| **C07** | Layout centrado no tabuleiro + painel Lance Selecionado contextual | Browser / CDP | `scratch/verify_v23_nocturne_focus_cdp.py` | **PASS** |
| **C08** | Topbar limpa, menu Diagnóstico & Estado, sidebar retrátil | Browser / CDP | `scratch/verify_v23_nocturne_focus_cdp.py` | **PASS** |
| **C09** | Estados epistêmicos discretos sem probabilidades flutuantes não calibradas | Schema / Unit | `tests/integration/test_v23_epistemic_audit.py` | **PASS** |
| **C10** | Encerramento consistente derivado de evento terminal único | Integration | `tests/integration/test_research_match_v2.py` | **PASS** |
| **C11** | Payload `MoveAuditPayloadSchema` em cada lance da timeline | Integration / Schema | `tests/integration/test_v23_epistemic_audit.py` | **PASS** |
| **C12** | Redação de dossiês não jogados para perfis observador / adversário | Security / API | `tests/integration/test_v23_epistemic_audit.py` | **PASS** |
| **UX01** | Iniciar investigação abre workspace focado sem poluição visual | Browser / CDP | `docs/screenshots/nocturne_v23_workspace_focus.png` | **PASS** |
| **UX02** | Xadrez 3D e 2D com coordenadas externas corretas | Browser / CDP | `docs/screenshots/nocturne_v23_board_2d_coordinates.png` | **PASS** |
| **UX03** | Go 9×9 com colunas A-J (sem a letra I) | Browser / CDP | `scratch/verify_v23_nocturne_focus_cdp.py` | **PASS** |
| **UX04** | Painel Lance Selecionado atualiza com peça, claim, quote e veredito | Browser / CDP | `docs/screenshots/nocturne_v23_lance_selecionado.png` | **PASS** |
| **UX05** | Replay histórico sincroniza lance, FEN e alegações sem chamar LLM | Browser / CDP | `scratch/verify_v23_nocturne_focus_cdp.py` | **PASS** |
| **UX06** | Sidebar recolhível e responsividade mobile sem overflow horizontal | Browser / CDP | `docs/screenshots/nocturne_v23_sidebar_collapsed.png` | **PASS** |
| **UX07** | Modal Diagnóstico exibe métricas, telemetria e integridade SHA-256 | Browser / CDP | `docs/screenshots/nocturne_v23_diagnostics_modal.png` | **PASS** |

---

## 7. Suíte de Rastreabilidade e Coordenadas v2.3.1 (`T01` a `T06`)

| ID | Cenário / Critério | Tipo | Arquivo de Teste / Evidência | Resultado |
|---|---|---|---|:---:|
| **T01** | Painel Lance Selecionado populado automaticamente na carga da partida | Browser / CDP | `docs/screenshots/nocturne_v23_1_lance_selecionado_auto.png` | **PASS** |
| **T02** | Replay sincroniza timeline completa de 10+ lances com dados semânticos | Browser / CDP | `docs/screenshots/nocturne_v23_1_replay_plies_1_to_10.png` | **PASS** |
| **T03** | Mapeamento atômico entre `move_event_seq` e `EventStore` no timeline | Unit / Schema | `tests/integration/test_v23_epistemic_audit.py` | **PASS** |
| **T04** | Grade 2D CSS (.board-2d-inner) alinhada 1:1 com as fileiras (8..1) e colunas (a..h) | Browser / CDP | `docs/screenshots/nocturne_v23_1_2d_aligned_grid.png` | **PASS** |
| **T05** | Overlay 3D projeta coordenadas com perspectiva exata sobre o WebGL | Browser / CDP | `docs/screenshots/nocturne_v23_1_3d_perspective_coords.png` | **PASS** |
| **T06** | Coordenadas do Go 9x9 com A-J (sem I) e honestidade de citações/capturas | Browser / CDP | `docs/screenshots/nocturne_v23_1_go_coords_no_i.png` | **PASS** |

---

## 8. Suíte de Redesign Nocturne Focus v2.4 (`R01` a `R07` e `UX08` a `UX12`)

| ID | Cenário / Critério | Tipo | Arquivo de Teste / Evidência | Resultado |
|---|---|---|---|:---:|
| **R01** | Simplificação para 2 Modos: Debate de Evidências e Auditoria de Controles | UI / Functional | `scratch/verify_v24_nocturne_cdp.py` | **PASS** |
| **R02** | Tema Único NOCTURNE: remoção do tema azul Cosmic, paleta estrita (#08080A) | UI / CSS | `scratch/verify_v24_nocturne_cdp.py` | **PASS** |
| **R03** | Xadrez 2D SVG como padrão com 64 casas, peças vetoriais e seta de lance | Browser / SVG | `docs/screenshots/nocturne_v24_debate_2d_chess.png` | **PASS** |
| **R04** | Go 9×9 2D SVG em madeira escura, pedras com sombra e anel pulsante | Browser / SVG | `docs/screenshots/nocturne_v24_audit_2d_go.png` | **PASS** |
| **R05** | Replay Bar com Reprodução Automática (Timer 1.5s) e barra SAN clicável | Browser / CDP | `scratch/verify_v24_nocturne_cdp.py` | **PASS** |
| **R06** | Painel de Auditoria de Controles com requisitos normativos e riscos | Integration / UI | `docs/screenshots/nocturne_v24_audit_2d_go.png` | **PASS** |
| **R07** | Segurança de Pacotes: exclusão estrita de `.env` nos ZIPs de release | Script / Security | `scratch/create_release_zip.py` | **PASS** |
| **UX08** | Home minimalista com alternador de modos proeminente e placeholders dinâmicos | Browser / CDP | `docs/screenshots/nocturne_v24_home_redesign.png` | **PASS** |
| **UX09** | Inversão de perspectiva do tabuleiro com um clique (`flip board`) | Browser / CDP | `docs/screenshots/nocturne_v24_debate_board_flipped.png` | **PASS** |
| **UX10** | Coordenadas de canto internas (estilo Chess.com / Lichess) | Browser / CDP | `docs/screenshots/nocturne_v24_debate_2d_chess.png` | **PASS** |
| **UX11** | Notação de lances compacta e clicável com realce ativo do lance atual | Browser / CDP | `scratch/verify_v24_nocturne_cdp.py` | **PASS** |
| **UX12** | Integridade da suíte completa de testes de regressão (90 testes unitários/integração) | Pytest Suite | `pytest tests/ -q` (90 passed) | **PASS** |



---

## 9. Suíte de Refinamento e Partidas Longas v2.4.1 (`P01` a `P06` e `UX13` a `UX18`)

| ID | Cenário / Critério | Tipo | Arquivo de Teste / Evidência | Resultado |
|---|---|---|---|:---:|
| **P01** | 3D Real (WebGL) como modo padrão com enquadramento aproximado (`radius=11.2`) e `resetCamBtn` | Browser / CDP | `docs/screenshots/nocturne_v24_1_3d_close_framed.png` | **PASS** |
| **P02** | 2D SVG reconstruído perfeitamente centralizado com 24 peças vetoriais Cburnett | Browser / CDP | `docs/screenshots/nocturne_v24_1_2d_cburnett_centered.png` | **PASS** |
| **P03** | Painel Narrativo Simplificado com Cabeçalho, Tese, Evidência e Veredito do Árbitro | Browser / CDP | `docs/screenshots/nocturne_v24_1_narrative_panel.png` | **PASS** |
| **P04** | Barra de Replay com lances formatados em pares numerados (`1. e4 e5 ...`) e auto-scroll | Browser / CDP | `docs/screenshots/nocturne_v24_1_replay_pairs_strip.png` | **PASS** |
| **P05** | Conclusão honesta de orçamento esgotado sem inventar vencedor artificial | Browser / CDP | `docs/screenshots/nocturne_v24_1_budget_exhausted_honest.png` | **PASS** |
| **P06** | Partida longa de 60 lances em Xadrez e Go 9x9 com inspeção de múltiplos lances | Browser / CDP | `docs/screenshots/nocturne_v24_1_audit_go_cburnett.png` | **PASS** |
| **UX13** | Botão `↺ Câmera` restaura perspectiva neutra (`theta=0, phi=0.82, radius=11.2`) | Browser / CDP | `scratch/verify_v24_1_full_run_cdp.py` | **PASS** |
| **UX14** | Eliminação da área morta à esquerda no 2D (`display: none` em #boardRanks2D) | Browser / CSS | `scratch/verify_v24_1_full_run_cdp.py` | **PASS** |
| **UX15** | Inversão do tabuleiro 2D preserva orientação vertical correta dos símbolos Cburnett | Browser / SVG | `scratch/verify_v24_1_full_run_cdp.py` | **PASS** |
| **UX16** | Sincronia instantânea de dossiê ao clicar em qualquer lance da barra em pares | Browser / CDP | `scratch/verify_v24_1_full_run_cdp.py` | **PASS** |
| **UX17** | Bloco de Auditoria de Controles exibindo Requisito, Risco e Conformidade no modo Audit | Browser / CDP | `docs/screenshots/nocturne_v24_1_audit_go_cburnett.png` | **PASS** |
| **UX18** | Coordenadas oficiais de Go 9x9 sem a letra `I` (colunas A..H, J) | Browser / CDP | `scratch/verify_v24_1_full_run_cdp.py` | **PASS** |


---

## 7. Suíte de Aceite Xadrez Epistêmico & Matriz SWOT v2.5 (`E01` a `E20`)

| ID | Cenário de Teste | Arquivo / Função | Resultado |
| :--- | :--- | :--- | :---: |
| `E01` | Identidades únicas para as 32 peças de xadrez (`piece_id`, `claim_id`) | `tests/integration/test_v25_epistemic_chess_swot.py::test_v25_heterogeneous_subtheses_32_pieces` | **PASS** |
| `E02` | Subteses heterogêneas especializadas por papel e casa | `tests/integration/test_v25_epistemic_chess_swot.py::test_v25_heterogeneous_subtheses_32_pieces` | **PASS** |
| `E03` | Dependência epistêmica estruturada (`parent_thesis_id`) | `tests/integration/test_v25_epistemic_chess_swot.py::test_v25_heterogeneous_subtheses_32_pieces` | **PASS** |
| `E04` | Legitimidade física restrita às regras FIDE (`python-chess`) | `tests/integration/test_v25_epistemic_chess_swot.py::test_v25_clash_engine_evidentiary_arbitration` | **PASS** |
| `E05` | Arbitragem puramente documental sem pesos arbitrários de peças | `tests/integration/test_v25_epistemic_chess_swot.py::test_v25_clash_engine_evidentiary_arbitration` | **PASS** |
| `E06` | Vereditos explícitos de confronto (`CAPTURE_AUTHORIZED`, `DEFENSE_SUCCESSFUL`, etc.) | `tests/integration/test_v25_epistemic_chess_swot.py::test_v25_clash_engine_evidentiary_arbitration` | **PASS** |
| `E07` | RBAC granular por peça no `DocumentVault` (`PermissionDeniedError` em acesso indevido) | `tests/integration/test_v25_epistemic_chess_swot.py::test_v25_piece_vault_rbac_isolation` | **PASS** |
| `E08` | Invariante Epistêmico do Rei (`is_king_protected=True`) | `tests/integration/test_v25_epistemic_chess_swot.py::test_v25_clash_engine_king_invariant` | **PASS** |
| `E09` | Resiliência do defensor: peça permanece no tabuleiro se a defesa sucede | `tests/integration/test_v25_epistemic_chess_swot.py::test_v25_clash_engine_evidentiary_arbitration` | **PASS** |
| `E10` | Realce visual de alcance e capturabilidade em 2D e 3D | `scratch/verify_v25_epistemic_cdp.py` (Passos 3 e 4) | **PASS** |
| `E11` | Modal interativo de confronto argumentativo com justificativa do árbitro | `scratch/verify_v25_epistemic_cdp.py` (Passo 5) | **PASS** |
| `E12` | Go 9×9 com Matriz SWOT dimensional (`STRENGTH`, `WEAKNESS`, `OPPORTUNITY`, `THREAT`) | `tests/integration/test_v25_epistemic_chess_swot.py::test_v25_go_swot_distribution` | **PASS** |
| `E13` | Preservação total das regras espaciais, liberdades e contagem do Go | `tests/integration/test_v25_epistemic_chess_swot.py::test_v25_go_swot_distribution` | **PASS** |
| `E14` | Cache de avaliações semânticas via hash SHA-256 | `tests/integration/test_v25_epistemic_chess_swot.py::test_v25_clash_engine_evidentiary_arbitration` | **PASS** |
| `E15` | Endpoint REST `GET /pieces/{piece_id}/reachability` | `tests/integration/test_v25_epistemic_chess_swot.py::test_v25_reachability_api_endpoint` | **PASS** |
| `E16` | Endpoint REST `POST /confrontation/evaluate` | `tests/integration/test_v25_epistemic_chess_swot.py::test_v25_confrontation_evaluate_api_endpoint` | **PASS** |
| `E17` | Zero Emojis em toda a interface e relatórios | `scratch/verify_v25_epistemic_cdp.py` (Passo 1) | **PASS** |
| `E18` | Rastreabilidade de confrontos no histórico individual de cada peça | `tests/integration/test_v25_epistemic_chess_swot.py::test_v25_full_chess_epistemic_match` | **PASS** |
| `E19` | Gravação de `clash_info` no payload de auditoria do Event Store | `tests/integration/test_v25_epistemic_chess_swot.py::test_v25_full_chess_epistemic_match` | **PASS** |
| `E20` | Partida completa de Xadrez Epistêmico gerando conclusão dual auditável | `tests/integration/test_v25_epistemic_chess_swot.py::test_v25_full_chess_epistemic_match` | **PASS** |


---

## 8. Suíte de Relevância Temática, Arbitragem Epistêmica e Correção 2D v2.5.1 (`R01` a `R07`)

| ID | Cenário de Teste | Arquivo / Função | Resultado |
| :--- | :--- | :--- | :---: |
| `R01` | Rejeição de templates de TI (MTTR, supply chain, RBAC) em perguntas políticas/eleitorais | `tests/integration/test_v25_1_thematic_relevance.py::test_political_investigation_rejects_it_templates_and_decomposes_electoral_dimensions` | **PASS** |
| `R02` | Decomposição analítica em dimensões políticas reais com confiança calibrada honesta | `tests/integration/test_v25_1_thematic_relevance.py::test_political_investigation_rejects_it_templates_and_decomposes_electoral_dimensions` | **PASS** |
| `R03` | Citação verdadeira porém descontextualizada (Temer 2016 vs Eleição 2030) não autoriza captura | `tests/integration/test_v25_1_thematic_relevance.py::test_irrelevant_true_quote_cannot_authorize_capture` | **PASS** |
| `R04` | Confronto entre duas hipóteses sem prova documental resulta em `CONFRONTATION_INCONCLUSIVE` | `tests/integration/test_v25_1_thematic_relevance.py::test_two_unsupported_hypotheses_produce_inconclusive_verdict` | **PASS** |
| `R05` | Evidência verificada e comprovadamente pertinente ao tema autoriza captura legítima | `tests/integration/test_v25_1_thematic_relevance.py::test_pertinent_verified_evidence_authorizes_capture` | **PASS** |
| `R06` | Centralização simétrica do tabuleiro 2D, ocultação de `#stageContainer` e eliminação de coordenadas fantasmas | `scratch/verify_v25_1_e2e_cdp.py` (Passo 4) | **PASS** |
| `R07` | Correspondência rigorosa 1:1 entre símbolos vetoriais Cburnett renderizados e o FEN do motor | `scratch/verify_v25_1_e2e_cdp.py` (Passo 5) | **PASS** |
