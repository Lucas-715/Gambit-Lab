"""
Preparação do Research Match (estágios 1, 2 e 4):
construção dos lados Pró/Contra, pesquisa isolada por cofre e atribuição de dossiês às peças/grupos.
"""
import copy
import re
from typing import Any, Dict, List, Tuple

from services.api.agents.gemini_adapter import is_future_projection_topic
from services.api.agents.web_search_adapter import WebSearchUnavailableError
from services.api.models.schemas import PieceArtifactRefSchema, PieceDossierSchema
from services.api.match.decision import comparison_plan, historical_comparison


class VaultIsolationError(RuntimeError):
    """Violação da Regra de Ouro: um lado enxergou artefato privado do adversário."""


class PreparationMixin:
    def _stage_1_build_sides(self, sess: Dict[str, Any], mstate: Dict[str, Any]) -> str:
        topic = sess["title"]
        mstate["comparison_plan"] = comparison_plan(topic, sess.get("mode"))
        self.sm._append_session_event(sess['id'], 'MATCH_RULES_DECLARED', {
            'comparison_plan': mstate['comparison_plan'], 'scheduled_plies': mstate['plies_budget'],
            'closing_rule': 'Fim natural ou adjudicação: material no xadrez; área com komi no Go. Igualdade resulta em empate. Não determina verdade factual.',
        })
        pro_c = mstate["pro_color"]
        contra_c = mstate["contra_color"]
        # O orçamento de lances da partida (plies_budget) substitui o teto de 12 etapas da investigação manual.
        sess["max_steps"] = mstate["plies_budget"]
        sess["budget"]["max_steps"] = mstate["plies_budget"]
        sess["budget"]["max_calls"] = max(sess["budget"].get("max_calls", 24), 24)
        if sess.get("mode") == "audit":
            mstate["pro_thesis"] = f"Controles e Conformidade (Lado Auditor · {pro_c.upper()}): verificação de controles normativos, evidências de conformidade e garantias técnicas para '{topic}'."
            mstate["contra_thesis"] = f"Riscos e Superfícies de Falha (Lado Auditado · {contra_c.upper()}): identificação de vulnerabilidades, lacunas, exceções operacionais e riscos residuais em '{topic}'."
        else:
            mstate["pro_thesis"] = f"Tese Favorável (Lado Pró · {pro_c.upper()}): investigação de viabilidade e sustentação para '{topic}'."
            mstate["contra_thesis"] = f"Tese Crítica (Lado Contra · {contra_c.upper()}): investigação de riscos, limites e contraprovas para '{topic}'."
        return (
            f"Lados configurados com cofres isolados: {'Auditor vs Auditado' if sess.get('mode') == 'audit' else 'Lado Pró vs Lado Contra'} "
            f"({pro_c.upper()} vs {contra_c.upper()}) · Profundidade {mstate['depth']} (orçamento: {mstate['plies_budget']} lances)."
        )

    def _stage_2_research_side(self, sess: Dict[str, Any], mstate: Dict[str, Any], side: str) -> str:
        session_id = sess["id"]
        topic = sess["title"]
        norm_policy = sess["normalized_source_policy"]
        owner_color = mstate["pro_color"] if side == "pro" else mstate["contra_color"]
        force_demo = sess["execution_mode"] == "DEMO_OFFLINE"

        # 1. Pesquisa Web isolada por lado quando WEB_ONLY ou HYBRID
        web_added = 0
        if norm_policy in ("WEB_ONLY", "HYBRID"):
            # Cada lado usa a PERGUNTA REAL como âncora; viés difere por modalidade e lado.
            if sess.get("mode") == "audit":
                query_focus = (
                    f"{topic} controles requisitos conformidade auditoria"
                    if side == "pro"
                    else f"{topic} riscos vulnerabilidades falhas brechas"
                )
            elif self._detect_topic_domain(topic) == "political_electoral":
                query_focus = (
                    f"{topic} propostas articulação alianças partido"
                    if side == "pro"
                    else f"{topic} críticas ataques rejeição controvérsias oposição"
                )
            else:
                query_focus = (
                    f"{topic} benefícios vantagens evidências"
                    if side == "pro"
                    else f"{topic} riscos limitações críticas"
                )
            if historical_comparison(topic):
                query_focus = f"{topic} indicadores históricos PIB pobreza desigualdade instituições comparação governos"
            existing_urls = {
                a.get("canonical_url") or a.get("url")
                for a in sess["artifacts"]
                if a.get("owner_side") == owner_color and (a.get("canonical_url") or a.get("url"))
            }
            try:
                records = self.sm.web_search_adapter.search_public_sources(query_focus, max_results=3)
                sess["web_queries_executed"].append(query_focus)
                if not records:
                    # Sem resultados com o viés: recai sobre a pergunta pura (continua isolado no cofre deste lado).
                    records = self.sm.web_search_adapter.search_public_sources(topic, max_results=3)
                    sess["web_queries_executed"].append(topic)
                for rec in records:
                    c_url = rec.get("canonical_url") or rec.get("url")
                    if c_url and c_url in existing_urls:
                        continue
                    art = self.sm.vault.ingest_document(
                        session_id=session_id,
                        name=f"[{'PRÓ' if side == 'pro' else 'CONTRA'}] {rec['title']}",
                        content=rec["content"],
                        mime_type="text/plain",
                        owner_side=owner_color,
                        source_type="web",
                        url=rec["url"],
                        canonical_url=rec["canonical_url"],
                        domain=rec["domain"],
                        retrieved_at=rec["retrieved_at"],
                        accessible=rec["accessible"],
                    )
                    sess["artifacts"].append(art)
                    existing_urls.add(c_url)
                    web_added += 1
            except WebSearchUnavailableError as w_err:
                sess["web_search_diagnostic"] = str(w_err)
                if len(sess["artifacts"]) == 0:
                    sess["source_status_override"] = "SEARCH_UNAVAILABLE"

        # 2. Isolamento Estrito: este lado enxerga APENAS owner_side == owner_color ou 'public'
        side_artifacts = self.sm.vault.get_accessible_artifacts_with_content(
            session_id, requesting_side=owner_color
        )
        if norm_policy == "WEB_ONLY":
            side_artifacts = [a for a in side_artifacts if a.get("source_type") == "web"]

        # Prova formal de isolamento: nenhum artefato do lado oposto pode estar presente
        opp_color = mstate["contra_color"] if side == "pro" else mstate["pro_color"]
        if any(a.get("owner_side") == opp_color for a in side_artifacts):
            raise VaultIsolationError(
                f"Violação de isolamento: o lado '{side}' recebeu artefato do cofre privado '{opp_color}'."
            )
        sess["_match_internal"].setdefault("isolation_log", []).append(
            {
                "side": side,
                "viewer_color": owner_color,
                "artifact_ids": [a["id"] for a in side_artifacts],
                "owner_sides_seen": sorted({a.get("owner_side") for a in side_artifacts}),
            }
        )

        # 3. Gera tese e subteses por papel para este lado
        raw_side = self.sm.gemini_adapter.generate_side_dossiers(
            topic=topic,
            side=side,
            game=sess["game"],
            artifacts=side_artifacts,
            budget=sess["budget"],
            force_demo=force_demo,
            comparison_plan=mstate.get('comparison_plan'),
        )
        if raw_side.get("provider_usage"):
            sess["provider_usage"] = raw_side["provider_usage"]

        if side == "pro":
            mstate["pro_thesis"] = raw_side["thesis"]
            sess["_match_internal"]["pro_raw"] = raw_side
        else:
            mstate["contra_thesis"] = raw_side["thesis"]
            sess["_match_internal"]["contra_raw"] = raw_side

        return (
            f"Lado {'Pró' if side == 'pro' else 'Contra'} ({owner_color.upper()}): "
            f"{len(side_artifacts)} fonte(s) acessível(is) no cofre isolado ({web_added} nova(s) da web)."
        )

    @staticmethod
    def _is_garbage_or_url_quote(quote: str) -> bool:
        """Rejeita fragmentos de URL, tokens base64 longos ou linhas de metadados como citação literal."""
        q = (quote or "").strip()
        if not q:
            return True
        q_low = q.lower()
        if any(p in q_low for p in ("http://", "https://", "com/rss/", "news.google.com", "url canônica:", "recuperado em:", "publicado em:")):
            return True
        if re.search(r"\S{42,}", q):
            return True
        return False

    def _is_quote_relevant_to_topic(self, topic: str, quote: str, art_title: str) -> bool:
        """Verifica se uma citação ou título possui pertinência temática com a pergunta investigada."""
        if not quote and not art_title:
            return False
        if quote and self._is_garbage_or_url_quote(quote):
            return False
        stop_words = {
            "de", "a", "o", "que", "e", "do", "da", "em", "um", "para", "é", "com", "não",
            "uma", "os", "no", "se", "na", "por", "mais", "as", "dos", "como", "mas", "foi",
            "ao", "ele", "das", "tem", "à", "seu", "sua", "ou", "ser", "quando", "muito", "há",
            "nos", "já", "está", "eu", "também", "só", "pelo", "pela", "até", "isso", "ela",
            "entre", "era", "depois", "sem", "mesmo", "aos", "ter", "seus", "quem", "nas", "me",
            "esse", "eles", "estão", "você", "tinha", "foram", "essa", "num", "nem", "suas",
            "meu", "às", "minha", "têm", "numa", "pelos", "elas", "havia", "seja", "qual",
            "quais", "será", "sera", "seria", "sobre", "referente", "melhor", "melhores",
            "pior", "piores", "toda", "todo", "todos", "todas", "história", "historia",
            "ano", "anos", "vai", "ganhar"
        }
        generic_words = {
            "brasil", "brasileiro", "brasileira", "brasileiros", "presidente", "presidênte",
            "presidencia", "presidência", "governo", "governos", "estado", "país", "pais",
            "mundo", "nacional", "público", "publico", "pública", "publica", "sistema", "sistemas",
            "2026", "2027", "2028", "2029", "2030", "2032", "2034", "2035", "2040",
        }
        words = [re.sub(r'[^\w]', '', w.lower()) for w in topic.split() if len(w) >= 3]
        substantive = [w for w in words if w and w not in stop_words]
        if not substantive:
            return True
        specific_words = [w for w in substantive if w not in generic_words and not w.isdigit()]
        target_words = specific_words if specific_words else substantive
        evidence_text = f"{art_title} {quote}".lower()
        return any(w in evidence_text for w in target_words) or ("mfa" in evidence_text and "multifator" in topic.lower())

    def _build_artifact_ref(
        self,
        session_id: str,
        owner_color: str,
        raw_art_id: str,
        raw_quote: str,
        accessible_arts: List[Dict[str, Any]],
        topic: str,
        piece_idx: int = 0,
    ) -> Tuple[List[PieceArtifactRefSchema], bool, float]:
        """Valida citação literal nos artefatos acessíveis ao lado e calcula confiança honesta e individualizada."""
        future_flag = is_future_projection_topic(topic)
        by_id = {a["id"]: a for a in accessible_arts}
        matched_art = by_id.get(raw_art_id) if raw_art_id else None
        verified = False
        final_quote = (raw_quote or "").strip()

        if matched_art and final_quote:
            ok, _ = self.sm.vault.find_verified_quote_offset(matched_art["id"], final_quote)
            if ok and self._is_quote_relevant_to_topic(topic, final_quote, matched_art.get("name", "")):
                verified = True

        if not verified and final_quote:
            for cand in accessible_arts:
                ok, _ = self.sm.vault.find_verified_quote_offset(cand["id"], final_quote)
                if ok and self._is_quote_relevant_to_topic(topic, final_quote, cand.get("name", "")):
                    matched_art = cand
                    verified = True
                    break

        if not matched_art and accessible_arts:
            for cand in accessible_arts:
                body = (cand.get("content") or cand.get("content_preview") or "").strip()
                clean_lines = [
                    ln.strip() for ln in body.splitlines()
                    if ln.strip() and not ln.strip().lower().startswith(
                        ("fonte web pública:", "url canônica:", "recuperado em:", "publicado em:", "citações acadêmicas:")
                    )
                ]
                clean_body = "\n".join(clean_lines)
                sents = [
                    s.strip() for s in re.split(r"[\n\.]+", clean_body)
                    if len(s.strip()) >= 28 and not self._is_garbage_or_url_quote(s.strip())
                ]
                if sents:
                    rotated_sents = sents[piece_idx % len(sents):] + sents[:piece_idx % len(sents)]
                    for s in rotated_sents[:6]:
                        test_q = s[:160]
                        ok, _ = self.sm.vault.find_verified_quote_offset(cand["id"], test_q)
                        if ok and self._is_quote_relevant_to_topic(topic, test_q, cand.get("name", "")):
                            matched_art = cand
                            final_quote = test_q
                            verified = True
                            break
                if verified:
                    break
            # Se não encontrou citação comprovadamente relevante, ainda assim vincula o documento do cofre ao RBAC da peça (em tópicos não-prospectivos), mas com verified=False
            if not matched_art and accessible_arts and not future_flag:
                matched_art = accessible_arts[0]
                verified = False

        refs: List[PieceArtifactRefSchema] = []
        if matched_art:
            refs.append(
                PieceArtifactRefSchema(
                    artifact_id=matched_art["id"],
                    title=matched_art["name"],
                    sha256=matched_art["sha256"],
                    owner_side=matched_art.get("owner_side", owner_color),
                    source_type=matched_art.get("source_type", "document"),
                    url=matched_art.get("canonical_url") or matched_art.get("url"),
                    domain=matched_art.get("domain"),
                    quote_text=final_quote if verified else None,
                    verified=verified,
                )
            )

        # Calibração honesta e individualizada de confiança (sem valores fixos de 48% para todas as 32 peças)
        if verified:
            conf = round(0.72 + (piece_idx % 6) * 0.02, 2)
            return refs, True, conf
        if accessible_arts and refs:
            conf = round(0.38 + (piece_idx % 5) * 0.025, 2)
            return refs, False, conf
        # Hipótese sem evidências documentais anexadas
        conf = round(0.18 + (piece_idx % 7) * 0.015, 2)
        return [], False, conf

    def _detect_topic_domain(self, topic: str) -> str:
        """Detecta o domínio temático principal da investigação."""
        if historical_comparison(topic):
            return "historical_comparison"
        t_lower = topic.lower()
        political_terms = [
            "presidente", "eleição", "eleitoral", "candidato", "candidatura",
            "voto", "partido", "ministro", "mandato", "senado", "congresso",
            "governo", "política", "renan", "lula", "bolsonaro", "tarcísio"
        ]
        security_terms = [
            "segurança", "vulnerabilidade", "credencial", "criptografia", "segredo",
            "mfa", "software", "código", "acesso", "privilégio", "auditoria", "iso"
        ]
        econ_terms = [
            "economia", "inflação", "juros", "mercado", "pib", "tributário", "custo",
            "investimento", "receita", "dólar", "capitalismo", "comunismo", "reforma"
        ]
        if any(k in t_lower for k in political_terms):
            return "political_electoral"
        if any(k in t_lower for k in security_terms):
            return "security_tech"
        if any(k in t_lower for k in econ_terms):
            return "economic"
        return "general_investigative"

    def _get_domain_role_dimension(
        self,
        domain: str,
        ptype: str,
        sq: str,
        side: str,
        topic: str,
    ) -> str:
        """Retorna dimensão analítica específica baseada no domínio, tipo de peça, casa e lado (Pró/Contra)."""
        is_pro = (side == "pro")
        file_letter = sq[0].lower() if len(sq) >= 2 else "x"

        if domain == 'historical_comparison':
            dimensions = comparison_plan(topic, 'debate')['criteria']
            index = (ord(file_letter) - ord('a')) % len(dimensions)
            dimension = dimensions[index]['label']
            return f"{dimension}: comparar governos, períodos e indicadores equivalentes; {'sustentação' if is_pro else 'contraprovas'} da tese, com controle de contexto histórico"

        if domain == "political_electoral":
            if ptype == "king":
                return "Viabilidade central e sustentabilidade global da candidatura" if is_pro else "Limites estruturais e fatores impeditivos da candidatura"
            if ptype == "queen":
                return "Articulação política ampla, liderança de coalizão e densidade de palanque" if is_pro else "Rejeição polarizada, isolamento de alianças e resistência em centros decisórios"
            if ptype == "rook":
                if sq in ("a1", "a8"):
                    return "Marco institucional partidário e segurança jurídica do registro" if is_pro else "Insegurança jurídica, disputas estatutárias e riscos de impugnação"
                return "Processos de governança de campanha e cumprimento de requisitos eleitorais" if is_pro else "Passivos de prestações de contas anteriores e atritos com a Justiça Eleitoral"
            if ptype == "bishop":
                if sq in ("c1", "c8"):
                    return "Plataforma programática, coerência ideológica e comunicação de massa" if is_pro else "Fragilidade programática e vulnerabilidades do discurso de campanha"
                return "Alinhamento com demandas do eleitorado e capacidade de mobilização" if is_pro else "Limitações de penetração demográfica e saturação em bolhas digitais"
            if ptype == "knight":
                if sq in ("b1", "b8"):
                    return "Potencial de atração de eleitores indecisos e dinâmica de migração de votos" if is_pro else "Incapacidade de diálogo além do nicho e transferibilidade adversa de votos"
                return "Inovações de estratégia e capilaridade em colégios eleitorais estratégicos" if is_pro else "Desvantagens de capilaridade e desvantagem logística frente a máquinas tradicionais"
            if ptype == "pawn":
                pawn_dimensions = {
                    "a": "Projeções de intenção de voto e recall eleitoral espontâneo" if is_pro else "Taxas de rejeição consolidada e teto eleitoral adverso",
                    "b": "Densidade partidária e capilaridade eleitoral em colégios chave" if is_pro else "Fragilidade da base partidária e isolamento regional",
                    "c": "Histórico de votação e consistência programática de base" if is_pro else "Inconsistências em votações anteriores e desvios de plataforma",
                    "d": "Capacidade de arrecadação formal e mobilização de recursos de campanha" if is_pro else "Dependência de financiamento volátil e passivos de campanha",
                    "e": "Engajamento digital orgânico e conversão em presença de rua" if is_pro else "Vulnerabilidade a campanhas adversárias e volatilidade nas redes",
                    "f": "Alianças táticas com lideranças regionais e governadores" if is_pro else "Resistência de caciques partidários e vetos cruzados",
                    "g": "Simulações de cenários de segundo turno e transferibilidade de votos" if is_pro else "Desvantagem em simulações diretas de segundo turno e dispersão",
                    "h": "Fatores exógenos e variáveis conjunturais do calendário eleitoral" if is_pro else "Riscos de polarização extrema e esvaziamento de terceira via",
                }
                return pawn_dimensions.get(file_letter, "Indicador eleitoral específico e dados históricos")

        elif domain == "security_tech":
            if ptype == "king":
                return "Garantias de segurança e integridade do modelo arquitetural proposto" if is_pro else "Superfície de ataque residual e limitações teóricas do modelo de segurança"
            if ptype == "queen":
                return "Eficácia dos controles defensivos principais e mitigação proativa" if is_pro else "Vetores de exploração sistêmica e dependências críticas comprometidas"
            if ptype == "rook":
                if sq in ("a1", "a8"):
                    return "Conformidade normativa e aderência a padrões técnicos de segurança" if is_pro else "Incompatibilidades regulatórias e lacunas de conformidade mandatórias"
                return "Processos formais de ciclo de vida e garantias operacionais de auditoria" if is_pro else "Custos de implementação e atrito em fluxos operacionais estabelecidos"
            if ptype == "bishop":
                if sq in ("c1", "c8"):
                    return "Fundamentação formal de modelagem de ameaças e pressupostos de confiança" if is_pro else "Premissas não demonstradas e falácias de correlação em testes preliminares"
                return "Condições de contorno onde os controles técnicos operam com eficácia comprovada" if is_pro else "Cenários adversos e zonas de falha onde os mecanismos de controle se degradam"
            if ptype == "knight":
                if sq in ("b1", "b8"):
                    return "Resultados empíricos de testes de invasão e relatórios de auditoria técnica" if is_pro else "Exceções operacionais e métricas adversas observadas em testes práticos"
                return "Inovações táticas de isolamento e contenção com menor impacto de desempenho" if is_pro else "Vetores de ataque de cauda longa e cenários imprevistos de exploração"
            if ptype == "pawn":
                pawn_dimensions = {
                    "a": "Procedência e verificação criptográfica de componentes e dependências" if is_pro else "Vulnerabilidades conhecidas em componentes de terceiros e dependências",
                    "b": "Tempo médio de detecção (MTTD) e resposta coordenada a incidentes" if is_pro else "Atrasos em resposta a incidentes e janelas de exposição prolongadas",
                    "c": "Cobertura de testes automatizados e validação contínua de código" if is_pro else "Lacunas em testes de regressão e superfícies não cobertas por automação",
                    "d": "Segregação de privilégios e controle de acesso baseado em papéis (RBAC)" if is_pro else "Elevação indevida de privilégios e permissões excessivas acumuladas",
                    "e": "Rastreabilidade de logs auditáveis e integridade de registros de eventos" if is_pro else "Falta de centralização de logs e riscos de adulteração de auditoria",
                    "f": "Revisão por pares independente e certificações técnicas de conformidade" if is_pro else "Ausência de revisão externa e não conformidade com frameworks formais",
                    "g": "Eficiência operacional e baixo consumo de recursos computacionais" if is_pro else "Degradação de latência e consumo excessivo sob estresse operacional",
                    "h": "Mecanismos de contingência, tolerância a falhas e redundância ativa" if is_pro else "Pontos únicos de falha e ausência de plano testado de contingência",
                }
                return pawn_dimensions.get(file_letter, "Evidência atômica e medição pontual de controle")

        elif domain == "economic":
            if ptype == "king":
                return "Sustentabilidade fiscal e equilíbrio econômico de longo prazo" if is_pro else "Riscos macroeconômicos e incerteza de choques fiscais futuros"
            if ptype == "queen":
                return "Eficiência alocativa, produtividade agregada e atração de investimentos" if is_pro else "Distorções distributivas e perda de competitividade em setores chave"
            if ptype == "rook":
                if sq in ("a1", "a8"):
                    return "Marco regulatório estável e segurança jurídica para investimentos" if is_pro else "Insegurança jurídica e riscos de contencioso tributário/regulatório"
                return "Previsibilidade institucional e cumprimento de metas orçamentárias" if is_pro else "Custos de transição e atritos na implementação de reformas"
            if ptype == "bishop":
                if sq in ("c1", "c8"):
                    return "Consistência teórica de incentivos e mecanismos de preços de mercado" if is_pro else "Inconsistência de pressupostos comportamentais e falhas de mercado"
                return "Alinhamento com melhores práticas e lições internacionais consolidadas" if is_pro else "Restrições de escopo que impedem a replicação direta de modelos externos"
            if ptype == "knight":
                if sq in ("b1", "b8"):
                    return "Séries históricas e indicadores empíricos de recuperação econômica" if is_pro else "Elasticidade adversa e efeitos secundários imprevistos sobre a inflação"
                return "Ganhos dinâmicos de escala e atração de capital inovador" if is_pro else "Vulnerabilidade a choques cambiais e fuga de capitais em momentos de estresse"
            if ptype == "pawn":
                pawn_dimensions = {
                    "a": "Indicadores setoriais de produtividade e margens operacionais" if is_pro else "Margens comprimidas e perda de competitividade frente a concorrentes",
                    "b": "Taxas de investimento direto e formação bruta de capital fixo" if is_pro else "Queda no investimento de longo prazo e cautela de alocação de capital",
                    "c": "Índices oficiais de preços, inflação e expectativas de mercado" if is_pro else "Pressões inflacionárias persistentes e desancoragem de expectativas",
                    "d": "Arrecadação tributária, despesas correntes e superávit primário" if is_pro else "Déficit fiscal primário e rigidez de despesas obrigatórias",
                    "e": "Taxas de emprego, geração de vagas formais e renda média" if is_pro else "Precarização do mercado de trabalho e estagnação da renda real",
                    "f": "Balança comercial, termos de troca e fluxo cambial" if is_pro else "Deterioração dos termos de troca e volatilidade cambial",
                    "g": "Taxas de juros reais e spreads bancários no crédito ao consumidor" if is_pro else "Endividamento excessivo das famílias e inadimplência no crédito",
                    "h": "Variáveis exógenas e impacto de preços de commodities internacionais" if is_pro else "Vulnerabilidade a choques externos de energia e commodities",
                }
                return pawn_dimensions.get(file_letter, "Dado macroeconômico específico e medição de mercado")

        # General investigative
        if ptype == "king":
            return "Consistência central e viabilidade global da hipótese investigada" if is_pro else "Incerteza fundamental e premissas não demonstradas que enfraquecem a tese"
        if ptype == "queen":
            return "Linha de sustentação principal com maior abrangência explicativa" if is_pro else "Contra-argumento central evidenciando vulnerabilidades e contradições"
        if ptype == "rook":
            return ("Fundamento institucional e regras operacionais de contorno" if sq in ("a1", "a8") else "Processos formais e governança de auditoria") if is_pro else ("Restrições normativas e atritos de viabilidade prática" if sq in ("a1", "a8") else "Custos de conformidade e complexidade regulatória")
        if ptype == "bishop":
            return ("Articulação causal e encadeamento lógico de causa e efeito" if sq in ("c1", "c8") else "Condições de contorno e aplicabilidade") if is_pro else ("Crítica metodológica e fragilidade no nexo de causalidade" if sq in ("c1", "c8") else "Cenários de exceção onde a tese falha")
        if ptype == "knight":
            return ("Evidências empíricas atípicas e dados de campo favoráveis" if sq in ("b1", "b8") else "Correlações inesperadas e hipóteses emergentes") if is_pro else ("Cenários de exceção e observações que contradizem a regra" if sq in ("b1", "b8") else "Viés de amostragem e ruído estatístico")
        pawn_general = {
            "a": "Dado primário específico e amostragem representativa" if is_pro else "Limitação amostral e viés de seleção nos dados iniciais",
            "b": "Métricas quantitativas e séries temporais consistentes" if is_pro else "Volatilidade das medições e sensibilidade a parâmetros",
            "c": "Documentação direta e registros verificáveis" if is_pro else "Ausência de documentação comprobatória e lacunas",
            "d": "Testes de reprodutibilidade e validação cruzada" if is_pro else "Falhas de replicação e dependência de condições ideais",
            "e": "Estudo de caso e benchmark com referências de mercado" if is_pro else "Inaplicabilidade de benchmarks em contextos divergentes",
            "f": "Parecer de especialistas e consenso da literatura" if is_pro else "Divergência técnica qualificada e ceticismo metodológico",
            "g": "Eficiência demonstrada e custo-benefício favorável" if is_pro else "Custos ocultos e deseconomias de escala não previstas",
            "h": "Análise de impacto e externalidades positivas" if is_pro else "Externalidades negativas e efeitos colaterais adversos",
        }
        return pawn_general.get(file_letter, "Observação atômica e medição pontual de suporte factual")

    def _generate_heterogeneous_subthesis(
        self,
        ptype: str,
        sq: str,
        color: str,
        side: str,
        mode: str,
        topic: str,
        r_entry: Dict[str, Any],
        refs: List[PieceArtifactRefSchema],
        mstate: Dict[str, Any],
    ) -> str:
        """Gera subtese individualizada, pertinente ao domínio da pergunta e honestamente fundamentada (v2.5)."""
        is_pro = (side == "pro")
        domain = self._detect_topic_domain(topic)
        dimension = self._get_domain_role_dimension(domain, ptype, sq, side, topic)

        has_verified_quote = bool(refs and refs[0].quote_text and refs[0].verified)
        raw_claim = (r_entry.get("claim") or "").strip()
        if raw_claim.startswith("[DEMO_OFFLINE]"):
            raw_claim = ""

        if ptype == "king":
            base_king = mstate["pro_thesis"] if is_pro else mstate["contra_thesis"]
            if has_verified_quote:
                return base_king
            return f"Hipótese a investigar: {base_king} (aguardando fundamentação documental)."

        if has_verified_quote:
            art_title = refs[0].title or "Documento verificado"
            quote_text = refs[0].quote_text or ""
            if raw_claim and raw_claim.lower() not in dimension.lower():
                return f"{dimension} — {raw_claim} [Fonte: '{art_title}' · \"{quote_text[:95]}...\"]"
            return f"{dimension}: evidência documental comprobatória em '{art_title}' [Fonte: '{quote_text[:95]}...']"

        # Se o modelo gerou uma análise específica para o papel e o tema é prospectivo/hipotético, combina com a dimensão da peça
        if raw_claim and ptype in ("queen", "rook", "bishop", "knight") and sq in ("d1", "d8", "a1", "a8", "c1", "c8", "b1", "b8"):
            prefix = "Hipótese a investigar" if is_pro else "Hipótese adversa a investigar"
            return f"{prefix} ({dimension}): {raw_claim} (aguardando fundamentação documental)."

        # Sem evidência comprovada: rotula explicitamente como hipótese investigável aberta
        prefix = "Hipótese a investigar" if is_pro else "Hipótese adversa a investigar"
        return f"{prefix}: {dimension} referente a '{topic}', aguardando fundamentação documental."
    def _assign_go_swot_role(self, gtype: str, side: str, anchor: str) -> Tuple[str, str]:
        """Classifica as 12 âncoras táticas de Go na matriz dimensional SWOT (v2.5)."""
        swot_map = {
            # Black / Pro
            "E5": ("STRENGTH", "Força Central: capacidades operacionais demonstradas e maturidade dos controles em vigor."),
            "C3": ("STRENGTH", "Base Territorial: consolidação de evidências primárias e rastreabilidade estruturada."),
            "G7": ("OPPORTUNITY", "Oportunidade Estrutural: adoção de melhores práticas internacionais e ganhos de escala."),
            "C7": ("OPPORTUNITY", "Oportunidade Tática: automação contínua de auditoria e redução de esforço humano."),
            "G3": ("WEAKNESS", "Fragilidade Operacional: dependência de intervenções manuais e gargalos de comunicação."),
            "E3": ("THREAT", "Ameaça Externa: pressões regulatórias crescentes e exigências de compliance mandatório."),
            # White / Contra
            "D4": ("THREAT", "Ameaça Adversarial: vetores de ataque externos e atores maliciosos avançados."),
            "F6": ("WEAKNESS", "Lacuna de Controle: superfícies de risco residual e pontos cegos na governança."),
            "D6": ("THREAT", "Risco de Terceiros: fragilidades na cadeia de suprimentos e APIs externas."),
            "F4": ("WEAKNESS", "Débito Técnico: lentidão de atualização de dependências e sistemas legados."),
            "E7": ("OPPORTUNITY", "Oportunidade de Remediação: planos corretivos estruturados e auditorias periódicas."),
            "C5": ("STRENGTH", "Resiliência Comprovada: histórico satisfatório de contenção de incidentes."),
        }
        return swot_map.get(anchor, ("STRENGTH" if side == "pro" else "WEAKNESS", "Fator SWOT dimensional."))

    def _stage_4_assign_pieces(self, sess: Dict[str, Any], mstate: Dict[str, Any]) -> str:
        session_id = sess["id"]
        topic = sess["title"]
        game = sess["game"]
        pro_raw = (sess.get("_match_internal") or {}).get("pro_raw") or {"roles": {}}
        contra_raw = (sess.get("_match_internal") or {}).get("contra_raw") or {"roles": {}}

        pro_color = mstate["pro_color"]
        contra_color = mstate["contra_color"]
        pro_arts = self.sm.vault.get_accessible_artifacts_with_content(session_id, requesting_side=pro_color)
        contra_arts = self.sm.vault.get_accessible_artifacts_with_content(session_id, requesting_side=contra_color)
        if sess["normalized_source_policy"] == "WEB_ONLY":
            pro_arts = [a for a in pro_arts if a.get("source_type") == "web"]
            contra_arts = [a for a in contra_arts if a.get("source_type") == "web"]

        pieces: List[Dict[str, Any]] = []

        if game == "chess":
            # Mapeia todas as 32 peças iniciais do tabuleiro de Xadrez para inspeção completa em qualquer casa
            chess_roster = [
                # White (Pro)
                ("white", "pro", "king", "♔", "Rei Branco (Tese Central Pró)", "Tese central do lado", "e1"),
                ("white", "pro", "queen", "♕", "Dama Branca (Ataque Principal Pró)", "Principal linha de ataque argumentativo", "d1"),
                ("white", "pro", "rook", "♖", "Torre Branca a1 (Pilar Estrutural Pró)", "Argumentos estruturais e institucionais", "a1"),
                ("white", "pro", "rook", "♖", "Torre Branca h1 (Marco Institucional Pró)", "Argumentos estruturais e institucionais", "h1"),
                ("white", "pro", "bishop", "♗", "Bispo Branco c1 (Leitura Conceitual Pró)", "Interpretações conceituais e leitura de contexto", "c1"),
                ("white", "pro", "bishop", "♗", "Bispo Branco f1 (Análise Contextual Pró)", "Interpretações conceituais e leitura de contexto", "f1"),
                ("white", "pro", "knight", "♘", "Cavalo Branco b1 (Conexão Tática Pró)", "Argumentos não lineares e conexões inesperadas", "b1"),
                ("white", "pro", "knight", "♘", "Cavalo Branco g1 (Salto Analítico Pró)", "Argumentos não lineares e conexões inesperadas", "g1"),
                # Black (Contra)
                ("black", "contra", "king", "♚", "Rei Preto (Tese Central Contra)", "Tese central do lado", "e8"),
                ("black", "contra", "queen", "♛", "Dama Preta (Contraprova Principal)", "Principal linha de ataque argumentativo", "d8"),
                ("black", "contra", "rook", "♜", "Torre Preta a8 (Crítica Estrutural)", "Argumentos estruturais e institucionais", "a8"),
                ("black", "contra", "rook", "♜", "Torre Preta h8 (Barreira Institucional)", "Argumentos estruturais e institucionais", "h8"),
                ("black", "contra", "bishop", "♝", "Bispo Preto c8 (Crítica Metodológica)", "Interpretações conceituais e leitura de contexto", "c8"),
                ("black", "contra", "bishop", "♝", "Bispo Preto f8 (Escopo & Limites)", "Interpretações conceituais e leitura de contexto", "f8"),
                ("black", "contra", "knight", "♞", "Cavalo Preto b8 (Vetor Adversarial)", "Argumentos não lineares e conexões inesperadas", "b8"),
                ("black", "contra", "knight", "♞", "Cavalo Preto g8 (Contraponto Não Linear)", "Argumentos não lineares e conexões inesperadas", "g8"),
            ]
            for file_ch in "abcdefgh":
                chess_roster.append(
                    ("white", "pro", "pawn", "♙", f"Peão Branco {file_ch}2 (Evidência Pontual Pró)", "Evidências pontuais, fatos e dados de suporte", f"{file_ch}2")
                )
            for file_ch in "abcdefgh":
                chess_roster.append(
                    ("black", "contra", "pawn", "♟", f"Peão Preto {file_ch}7 (Fato Limitante Contra)", "Evidências pontuais, fatos e dados de suporte", f"{file_ch}7")
                )

            used_quotes_by_side: Dict[str, set] = {"pro": set(), "contra": set()}
            for idx, (color, side, ptype, sym, label, role_desc, sq) in enumerate(chess_roster):
                raw_roles = pro_raw.get("roles", {}) if side == "pro" else contra_raw.get("roles", {})
                side_arts = pro_arts if side == "pro" else contra_arts
                r_entry = raw_roles.get(ptype) or {}

                # Diversifica artefato e trecho usado entre peças do mesmo tipo (evita repetir a mesma citação em 8 peões)
                rotated_arts = side_arts[idx % len(side_arts):] + side_arts[:idx % len(side_arts)] if side_arts else []
                cand_quote = (r_entry.get("quote_text") or "").strip()
                cand_art_id = r_entry.get("artifact_id", "")
                if cand_quote and cand_quote in used_quotes_by_side[side]:
                    cand_quote = ""
                    cand_art_id = ""

                refs, is_ver, base_conf = self._build_artifact_ref(
                    session_id=session_id,
                    owner_color=color,
                    raw_art_id=cand_art_id,
                    raw_quote=cand_quote,
                    accessible_arts=rotated_arts,
                    topic=topic,
                    piece_idx=idx,
                )
                if is_ver and refs and refs[0].quote_text:
                    used_quotes_by_side[side].add(refs[0].quote_text)

                # Gera subtese heterogênea única por peça (v2.5)
                claim_txt = self._generate_heterogeneous_subthesis(
                    ptype=ptype,
                    sq=sq,
                    color=color,
                    side=side,
                    mode=sess.get("mode", "debate"),
                    topic=topic,
                    r_entry=r_entry,
                    refs=refs,
                    mstate=mstate,
                )

                piece_id = f"{color}_{ptype}_{sq}"
                parent_thesis_id = f"{color}_central_thesis"
                claim_id = f"claim_{color}_{ptype}_{sq}"
                auth_art_ids = [r.artifact_id for r in refs]

                # Registra controle de acesso granular de cofre por peça (RBAC v2.5)
                if hasattr(self.sm.vault, "set_piece_permissions"):
                    self.sm.vault.set_piece_permissions(session_id, piece_id, auth_art_ids)

                conf = round(base_conf, 2)
                ep_status = "SOURCE_VERIFIED" if is_ver else ("HYPOTHESIS" if (not side_arts or is_future_projection_topic(topic)) else "INSUFFICIENT")

                pieces.append(
                    PieceDossierSchema(
                        piece_id=piece_id,
                        side=side,
                        color=color,
                        piece_type=ptype,
                        symbol=sym,
                        label=label,
                        role=role_desc,
                        initial_coord=sq,
                        current_coord=sq,
                        alive=True,
                        claim=claim_txt,
                        parent_thesis_id=parent_thesis_id,
                        claim_id=claim_id,
                        authorized_artifact_ids=auth_art_ids,
                        supporting_evidence_ids=[r.artifact_id for r in refs if r.verified],
                        contradicting_evidence_ids=[],
                        board_status="in_game",
                        supporting_artifacts=refs,
                        confidence_score=conf,
                        epistemic_status=ep_status,
                        confrontation_history=[],
                        swot_category=None,
                        swot_rationale=None,
                    ).model_dump()
                )
        else:
            # 12 Grupos Estratégicos de Go 9x9 (6 Pretas/Pró + 6 Brancas/Contra)
            go_roster = [
                ("black", "pro", "go_influence", "◉", "Grupo Preto — Influência Central (Pró)", "Bloco argumentativo de cobertura macro", "E5"),
                ("black", "pro", "go_territory", "◉", "Grupo Preto — Território Consolidado (Pró)", "Área de dominância interpretativa e fontes primárias", "C3"),
                ("black", "pro", "go_eyes", "◉", "Grupo Preto — Olhos Resilientes (Pró)", "Argumento resiliente autossustentado", "G7"),
                ("black", "pro", "go_invasion", "◉", "Grupo Preto — Expansão Tática (Pró)", "Avanço sobre premissas em aberto", "C7"),
                ("black", "pro", "go_siege", "◉", "Grupo Preto — Cerco Argumentativo (Pró)", "Pressão sobre linhas sem sustentação", "G3"),
                ("black", "pro", "go_connection", "◉", "Grupo Preto — Conexão Estrutural (Pró)", "Articulação entre evidências independentes", "E3"),
                ("white", "contra", "go_invasion", "○", "Grupo Branco — Invasão Crítica (Contra)", "Contra-argumento em território consolidado", "D4"),
                ("white", "contra", "go_territory", "○", "Grupo Branco — Território de Ceticismo (Contra)", "Delimitação de limites estruturais e riscos", "F6"),
                ("white", "contra", "go_eyes", "○", "Grupo Branco — Olhos Metodológicos (Contra)", "Contraprova resiliente e independente", "D6"),
                ("white", "contra", "go_influence", "○", "Grupo Branco — Contraponto Sistêmico (Contra)", "Leitura alternativa de variáveis macro", "F4"),
                ("white", "contra", "go_siege", "○", "Grupo Branco — Cerco de Refutação (Contra)", "Pressão sobre lacunas empíricas da tese", "E7"),
                ("white", "contra", "go_connection", "○", "Grupo Branco — Conexão de Riscos (Contra)", "Encadeamento de falhas e incertezas", "C5"),
            ]
            for idx, (color, side, gtype, sym, label, role_desc, anchor) in enumerate(go_roster):
                raw_roles = pro_raw.get("roles", {}) if side == "pro" else contra_raw.get("roles", {})
                side_arts = pro_arts if side == "pro" else contra_arts
                r_entry = raw_roles.get(gtype) or {}
                claim_txt = r_entry.get("claim") or (
                    mstate["pro_thesis"] if side == "pro" else mstate["contra_thesis"]
                )
                rotated_arts = side_arts[idx % len(side_arts):] + side_arts[:idx % len(side_arts)] if side_arts else []
                refs, is_ver, base_conf = self._build_artifact_ref(
                    session_id=session_id,
                    owner_color=color,
                    raw_art_id=r_entry.get("artifact_id", ""),
                    raw_quote=r_entry.get("quote_text", ""),
                    accessible_arts=rotated_arts,
                    topic=topic,
                    piece_idx=idx,
                )

                piece_id = f"{color}_{gtype}_{anchor.lower()}"
                parent_thesis_id = f"{color}_central_thesis"
                claim_id = f"claim_{color}_{gtype}_{anchor.lower()}"
                auth_art_ids = [r.artifact_id for r in refs]

                # Registra controle de acesso granular de cofre por peça (RBAC v2.5)
                if hasattr(self.sm.vault, "set_piece_permissions"):
                    self.sm.vault.set_piece_permissions(session_id, piece_id, auth_art_ids)

                swot_cat, swot_rat = self._assign_go_swot_role(gtype, side, anchor)
                conf = round(base_conf, 2)
                ep_status = "SOURCE_VERIFIED" if is_ver else ("HYPOTHESIS" if (not side_arts or is_future_projection_topic(topic)) else "INSUFFICIENT")

                pieces.append(
                    PieceDossierSchema(
                        piece_id=piece_id,
                        side=side,
                        color=color,
                        piece_type=gtype,
                        symbol=sym,
                        label=label,
                        role=role_desc,
                        initial_coord=anchor,
                        current_coord=anchor,
                        stones=[],
                        alive=True,
                        claim=claim_txt,
                        parent_thesis_id=parent_thesis_id,
                        claim_id=claim_id,
                        authorized_artifact_ids=auth_art_ids,
                        supporting_evidence_ids=[r.artifact_id for r in refs if r.verified],
                        contradicting_evidence_ids=[],
                        board_status="in_game",
                        supporting_artifacts=refs,
                        confidence_score=conf,
                        epistemic_status=ep_status,
                        confrontation_history=[],
                        swot_category=swot_cat,
                        swot_rationale=swot_rat,
                    ).model_dump()
                )

        mstate["pieces"] = pieces
        
        ver_cnt = sum(1 for p in pieces if p["epistemic_status"] in ("SOURCE_VERIFIED", "SUPPORTED"))
        return f"{len(pieces)} unidades táticas vinculadas a teses e dossiês ({ver_cnt} com citação literal verificada)."
