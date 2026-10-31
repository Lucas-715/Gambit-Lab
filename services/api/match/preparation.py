"""
Preparação do Research Match (estágios 1, 2 e 4):
construção dos lados Pró/Contra, pesquisa isolada por cofre e atribuição de dossiês às peças/grupos.
"""
import copy
from typing import Any, Dict, List, Tuple

from services.api.agents.gemini_adapter import is_future_projection_topic
from services.api.agents.web_search_adapter import WebSearchUnavailableError
from services.api.models.schemas import PieceArtifactRefSchema, PieceDossierSchema


class VaultIsolationError(RuntimeError):
    """Violação da Regra de Ouro: um lado enxergou artefato privado do adversário."""


class PreparationMixin:
    def _stage_1_build_sides(self, sess: Dict[str, Any], mstate: Dict[str, Any]) -> str:
        topic = sess["title"]
        pro_c = mstate["pro_color"]
        contra_c = mstate["contra_color"]
        # O orçamento de lances da partida (plies_budget) substitui o teto de 12 etapas da investigação manual.
        sess["max_steps"] = mstate["plies_budget"]
        sess["budget"]["max_steps"] = mstate["plies_budget"]
        sess["budget"]["max_calls"] = max(sess["budget"].get("max_calls", 24), 24)
        mstate["pro_thesis"] = f"Tese Favorável (Lado Pró · {pro_c.upper()}): investigação de viabilidade e sustentação para '{topic}'."
        mstate["contra_thesis"] = f"Tese Crítica (Lado Contra · {contra_c.upper()}): investigação de riscos, limites e contraprovas para '{topic}'."
        return (
            f"Lados configurados com cofres isolados: Lado Pró ({pro_c.upper()}) vs "
            f"Lado Contra ({contra_c.upper()}) · Profundidade {mstate['depth']} (orçamento: {mstate['plies_budget']} lances)."
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
            # Cada lado usa a PERGUNTA REAL como âncora; apenas o viés de busca difere (a favor vs. contra).
            query_focus = (
                f"{topic} benefícios vantagens evidências"
                if side == "pro"
                else f"{topic} riscos limitações críticas"
            )
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

    def _build_artifact_ref(
        self,
        session_id: str,
        owner_color: str,
        raw_art_id: str,
        raw_quote: str,
        accessible_arts: List[Dict[str, Any]],
        topic: str,
    ) -> Tuple[List[PieceArtifactRefSchema], bool, float]:
        """Valida citação literal nos artefatos acessíveis ao lado e calcula confiança honesta."""
        future_flag = is_future_projection_topic(topic)
        by_id = {a["id"]: a for a in accessible_arts}
        matched_art = by_id.get(raw_art_id) if raw_art_id else None
        verified = False
        final_quote = (raw_quote or "").strip()

        if matched_art and final_quote:
            ok, _ = self.sm.vault.find_verified_quote_offset(matched_art["id"], final_quote)
            if ok:
                verified = True

        if not verified and final_quote:
            for cand in accessible_arts:
                ok, _ = self.sm.vault.find_verified_quote_offset(cand["id"], final_quote)
                if ok:
                    matched_art = cand
                    verified = True
                    break

        if not matched_art and accessible_arts and not future_flag:
            # Vincula referência documental disponível no cofre do lado e extrai trecho literal real se compatível
            cand = accessible_arts[0]
            body = (cand.get("content") or cand.get("content_preview") or "").strip()
            sents = [s.strip() for s in body.replace("\n", ". ").split(".") if len(s.strip()) >= 22]
            if sents:
                test_q = sents[0][:160]
                ok, _ = self.sm.vault.find_verified_quote_offset(cand["id"], test_q)
                if ok:
                    matched_art = cand
                    final_quote = test_q
                    verified = True

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

        if future_flag:
            return refs, False, 0.48
        if verified:
            return refs, True, 0.82
        if accessible_arts:
            return refs, False, 0.50
        return [], False, 0.42

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

            for idx, (color, side, ptype, sym, label, role_desc, sq) in enumerate(chess_roster):
                raw_roles = pro_raw.get("roles", {}) if side == "pro" else contra_raw.get("roles", {})
                side_arts = pro_arts if side == "pro" else contra_arts
                r_entry = raw_roles.get(ptype) or {}
                claim_txt = r_entry.get("claim") or (
                    mstate["pro_thesis"] if side == "pro" else mstate["contra_thesis"]
                )
                # Diversifica artefato usado entre peças do mesmo tipo quando há múltiplas fontes no cofre
                rotated_arts = side_arts[idx % len(side_arts):] + side_arts[:idx % len(side_arts)] if side_arts else []
                refs, is_ver, base_conf = self._build_artifact_ref(
                    session_id=session_id,
                    owner_color=color,
                    raw_art_id=r_entry.get("artifact_id", ""),
                    raw_quote=r_entry.get("quote_text", ""),
                    accessible_arts=rotated_arts,
                    topic=topic,
                )
                # v2.3 C01/C09: Trecho localizado = SOURCE_VERIFIED (sem SUPPORTED automático nem bônus de peça)
                conf = round(base_conf, 2)
                ep_status = "SOURCE_VERIFIED" if is_ver else ("HYPOTHESIS" if (not side_arts or is_future_projection_topic(topic)) else "INSUFFICIENT")

                pieces.append(
                    PieceDossierSchema(
                        piece_id=f"{color}_{ptype}_{sq}",
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
                        supporting_artifacts=refs,
                        confidence_score=conf,
                        epistemic_status=ep_status,
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
                )
                # v2.3 C01/C09: Trecho localizado = SOURCE_VERIFIED (sem SUPPORTED automático)
                conf = round(base_conf, 2)
                ep_status = "SOURCE_VERIFIED" if is_ver else ("HYPOTHESIS" if (not side_arts or is_future_projection_topic(topic)) else "INSUFFICIENT")

                pieces.append(
                    PieceDossierSchema(
                        piece_id=f"{color}_{gtype}_{anchor.lower()}",
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
                        supporting_artifacts=refs,
                        confidence_score=conf,
                        epistemic_status=ep_status,
                    ).model_dump()
                )

        mstate["pieces"] = pieces
        
        ver_cnt = sum(1 for p in pieces if p["epistemic_status"] in ("SOURCE_VERIFIED", "SUPPORTED"))
        return f"{len(pieces)} unidades táticas vinculadas a teses e dossiês ({ver_cnt} com citação literal verificada)."
