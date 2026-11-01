"""
Semantic Clash Engine — Gambit Lab v2.5
Motor de arbitragem semântica de confrontos entre peças no Xadrez Epistêmico.
Avalia a colisão entre subteses e evidências autorizadas sem pontuação arbitrária de material.
(Etapa D, RN-X01..RN-X06)
"""
import hashlib
import json
import re
from typing import Any, Dict, List, Optional, Tuple

import chess

from services.api.models.schemas import ClashVerdict


class SemanticClashEngine:
    def __init__(self, session_manager=None):
        self.sm = session_manager
        # session_id -> { cache_key: ClashEvaluationResult }
        self._cache: Dict[str, Dict[str, Dict[str, Any]]] = {}

    def _compute_cache_key(
        self,
        attacker: Dict[str, Any],
        defender: Dict[str, Any],
        from_coord: str,
        to_coord: str,
    ) -> str:
        att_claim = attacker.get("claim", "")
        att_refs = ",".join(
            sorted(f"{r.get('artifact_id')}:{r.get('quote_text')}" for r in attacker.get("supporting_artifacts", []))
        )
        def_claim = defender.get("claim", "")
        def_refs = ",".join(
            sorted(f"{r.get('artifact_id')}:{r.get('quote_text')}" for r in defender.get("supporting_artifacts", []))
        )
        raw = f"{attacker.get('piece_id')}:{from_coord}|{att_claim}|{att_refs}=>{defender.get('piece_id')}:{to_coord}|{def_claim}|{def_refs}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    _compute_confrontation_hash = _compute_cache_key

    def _check_relevance(self, claim_a: str, claim_b: str, quote: str, title: str) -> bool:
        """Verifica se a evidência apresentada guarda pertinência temática real com o confronto."""
        if not quote and not title:
            return False
        combined_claim = f"{claim_a} {claim_b}".lower()
        stop_words = {
            "de", "a", "o", "que", "e", "do", "da", "em", "um", "para", "é", "com", "não",
            "uma", "os", "no", "se", "na", "por", "mais", "as", "dos", "como", "mas", "foi",
            "ao", "ele", "das", "tem", "à", "seu", "sua", "ou", "ser", "quando", "muito", "há",
            "nos", "já", "está", "eu", "também", "só", "pelo", "pela", "até", "isso", "ela",
            "entre", "era", "depois", "sem", "mesmo", "aos", "ter", "seus", "quem", "nas", "me",
            "esse", "eles", "estão", "você", "tinha", "foram", "essa", "num", "nem", "suas",
            "meu", "às", "minha", "têm", "numa", "pelos", "elas", "havia", "seja", "qual",
            "será", "seria", "sobre", "referente", "hipótese", "aberta", "aguardando",
            "fundamentação", "documental", "investigar"
        }
        words = [re.sub(r'[^\w]', '', w) for w in combined_claim.split() if len(w) >= 3]
        substantive = [w for w in words if w and w not in stop_words]
        evidence_text = f"{title} {quote}".lower()
        if not substantive:
            return True
        matches = sum(1 for w in substantive if w in evidence_text)
        return matches >= 1

    def evaluate_confrontation(
        self,
        session_id: str,
        attacker: Dict[str, Any],
        defender: Dict[str, Any],
        from_coord: str,
        to_coord: str,
        board_fen: str = "",
        all_pieces: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Avalia o confronto semântico entre a peça atacante e a peça defensora (v2.5.1).
        Regras fundamentais:
        1. SOURCE_VERIFIED != CLAIM_SUPPORTED.
        2. Duas hipóteses não comprovadas resultam em CONFRONTATION_INCONCLUSIVE.
        3. Citação verdadeira fora de contexto eleitoral/investigado não autoriza captura.
        4. O Rei só pode ser capturado após todas as outras peças serem eliminadas (RN-X04).
        """
        cache_key = self._compute_cache_key(attacker, defender, from_coord, to_coord)
        sess_cache = self._cache.setdefault(session_id, {})
        if cache_key in sess_cache:
            res = dict(sess_cache[cache_key])
            res["cached"] = True
            return res

        # Etapa 1: Validação de Movimento Físico (se FEN e tabuleiro fornecidos)
        if board_fen and from_coord and to_coord:
            try:
                board = chess.Board(board_fen)
                from_sq = chess.parse_square(from_coord.lower())
                to_sq = chess.parse_square(to_coord.lower())
                test_move = chess.Move(from_sq, to_sq)
                # Verifica legalidade física do movimento na posição atual
                if test_move not in board.legal_moves:
                    # Pode ser promoção? Tenta dama
                    test_promo = chess.Move(from_sq, to_sq, promotion=chess.QUEEN)
                    if test_promo not in board.legal_moves:
                        illegal_res = {
                            "confrontation_id": f"clash_{cache_key[:12]}",
                            "session_id": session_id,
                            "attacker_piece_id": attacker.get("piece_id", "unknown"),
                            "defender_piece_id": defender.get("piece_id", "unknown"),
                            "attacker_claim": attacker.get("claim", ""),
                            "defender_claim": defender.get("claim", ""),
                            "attacker_artifacts": attacker.get("supporting_artifacts", []),
                            "defender_artifacts": defender.get("supporting_artifacts", []),
                            "verdict": "MOVE_ILLEGAL",
                            "justification": f"Movimento {from_coord} → {to_coord} é geometricamente inválido pelas regras físicas da posição.",
                            "is_king_protected": False,
                            "cached": False,
                        }
                        sess_cache[cache_key] = illegal_res
                        return illegal_res
            except Exception:
                pass

        # Etapa 2 & 3: Invariante de Proteção do Rei (RN-X04)
        def_type = (defender.get("piece_type") or ("king" if "king" in defender.get("piece_id", "").lower() else "")).lower()
        def_color = defender.get("color", "")
        if (def_type == "king" or "king" in defender.get("piece_id", "").lower()) and all_pieces:
            # Verifica se existem outras peças vivas do mesmo lado defendendo o Rei
            active_guards = [
                p for p in all_pieces
                if p.get("color") == def_color
                and not ("king" in p.get("piece_id", "").lower() or p.get("piece_type") == "king")
                and p.get("alive", True)
                and p.get("piece_id") != defender.get("piece_id")
            ]
            if len(active_guards) > 0:
                guard_count = len(active_guards)
                justification = (
                    f"Proteção Invariante do Rei: o Rei ({def_color}) é a tese central e está blindado por "
                    f"{guard_count} subtese(s) defensiva(s) ativa(s) no tabuleiro. O confronto final só é "
                    "permitido após a superação de todas as peças de suporte."
                )
                result = {
                    "confrontation_id": f"clash_{cache_key[:12]}",
                    "session_id": session_id,
                    "attacker_piece_id": attacker.get("piece_id", "unknown"),
                    "defender_piece_id": defender.get("piece_id", "unknown"),
                    "attacker_claim": attacker.get("claim", ""),
                    "defender_claim": defender.get("claim", ""),
                    "attacker_artifacts": attacker.get("supporting_artifacts", []),
                    "defender_artifacts": defender.get("supporting_artifacts", []),
                    "verdict": "DEFENSE_SUCCESSFUL",
                    "justification": justification,
                    "is_king_protected": True,
                    "cached": False,
                }
                sess_cache[cache_key] = result
                return result

        # Arbitragem semântica rigorosa entre as evidências
        att_refs = attacker.get("supporting_artifacts", [])
        def_refs = defender.get("supporting_artifacts", [])
        att_ver = any(r.get("verified") is True or bool(r.get("quote_text")) for r in att_refs)
        def_ver = any(r.get("verified") is True or bool(r.get("quote_text")) for r in def_refs)
        att_conf = attacker.get("confidence_score", 0.5)
        def_conf = defender.get("confidence_score", 0.5)
        att_status = attacker.get("epistemic_status", "HYPOTHESIS")
        def_status = defender.get("epistemic_status", "HYPOTHESIS")

        # Critérios Epistêmicos Formais Rigorosos (v2.5.1):
        # 1. Se NENHUM tem fonte verificada (ambas são hipóteses abertas sem suporte probatório):
        #    -> Confronto inconclusivo; duas alegações sem prova documental não produzem vitória/refutação.
        # 2. Se atacante tem citação verificada e defensora NÃO TEM:
        #    -> Valida se a evidência é relevante e não apenas uma citação desconexa. Se irrelevante -> INCONCLUSIVE.
        # 3. Se defensora tem citação verificada e atacante NÃO TEM:
        #    -> Defesa bem-sucedida (hipótese atacante não derruba fato documental verificado).
        # 4. Se AMBOS têm fontes verificadas:
        #    -> Compara pertinência e solidez probatória comparada.

        if not att_ver and not def_ver:
            verdict: ClashVerdict = "CONFRONTATION_INCONCLUSIVE"
            justification = (
                f"Confronto inconclusivo: ambas as alegações mantêm status {att_status}/{def_status} "
                "sem citações documentais verificadas no cofre para sustentar refutação. Duas hipóteses "
                "sem suporte documental não autorizam a captura de uma peça."
            )
        elif att_ver and not def_ver:
            att_title = att_refs[0].get("title", "Fonte primária") if att_refs else "Fonte primária"
            att_quote = att_refs[0].get("quote_text", "") if att_refs else ""
            is_rel = self._check_relevance(attacker.get("claim", ""), defender.get("claim", ""), att_quote, att_title)
            if not is_rel:
                verdict = "CONFRONTATION_INCONCLUSIVE"
                justification = (
                    f"Confronto inconclusivo: a evidência apresentada por {attacker.get('label')} "
                    f"('{att_title}') não possui relevância temática demonstrada para refutar a "
                    f"alegação de {defender.get('label')}. Citação verdadeira em contexto não correlato não autoriza refutação."
                )
            else:
                verdict = "CAPTURE_AUTHORIZED"
                justification = (
                    f"Refutação demonstrada: {attacker.get('label', 'Peça atacante')} apresentou evidência documental "
                    f"pertinente e verificada em '{att_title}' ({att_conf:.2f}), superando a hipótese "
                    f"não comprovada de {defender.get('label', 'Peça defensora')}."
                )
        elif def_ver and not att_ver:
            verdict = "DEFENSE_SUCCESSFUL"
            def_title = def_refs[0].get("title", "Documento oficial") if def_refs else "Documento oficial"
            justification = (
                f"Defesa sustentada: a subtese de {defender.get('label', 'Peça defensora')} está respaldada por citação "
                f"literal verificada em '{def_title}' ({def_conf:.2f}). A contestação de {attacker.get('label')} não "
                "apresentou evidência documental correspondente para refutá-la."
            )
        else:
            # Ambos têm fontes verificadas
            att_title = att_refs[0].get("title", "") if att_refs else ""
            att_quote = att_refs[0].get("quote_text", "") if att_refs else ""
            def_title = def_refs[0].get("title", "") if def_refs else ""
            def_quote = def_refs[0].get("quote_text", "") if def_refs else ""
            is_att_rel = self._check_relevance(attacker.get("claim", ""), defender.get("claim", ""), att_quote, att_title)
            is_def_rel = self._check_relevance(defender.get("claim", ""), attacker.get("claim", ""), def_quote, def_title)

            if is_att_rel and not is_def_rel:
                verdict = "CAPTURE_AUTHORIZED"
                justification = (
                    f"Refutação por pertinência: {attacker.get('label')} apresentou evidência diretamente correlata "
                    f"({att_conf:.2f}), enquanto a referência de {defender.get('label')} mostrou-se descontextualizada."
                )
            elif is_def_rel and not is_att_rel:
                verdict = "DEFENSE_SUCCESSFUL"
                justification = (
                    f"Defesa sustentada: {defender.get('label')} apresentou evidência diretamente pertinente ao confronto "
                    f"({def_conf:.2f}), resistindo à citação descontextualizada de {attacker.get('label')}."
                )
            elif att_conf >= def_conf + 0.15:
                verdict = "CAPTURE_AUTHORIZED"
                justification = (
                    f"Refutação demonstrada: ambas possuem fontes verificadas, mas a fundamentação contextual de "
                    f"{attacker.get('label')} ({att_conf:.2f}) supera a sustentação de {defender.get('label')} ({def_conf:.2f})."
                )
            elif def_conf >= att_conf + 0.05:
                verdict = "DEFENSE_SUCCESSFUL"
                justification = (
                    f"Defesa resistente: {defender.get('label')} possui solidez probatória comprovada ({def_conf:.2f}) "
                    f"suficiente para mitigar o contraditório apresentado por {attacker.get('label')} ({att_conf:.2f})."
                )
            else:
                verdict = "CONFRONTATION_INCONCLUSIVE"
                justification = (
                    f"Confronto inconclusivo: ambas as alegações possuem evidências verificadas de peso equivalente "
                    f"({att_conf:.2f} vs {def_conf:.2f}). As perspectivas coexistem sem refutação categórica."
                )

        result = {
            "confrontation_id": f"clash_{cache_key[:12]}",
            "session_id": session_id,
            "attacker_piece_id": attacker.get("piece_id", "unknown"),
            "defender_piece_id": defender.get("piece_id", "unknown"),
            "attacker_claim": attacker.get("claim", ""),
            "defender_claim": defender.get("claim", ""),
            "attacker_artifacts": attacker.get("supporting_artifacts", []),
            "defender_artifacts": defender.get("supporting_artifacts", []),
            "verdict": verdict,
            "justification": justification,
            "is_king_protected": False,
            "cached": False,
        }
        sess_cache[cache_key] = result
        return result

    def get_piece_reachability(
        self,
        session_id: str,
        piece_id: str,
        board_fen: str,
        pieces: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Calcula imediata e deterministicamente o alcance físico da peça na posição FEN
        e classifica cada alvo adversário alcançável quanto ao seu status de confronto.
        """
        pieces_by_id = {p["piece_id"]: p for p in pieces}
        piece = pieces_by_id.get(piece_id)
        if not piece:
            raise KeyError(f"Peça {piece_id} não encontrada na sessão.")

        board = chess.Board(board_fen)
        coord = (piece.get("current_coord") or piece.get("initial_coord") or "").lower()
        if not coord or len(coord) != 2:
            return {
                "piece_id": piece_id,
                "coord": coord,
                "label": piece.get("label", ""),
                "role": piece.get("role", ""),
                "claim": piece.get("claim", ""),
                "side": piece.get("side", ""),
                "color": piece.get("color", ""),
                "epistemic_status": piece.get("epistemic_status", "HYPOTHESIS"),
                "authorized_artifact_ids": piece.get("authorized_artifact_ids", []),
                "authorized_artifacts": piece.get("supporting_artifacts", []),
                "free_moves": [],
                "reachable_opponents": [],
            }

        sq = chess.parse_square(coord)
        piece_color = chess.WHITE if piece.get("color") == "white" else chess.BLACK

        # Mapeia casa atual de cada peça viva
        sq_to_piece: Dict[int, Dict[str, Any]] = {}
        for p in pieces:
            if not p.get("alive", True):
                continue
            p_coord = p.get("current_coord") or p.get("initial_coord")
            if p_coord and len(p_coord) == 2:
                try:
                    sq_to_piece[chess.parse_square(p_coord.lower())] = p
                except Exception:
                    pass

        # Cria tabuleiro temporário com a vez de quem joga ajustada para a cor da peça
        eval_board = board.copy()
        eval_board.turn = piece_color

        free_moves: List[str] = []
        reachable_opponents: List[Dict[str, Any]] = []

        for move in eval_board.legal_moves:
            if move.from_square == sq:
                dest_name = chess.square_name(move.to_square)
                is_cap = eval_board.is_capture(move)
                if not is_cap:
                    free_moves.append(dest_name)
                else:
                    target_sq = move.to_square
                    if eval_board.is_en_passant(move):
                        target_sq = chess.square(chess.square_file(move.to_square), chess.square_rank(move.from_square))
                    target_piece = sq_to_piece.get(target_sq)
                    if target_piece and target_piece.get("color") != piece.get("color"):
                        clash_res = self.evaluate_confrontation(
                            session_id=session_id,
                            attacker=piece,
                            defender=target_piece,
                            from_coord=coord,
                            to_coord=dest_name,
                            board_fen=board_fen,
                            all_pieces=pieces,
                        )
                        reachable_opponents.append({
                            "coord": dest_name,
                            "piece_id": target_piece.get("piece_id"),
                            "label": target_piece.get("label", ""),
                            "role": target_piece.get("role", ""),
                            "claim": target_piece.get("claim", ""),
                            "clash_status": clash_res["verdict"],
                            "clash_reason": clash_res["justification"],
                            "attacker_evidence_count": len(piece.get("supporting_artifacts", [])),
                            "defender_evidence_count": len(target_piece.get("supporting_artifacts", [])),
                            "is_king_protected": clash_res.get("is_king_protected", False),
                            "evaluated": True,
                        })

        return {
            "piece_id": piece_id,
            "coord": coord,
            "label": piece.get("label", ""),
            "role": piece.get("role", ""),
            "claim": piece.get("claim", ""),
            "side": piece.get("side", ""),
            "color": piece.get("color", ""),
            "epistemic_status": piece.get("epistemic_status", "HYPOTHESIS"),
            "authorized_artifact_ids": piece.get("authorized_artifact_ids", []),
            "authorized_artifacts": piece.get("supporting_artifacts", []),
            "free_moves": sorted(free_moves),
            "reachable_opponents": reachable_opponents,
        }
