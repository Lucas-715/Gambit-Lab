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
