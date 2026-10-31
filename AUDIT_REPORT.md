# Relatório Técnico de Auditoria e Reengenharia — Gambit Lab Nocturne (R1.0)

**Versão Auditada:** Gambit Lab 2.0 (`master` @ `21425e0`)  
**Versão Reengenheirada:** Gambit Lab 2.1.0-nocturne (`refactor/nocturne-audit`)  
**Abordagem:** Reengenharia Controlada (preservando motores determinísticos `python-chess` e `GoEngine9x9`, API FastAPI, `EventStore` SHA-256, `DocumentVault`, `FusionOrchestrator` e renderização WebGL 3D procedural nativa).

---

## 1. Sumário Executivo

A auditoria independente no código-fonte de `master` (`21425e0`) confirmou integralmente os quatro diagnósticos levantados na inspeção funcional (`AUD-01` a `AUD-04`) e revelou três defeitos subjacentes adicionais de verificação epistêmica. Todos os problemas foram corrigidos sem descartar a arquitetura base, elevando a suíte automatizada de **41 para 66 testes aprovados (`66 PASSED, 0 FAILED, 0 SKIPPED`)**, incluindo validação ponta a ponta ao vivo (`LIVE_WEB`) com Google Gemini e pesquisa web pública auditável.

---

## 2. Tabela de Causas Raiz, Correções e Evidências (`file:line`)

| ID | Problema Auditado | Arquivo:Linha (`master`) | Causa Raiz Comprovada | Correção Implementada (`refactor/nocturne-audit`) | Teste / Evidência |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **AUD-01** | Pesquisa Web indisponível ("em desenvolvimento") e ausência de contrato de capacidades | `apps/web/index.html:464`<br>`services/api/models/schemas.py:21` | `source_policy` aceitava apenas `own_only` e `web_opt_in` sem adaptador de busca real; a UI marcava a opção como planejada/indisponível e não consultava capacidades do servidor. | Criado `GET /api/v1/capabilities` (`services/api/routes/capabilities.py`) e `WebSearchAdapter` (`services/api/agents/web_search_adapter.py`) com políticas explícitas `OWN_ONLY`, `WEB_ONLY` e `HYBRID` (retrocompatíveis), busca HTTPS pública (OpenAlex + Wikimedia/Wikipedia), captura manual de snapshot HTTPS, sanitização HTML, hash SHA-256 e bloqueio anti-SSRF rigoroso. | `AT-01` a `AT-06`, `AT-18`, `test_live_web_advance_and_real_telemetry` (**PASS**) |
| **AUD-02** | Partida limitada artificialmente a 3 lances (`Lance 3 / 3`) e mistura entre avanço e replay | `apps/web/index.html:1400-1413`<br>`services/api/storage/session_manager.py:131-190` | O frontend semeava um array fixo de apenas 3 lances de abertura (`seedDemoMoves` / `sessionMoves`) na criação da sessão, e os botões `←` / `→` apenas percorriam esse buffer estático sem acionar um orquestrador contínuo de turnos. | Criado endpoint dedicado `POST /api/v1/sessions/{id}/advance` com `Idempotency-Key` e `expected_version` (`409 Conflict`), rotas `/pause`, `/resume` e `/cancel`, método `GoEngine9x9.get_legal_moves()`, contadores independentes (`ply_count`, `investigation_step_index`, `events_count`) e separação visual/semântica entre **`▶ Continuar investigação`** e **`Replay histórico`** (`GET /replay?up_to_seq=...` com zero chamadas ao LLM). | `AT-07`, `AT-08`, `AT-09`, `AT-21`, `AT-23` + verificação Chromium com 6+ lances em Xadrez e Go (**PASS**) |
| **AUD-03A** | Queda silenciosa de `LIVE` para `DEMO` em falhas/cota (`HTTP 429`), mascarando respostas sintéticas como execução real | `services/api/agents/gemini_adapter.py:93-95`<br>`tests/conftest.py:1-14` | **Hipótese H3.1 comprovada empiricamente:** `gemini-flash-latest` no Free Tier possui limite de 20 req/dia. Ao atingir `HTTP 429 RESOURCE_EXHAUSTED`, o bloco `except Exception: return self._demo_research_step(...)` capturava o erro silenciosamente e devolvia texto sintético predefinido mantendo aparência de sessão conectada. | Removido o fallback silencioso em modos `LIVE_*`. `GeminiAdapter` agora aplica *bounded retries* em `429`/`503`/timeout e lança `ProviderUnavailableError` (retornando HTTP `429`/`503` explícito e pausando a sessão de forma honesta). Modos explícitos: `DEMO_OFFLINE`, `LIVE_DOCUMENTS`, `LIVE_WEB`, `LIVE_HYBRID`. | `AT-11`, `AT-12`, `AT-13` (**PASS**) |
| **AUD-03B** | Telemetria fictícia/fixa (`12 ms`, `$0.0000`) sem medição real | `apps/web/index.html`<br>`services/api/agents/gemini_adapter.py:66-92` | `GeminiAdapter._call_gemini_api` descartava o objeto `usageMetadata` da resposta REST do Gemini e não cronometrava a chamada; a UI exibia valores estáticos decorativos. | Extração real de `usageMetadata` (`promptTokenCount`, `candidatesTokenCount`, `totalTokenCount`) e `latency_ms` via `time.perf_counter()` em `ProviderUsageSchema`. Quando não medido (ex.: `DEMO_OFFLINE`), a API retorna `null` e a UI exibe **`Não medido`**. | `AT-11`, `AT-12`, `test_live_web_advance_and_real_telemetry` (**PASS**) |
| **AUD-04A** | Respostas genéricas sobre SHA-256 desconectadas do tema e falsa certeza sobre eventos futuros (ex.: Eleições 2030) | `services/api/storage/session_manager.py:72-98`<br>`services/api/agents/gemini_adapter.py:130-165` | Prompts não relacionados recebiam narrativa genérica de integridade ou tinham fixtures anexadas indevidamente; perguntas prospectivas (ex.: eleições de 2030) não tinham diretriz formal de projeção/incerteza. | Prompts livres sem fontes iniciam com `0` artefatos (`NO_SOURCES_ATTACHED` / `HYPOTHESIS`). Perguntas sobre eventos futuros recebem `uncertainty_level="PROJECTION"`, `uncertainty_recognized=True` e veredito `HYPOTHESIS` / `INSUFFICIENT` (jamais `SUPPORTED` com vencedor fabricado). | `AT-15`, `AT-16`, `AT-17` (**PASS**) |
| **AUD-04B** | Bug de citação vazia aprovada (`"" in content`) e defaults otimistas na exportação de relatórios | `services/api/storage/vault.py:100-101`<br>`services/api/routes/reports.py:44-45` | Em Python, `"" in norm_content` avalia como `True`, permitindo que uma citação vazia passasse em `verify_quote_exists`. Além disso, `reports.py` usava `"SOURCE_VERIFIED"` e `"SUPPORTED"` como fallback default em `.get()`. | `DocumentVault.find_verified_quote_offset()` exige trecho normalizado mínimo (`>= 4` caracteres) e retorna offsets reais `(char_start, char_end)` ou `QUOTE_MISMATCH`. Fallbacks em `reports.py` corrigidos para `"NO_SOURCES_ATTACHED"` e `"NOT_ASSESSED"`. | `AT-14`, `AT-15`, `AT-24` (**PASS**) |

---

## 3. Matriz de Honestidade Epistêmica e Modos de Execução

| Modo de Execução (`execution_mode`) | Condição de Ativação | Chamadas Externas Web | Chamadas Google Gemini | Telemetria (`provider_usage`) | Teto Epistêmico sem Fontes Verificadas |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`DEMO_OFFLINE`** | `force_demo=true`, `GAMBIT_FORCE_DEMO=1` ou ausência de `GEMINI_API_KEY` | **Zero** (ou mock explícito de teste) | **Zero** | `source="demo_offline"`, tokens/latência `null` (`"Não medido"`) | `NO_SOURCES_ATTACHED` → `HYPOTHESIS` |
| **`LIVE_DOCUMENTS`** | Gemini ativo + política `OWN_ONLY` | **Zero** (`AT-04` comprovado) | **Real** (`usageMetadata` extraído) | `source="gemini_api"`, tokens e `latency_ms` reais | `NO_SOURCES_ATTACHED` → `HYPOTHESIS` |
| **`LIVE_WEB`** | Gemini ativo + política `WEB_ONLY` | **HTTPS Público + Anti-SSRF** (OpenAlex / Wikimedia) | **Real** (`usageMetadata` extraído) | `source="gemini_api"`, tokens e `latency_ms` reais | Se busca falhar: `SEARCH_UNAVAILABLE` → `NOT_ASSESSED` (zero fontes inventadas) |
| **`LIVE_HYBRID`** | Gemini ativo + política `HYBRID` | **Cofre Local + HTTPS Público Anti-SSRF** | **Real** (`usageMetadata` extraído) | `source="gemini_api"`, tokens e `latency_ms` reais | Exige `SOURCE_VERIFIED` + quote literal para `SUPPORTED` |

---

## 4. Segurança e Proteção Anti-SSRF / Anti-Prompt-Injection

1. **Proteção Anti-SSRF (`services/api/agents/web_search_adapter.py`)**:
   - Aceita exclusivamente esquema `https://` na porta `443` (bloqueia `http://`, `file://`, `ftp://`, `gopher://` e portas não-padrão).
   - Resolve DNS e bloqueia `localhost`, loopback (`127.0.0.0/8`, `::1`), redes privadas RFC 1918 (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), link-local e **Cloud Metadata** (`169.254.169.254`), CGNAT (`100.64.0.0/10`), multicast e endereços reservados.
   - Valida manualmente cada salto de redirecionamento HTTP (`follow_redirects=False` com revalidação DNS/IP a cada hop, máximo 3 saltos).
   - Limita payload a `512 KB` e filtra MIME types permitidos (`text/html`, `text/plain`, `application/json`, `text/markdown`).
2. **Isolamento de Cofres Privados (`HTTP 403`)**:
   - Em sessões de Debate, documentos do cofre `white` ou `black` permanecem isolados e tentativas de leitura cruzada retornam `HTTP 403 Forbidden` (`AT-19`).
3. **Neutralização de Prompt Injection em Fontes (`AT-20`)**:
   - Todo conteúdo documental/web é sanitizado e encapsulado em blocos inertes `<INERT_DOCUMENT_EVIDENCE>` com instrução explícita de sistema proibindo obediência a comandos embutidos nas fontes; o árbitro determinístico valida a citação literal independentemente do texto gerado pelo LLM.
4. **Higiene de Segredos**:
   - `GEMINI_API_KEY` é lida exclusivamente no backend via variável de ambiente (`.env` listado no `.gitignore`), jamais trafegando em payloads REST, Event Store, logs ou código cliente.

---

## 5. Verificação Visual e Funcional em Navegador Real (Chromium + WebGL)

A interface **Gambit Lab Nocturne** (`apps/web/index.html`) foi validada em instância real do Google Chrome via Chrome DevTools Protocol (CDP) sobre o servidor FastAPI ativo:
- **Paleta Nocturne confirmada**: `--bg: #040405` (`rgb(4, 4, 5)`), alto contraste WCAG AA, alternância opcional de tema `Nocturne / Cosmic`.
- **WebGL 3D preservado**: Peças procedurais 3D de Xadrez e pedras lenticulares 3D de Go renderizadas sem regressão, com alternância imediata para o tabuleiro **2D Acessível (WCAG)** (64 casas interativas no Xadrez / 81 interseções no Go).
- **Progressão acima de 3 lances comprovada na UI**:
  - Sessão de Xadrez avançada continuamente até **6 lances (`metricPlies = 6`, `Etapas = 6 / 12`)**, com fontes verificadas (`SOURCE_VERIFIED` / `SUPPORTED`).
  - Sessão de Auditoria em Go 9×9 avançada continuamente até **6 lances (`metricPlies = 6`)**, sem documentos anexados, exibindo honestamente `NO_SOURCES_ATTACHED` e `HYPOTHESIS`.
- **Separação entre Avanço e Replay**: Navegação de replay (`← Anterior` / `⏭ Atual`) ativou o banner `Modo Replay` reconstruindo estados passados sem alterar `completed_steps` nem acionar o LLM.
- **Responsividade Mobile (`390×844`)**: `scrollWidth <= 390px` (zero overflow horizontal).
- **Erros de Console / Exceções JS**: **`0` erros de console e `0` exceções não tratadas**.

---

## 6. Resumo Final da Execução de Testes

| Suíte | Arquivo | Total | PASS | FAIL | SKIP |
| :--- | :--- | :---: | :---: | :---: | :---: |
| Motores Determinísticos (Xadrez FIDE & Go 9×9) | `tests/unit/test_chess_engine.py`, `tests/unit/test_go_engine.py` | 15 | **15** | 0 | 0 |
| Event Store SHA-256, Concorrência & Replay | `tests/unit/test_event_store.py` | 4 | **4** | 0 | 0 |
| Pipeline FUSION Multi-Estratégia | `tests/unit/test_fusion_pipeline.py` | 2 | **2** | 0 | 0 |
| Endpoints REST & Matriz 3×2 (`AC-01`..`AC-06`) | `tests/integration/test_api_endpoints.py` | 10 | **10** | 0 | 0 |
| Fluxo Conversacional, Segurança & Camadas Epistêmicas | `tests/integration/test_cosmic_flow.py`, `test_security_isolation.py`, `test_verification_tiers.py` | 9 | **9** | 0 | 0 |
| **Suíte de Aceite Reengenharia Nocturne (`AT-01`..`AT-24`)** | `tests/integration/test_nocturne_reengineering.py` | 24 | **24** | 0 | 0 |
| **Testes Ao Vivo Google Gemini + Web Pública (`LIVE_WEB`)** | `tests/live/test_gemini_live.py` | 2 | **2** | 0 | 0 |
| **TOTAL GERAL** | **10 arquivos de teste** | **66** | **66** | **0** | **0** |



---

## 7. Reengenharia v2.2: Research Match, Fundo Vivo e Dossiês de Peças

Em conformidade com os novos requisitos do produto ("Fundo Vivo", partidas completas sem morte em 12 lances, isolamento estrito de pesquisa Pró vs Contra, dossiês por peça e desacoplamento do veredito científico), a arquitetura foi estendida com o motor modular `services/api/match/` e a interface Nocturne v2.2:

### 7.1 Fundo Vivo & Parallax Cósmico
- Implementado canvas de estrelas em 3 camadas de profundidade (distante, intermediária, próxima) com velocidades e densidades diferenciadas.
- Adicionado drift cósmico contínuo suave com renovação de bordas e interpolação de mouse parallax.
- Inserido controle acessível `#motionBtn` na barra de navegação para alternar a animação (respeitando `prefers-reduced-motion`).

### 7.2 Partida Completa em 7 Estágios Determinísticos
1. `DEFINING_SIDES`: Identificação substantiva do tema e teses centrais.
2. `PRO_RESEARCH`: Coleta em cofre privado isolado (HTTP 403 para a parte adversa).
3. `CONTRA_RESEARCH`: Coleta contrária estritamente isolada em cofre independente.
4. `DOSSIER_ASSIGNMENT`: Atribuição de papéis, teses e evidências a cada peça (32 no Xadrez).
5. `LUDIC_SIMULATION`: Jogo completo em `python-chess` / `GoEngine9x9` até critério formal de término (xeque-mate, resignação com déficit de 800 cp por 3 lances, dois passes no Go ou `BUDGET_EXHAUSTED` explícito e retomável).
6. `SYNTHESIS`: Síntese cruzada com desacoplamento lúdico vs epistêmico.
7. `REPLAY_SEALED`: Hash chain SHA-256 selada para auditoria sem LLM.

### 7.3 Conclusão Dual Desacoplada e Ponto de Virada
- **Resultado Lúdico**: Apura o vencedor pelas regras do jogo (`WHITE_WINS`, `BLACK_WINS`, `DRAW`, `UNDECIDED`).
- **Veredito Epistêmico**: Determinado unicamente por citações literais auditadas (`PRO_THESIS_SUPPORTED`, `CONTRA_THESIS_SUPPORTED`, `INCONCLUSIVE`, `OPEN_HYPOTHESIS`).
- **Botão Ponto de Virada (`⚡ Ponto de Virada`)**: Posiciona o cursor de replay diretamente no lance chave onde a disputa argumentativa foi decidida.

### 7.4 5ª Aba Analítica: Peças & Teses
- Apresenta os dossiês de todas as peças em jogo, com glifos, lado (⚪ Pró / ⚫ Contra), status epistêmico (`SUPPORTED`, `CONTESTED`, `FALLEN`, etc.), barra de confiança percentual e alegação textual vinculada.
- Clique em qualquer casa do tabuleiro 2D/3D exibe o dossiê da peça correspondente no modal e permite saltar para a aba analítica.

---

## 8. Tabela de Verificação Consolidada (Final v2.2)

| Componente | Testes Automatizados | Status |
| :--- | :---: | :---: |
| Motores de Jogo (FIDE Chess + Go 9×9) | 15 unitários | **PASS (100%)** |
| Event Store SHA-256 e Concorrência | 4 unitários | **PASS (100%)** |
| FUSION Pipeline Multi-Estratégia | 2 unitários | **PASS (100%)** |
| Endpoints REST & Aplicações 3×2 | 10 integração | **PASS (100%)** |
| Camadas de Verificação e Segurança | 9 integração | **PASS (100%)** |
| Reengenharia Nocturne R1.0 (`AT-01`..`AT-24`) | 24 integração | **PASS (100%)** |
| **Research Match v2.2 (`RM-01`..`RM-17`)** | **17 integração** | **PASS (100%)** |
| **Automação de Navegador Real (CDP)** | **6 cenários** | **PASS (100%)** |
| **TOTAL CONSOLIDADO** | **81 unit/int + 6 CDP** | **87 / 87 PASS (100%)** |


---

## 7. Reengenharia v2.3 — UI Nocturne Focus e Resolução de C01–C12

Em resposta à auditoria formal de produto e aos achados de integridade científica (`GAMBIT_LAB_V23_AUDITORIA_REENGENHARIA.md`), a versão **v2.3 (Nocturne Focus)** promoveu o redesenho da experiência: **"Xadrez/Go primeiro, lance e evidência depois"**, aliada à correção rigorosa das premissas epistêmicas.

### Tabela de Resolução dos Achados C01–C12

| ID | Achado Auditado | Resolução v2.3 | Evidência / Teste |
|---|---|---|---|
| **C01** | `preparation.py` marcava `SUPPORTED` apenas por localizar trecho literal | Citação verificada no arquivo marca `SOURCE_VERIFIED`; `SUPPORTED` exige validação semântica da tese forte | `test_c01_quote_found_does_not_equal_supported` (**PASS**) |
| **C02** | Captura física gerava `REFUTED` no histórico da peça | Captura no tabuleiro físico `PIECE_CAPTURED` registra `NOT_ASSESSED` ou `INCONCLUSIVE`, jamais `REFUTED` automático | `test_c02_physical_capture_does_not_equal_refuted` (**PASS**) |
| **C03** | Confiança multiplicada por tipo de peça (Rei 2.6x, Dama 2.3x) e fontes duplicadas somadas | Pesos unitários (`1.0`); deduplicação estrita de claims e fontes por hash/DOI na síntese epistêmica | `test_c03_no_piece_weight_multiplication_and_deduplication` (**PASS**) |
| **C04** | Resignação automática após 800cp por 3 turnos gerava término forçado | Resignação automática desabilitada por padrão (`DEFAULT_AUTO_RESIGN=False`); regras FIDE oficiais governam xeque-mate e empates | `test_c04_default_chess_disables_auto_resignation_and_honors_fide` (**PASS**) |
| **C05** | Portão epistêmico rejeitava capturas legais no xadrez padrão | No xadrez padrão FIDE, capturas legais nunca são bloqueadas; avaliação epistêmica segue paralela | `test_c05_legal_captures_not_blocked_in_standard_chess` (**PASS**) |
| **C06** | Ausência de coordenadas externas visíveis no tabuleiro | Rótulos externos legíveis nos modos 2D e 3D: Xadrez `a–h`, `1–8`; Go `A B C D E F G H J` (sem `I`), `1–9` | `nocturne_v23_board_2d_coordinates.png`, `nocturne_v23_board_3d_coordinates.png` (**PASS**) |
| **C07** | Poluição visual: 4 cartões de métricas e até 32 dossiês ocupando a dobra | Layout focado no tabuleiro + painel contextual **LANCE SELECIONADO**; 32 dossiês virtualizados sob demanda | `nocturne_v23_workspace_focus.png`, `nocturne_v23_lance_selecionado.png` (**PASS**) |
| **C08** | Badges permanentes na navbar poluindo o topo | Navbar minimalista com modal **Diagnóstico & Estado**; sidebar retrátil e drawer mobile com teclado/ESC | `nocturne_v23_sidebar_collapsed.png`, `nocturne_v23_diagnostics_modal.png` (**PASS**) |
| **C09** | Scores arbitrários (.82, .88) usados como probabilidade de verdade | Estados discretos calibrados: `UNVERIFIED`, `SOURCE_VERIFIED`, `EVIDENCE_REVIEWED`, `SUPPORTED`, `REFUTED`, `INCONCLUSIVE` | `test_c09_discrete_epistemic_states_no_arbitrary_floats` (**PASS**) |
| **C10** | Inconsistência entre término lúdico e status da sessão | Resultado lúdico, FEN final e encerramento derivados exclusivamente do evento terminal oficial | `test_rm06_chess_ends_only_by_rule_or_explicit_budget` (**PASS**) |
| **C11** | Falta de evento de confrontação semântica auditável por lance | `MoveAuditPayloadSchema` em cada ply com SAN, UCI, peça, oponente, evidências, veredito e board_outcome | `test_c11_timeline_contains_audit_confrontation_payload` (**PASS**) |
| **C12** | Possível vazamento de dossiês não jogados para observador | Controle estrito de acesso por papéis (`owner`, `white`, `black`, `observer`). Dossiês não jogados são redigidos até abertura no tabuleiro | `test_c12_viewer_privacy_for_unplayed_dossiers` (**PASS**) |

### Resultados da Suíte Automatizada v2.3

- Total de testes no repositório: **90 testes aprovados (`90 PASSED, 0 FAILED`)**
- Verificação funcional no Google Chrome real via CDP: **Cenários UX01 a UX07 aprovados com 100% de sucesso**.

---

## 8. Auditoria de Rastreabilidade e Coordenadas v2.3.1 (Resolução T01–T06)

Em atendimento à auditoria de rastreamento de lances e alinhamento visual, a versão **v2.3.1** corrigiu as 6 inconsistências críticas de integração entre tabuleiro, histórico e painel de evidências:

| ID | Problema Auditado | Causa Raiz Técnica | Resolução Implementada | Evidência / Teste |
|---|---|---|---|---|
| **T01** | Painel "Lance Selecionado" vazio ao carregar partida | `loadMatchAndPieces` não disparava a seleção do último lance no painel após obter os dados | Invocação automática de `selectMoveByPly(activeMatchTimeline.length, false)` com dados sincronizados (SAN, peça, tese, evidência e veredito) | `nocturne_v23_1_lance_selecionado_auto.png` (**PASS**) |
| **T02** | Replay sem rastreabilidade completa | Busca de `timeline` em endpoint de resumo onde o payload era mantido leve | `activeMatchTimeline` desacoplado e lido de `GET /sessions/{id}/match`, garantindo replay auditável de todos os lances | `nocturne_v23_1_replay_plies_1_to_10.png` (**PASS**) |
| **T03** | Mapeamento divergente entre evento e lance | `MatchPlyRecordSchema` não armazenava o `move_event_seq` do `EventStore` | Adicionado campo `move_event_seq` em `MatchPlyRecordSchema` e `MoveAuditPayloadSchema`, gravado atomicamente em `recording.py` | `test_v23_epistemic_audit.py` (**PASS**) |
| **T04** | Coordenadas 2D deslocadas | Moldura externa flex com espaçamento divergente das células `.cell-2d` | Estrutura CSS Grid `.board-2d-inner` com ranks `8..1` e files `a..h` matematicamente alinhados 1:1 com as casas | `nocturne_v23_1_2d_aligned_grid.png` (**PASS**) |
| **T05** | Coordenadas 3D fora de perspectiva | Rótulos HTML externos ao redor do canvas sem matriz de câmera | Overlay sincronizado `<canvas id="stageCoordsOverlay">` projetando rótulos diretamente no espaço de tela via matriz de câmera `vp` | `nocturne_v23_1_3d_perspective_coords.png` (**PASS**) |
| **T06** | Citações e capturas exibidas sem rigor | Interface assumia texto localizado como prova factual e capturas como refutação | Badges honestos: "✓ Citação verificada no arquivo" vs "⚠️ Citação anexada; relevância semântica pendente"; capturas preservam veredito neutro (`INCONCLUSIVE`) | Testes E2E CDP 2 e 3 (**PASS**) |

### Resultados Consolidados v2.3.1
- **Suíte Pytest Total**: 90 testes aprovados (`90 passed, 0 failed, 1 warning`).
- **Suíte E2E CDP v2.3.1**: 6 cenários aprovados com gravação de telas comprovando a resolução de T01 a T06.

---

## 9. Redesign e Consolidação de Produto v2.4 (Resolução R01–R07)

A versão **v2.4.0** implementou a reformulação completa de experiência e simplificação arquitetural demandada pelo usuário e baseada nos templates Stitch:

| ID | Item do Redesign | Causa / Requisito | Resolução Implementada | Evidência / Screenshot |
|---|---|---|---|---|
| **R01** | Simplificação para 2 Modos Principais | Funcionalidades concorrentes na Home e excesso de jargões técnicos | Interface focada em **Debate de Evidências** (`debate`) e **Auditoria de Controles** (`audit`). A antiga Pesquisa Estratégica foi aposentada e suas ferramentas (Web, cofre, FUSION) integradas ao Debate. Sessões legadas `research` continuam legíveis. | `nocturne_v24_home_redesign.png` (**PASS**) |
| **R02** | Tema Único NOCTURNE | Tema azul Cosmic poluidor concorrendo com o foco analítico | Eliminação total do tema azul Cosmic. Identidade estrita Nocturne: `#08080A`, `#111114`, `#18181D`, `#202028`, `#2B2B32` e violeta discreto `#A78BFA`. Fundo estelar sutil em monocromático com drift e parallax suave. | E2E CDP Passo 1 (**PASS**) |
| **R03** | Xadrez 2D SVG Profissional como Padrão | Visualização 3D como padrão gerava sobrecarga e 2D usava glifos de texto desalinhados | 2D definido como padrão inicial (`viewMode = '2d'`). Renderização SVG 800×800 pura com 12 peças vetoriais nítidas do Stitch (`#w-pawn`, `#b-king`, etc.), seta vetorial do lance (`marker-end="url(#arrow-move)"`), coordenadas de canto internas e inversão de tabuleiro (`#flipBoardBtn`). | `nocturne_v24_debate_2d_chess.png`, `nocturne_v24_debate_board_flipped.png` (**PASS**) |
| **R04** | Go 9×9 2D SVG Refinado | Grade anterior simples sem textura ou profundidade | Tabuleiro em madeira escura `#1B1B22`, linhas `#33333F`, pedras com gradiente radial e filtro de sombra projetada (`#stoneShadow`), anel pulsante no último lance e coordenadas `A..H, J` e `1..9`. | `nocturne_v24_audit_2d_go.png` (**PASS**) |
| **R05** | Replay Bar com Play/Pause e Notação Clicável | Navegação manual passo a passo cansativa sem visão geral da timeline | Botão `#repPlayPauseBtn` avança lances a cada 1.5s automaticamente; barra de notação SAN clicável (`#replayMovesStrip`) permite saltar diretamente para qualquer lance com destaque ativo. | E2E CDP Passo 3 (**PASS**) |
| **R06** | Painel Contextual Adaptativo por Modo | Auditoria em Go ou Xadrez não exibia requisitos normativos nem riscos estruturados | Adicionado modelo e preenchimento de `control_audit` no backend (`schemas.py`, `preparation.py`, `play.py`) e painel `#smpAuditBox` na UI: requisito normativo (ISO 27001, SOC 2, NIST, LGPD), badges de risco e conformidade, critérios esperados, evidências, achados e recomendações. | `nocturne_v24_audit_2d_go.png` (**PASS**) |
| **R07** | Segurança e Higiene de Pacotes (CRÍTICO) | Risco de distribuição acidental de chaves de API em arquivos `.env` | Atualizado `scratch/create_release_zip.py` com `EXCLUDE_FILES = {".env"}` e validação pós-geração obrigatória que falha caso `.env` esteja presente ou `.env.example` esteja ausente. | `create_release_zip.py` (**VERIFIED**) |

### Resultados Consolidados v2.4
- **Suíte Pytest Completa**: **90 passed, 0 failed, 1 warning**.
- **Suíte E2E CDP Real**: Todos os 5 passos aprovados com 4 telas de alta fidelidade capturadas.
- **Pacote de Distribuição**: `Gambit_Lab_v2.4_Nocturne_Redesign.zip` verificado e livre de segredos.



---

## 10. Refinamento de Apresentação, Peças Cburnett e Partidas Longas v2.4.1 (Resoluções P01–P06)

Em atendimento à avaliação de interface e rigor funcional solicitada pelo usuário, a versão **v2.4.1** implementou o refinamento cirúrgico de apresentação:

| ID | Item Refinado | Causa / Requisito | Resolução Implementada | Evidência / Screenshot |
|---|---|---|---|---|
| **P01** | 3D Real (WebGL) como Apresentação Principal | 3D visualmente superior e mais elegante para o tema Nocturne | 3D restaurado como modo padrão (`viewMode = '3d'`); enquadramento aproximado (`radius = 11.2`, `phi = 0.82`); botão `#resetCamBtn` (`↺ Câmera`) restaurando o enquadramento ideal. | `nocturne_v24_1_3d_close_framed.png` (**PASS**) |
| **P02** | Reconstrução do 2D SVG com Peças Cburnett | Grade anterior deslocada à direita com área morta e peças simplificadas | Grade centralizada 1:1 sem coluna externa morta (`max-width: 500px`); 24 símbolos vetoriais clássicos SVG Cburnett de `python-chess` em marfim `#F8F8FA` e obsidiana `#22232B`; rótulos de coordenadas nos cantos periféricos; peças mantidas em pé na inversão. | `nocturne_v24_1_2d_cburnett_centered.png` (**PASS**) |
| **P03** | Painel Narrativo Simplificado de Lance | Múltiplos cartões técnicos dispersos prejudicando o fluxo investigativo | Painel unificado em narrativa contínua: 1. Cabeçalho minimalista; 2. O que este movimento representa?; 3. Qual evidência foi utilizada?; 4. Avaliação do Árbitro; 5. Auditoria de Controles; 6. Auditoria técnica e telemetria colapsadas em `<details>`. | `nocturne_v24_1_narrative_panel.png` (**PASS**) |
| **P04** | Barra de Replay em Pares Numerados | Lances exibidos em lista corrida sem padrão oficial de notação | Notação oficial em pares numerados (`1. e4 e5   2. Nf3 Nc6 ...`) estilo planilha oficial com auto-scroll suave. | `nocturne_v24_1_replay_pairs_strip.png` (**PASS**) |
| **P05** | Honestidade Epistemológica no Encerramento | Teto de lances não deve inventar vencedor nem forçar empate | Esgotamento de orçamento (60 lances) explicitamente rotulado como `"⏳ Partida não concluída — Orçamento esgotado"`, com botão `[ ▶ Retomar Partida ]` sem forçar término falso. | `nocturne_v24_1_budget_exhausted_honest.png` (**PASS**) |
| **P06** | Partidas Reais Longas (60 Lances) | Necessidade de testar estabilidade e sincronia em partidas de 30 a 60 lances | Execução e validação de partidas completas de 60 lances em Xadrez e Go, comprovando sincronia de dossiês, evidências e tabuleiro em cada lance. | `nocturne_v24_1_audit_go_cburnett.png` (**PASS**) |

### Resultados Consolidados v2.4.1
- **Suíte Pytest Completa**: **90 passed, 0 failed, 1 warning**.
- **Suíte E2E CDP Real (v2.4.1)**: Todos os 8 passos aprovados com 6 telas comprobatórias capturadas em alta definição.
