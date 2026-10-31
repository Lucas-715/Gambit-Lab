"""
Semantic Clash Engine — Gambit Lab v2.5
Motor de arbitragem semântica de confrontos entre peças no Xadrez Epistêmico.
Avalia a colisão entre subteses e evidências autorizadas sem pontuação arbitrária de material.
(Etapa D, RN-X01..RN-X06)
"""
import hashlib
import json
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

    def evaluate_confrontation(
        self,
        session_id: str,
        attacker: Dict[str, Any],
        defender: Dict[str, Any],
        from_coord: str,
        to_coord: str,
        board_fen: Optional[str] = None,
        all_pieces: Optional[List[Dict[str, Any]]] = None,
        force_fresh: bool = False,
    ) -> Dict[str, Any]:
        """
        Executa a sequência de 4 etapas de arbitragem semântica:
        1. Validação física/geométrica (se board_fen fornecido).
        2. Identificação das alegações e fontes autorizadas.
        3. Arbitragem semântica com verificação do Invariante do Rei.
        4. Emissão do veredito explícito e gravação em cache.
        """
        # Checa cache
        cache_key = self._compute_cache_key(attacker, defender, from_coord, to_coord)
        sess_cache = self._cache.setdefault(session_id, {})
        if not force_fresh and cache_key in sess_cache:
            res = dict(sess_cache[cache_key])
            res["cached"] = True
            return res

        # Etapa 1: Validação física se FEN fornecido
        if board_fen:
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

        # Critérios Epistêmicos Formais:
        # 1. Se atacante tem citação literal verificada (SOURCE_VERIFIED/SUPPORTED) e defensora NÃO TEM
        #    -> Refutação autorizada (evidência pontual supera mera hipótese).
        # 2. Se defensora tem citação literal verificada e atacante NÃO TEM
        #    -> Defesa bem-sucedida (hipótese atacante não derruba fato documental verificado).
        # 3. Se AMBOS têm fontes verificadas:
        #    -> Compara solidez, consistência interna e amplitude da tese.
        # 4. Se NENHUM tem fontes verificadas:
        #    -> Confronto inconclusivo (não há substância empírica para decretar refutação).

        if att_ver and not def_ver:
            verdict: ClashVerdict = "CAPTURE_AUTHORIZED"
            att_title = att_refs[0].get("title", "Fonte primária") if att_refs else "Fonte primária"
            justification = (
                f"Refutação fundamentada: {attacker.get('label', 'Peça atacante')} apresentou evidência com "
                f"citação literal verificada em '{att_title}' ({att_conf:.2f}), superando a alegação "
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
        elif att_ver and def_ver:
            # Ambos têm fontes verificadas: avalia diferencial de fundamentação
            if att_conf >= def_conf + 0.15:
                verdict = "CAPTURE_AUTHORIZED"
                justification = (
                    f"Refutação demonstrada: ambas possuem fontes verificadas, mas a fundamentação contextual de "
                    f"{attacker.get('label')} ({att_conf:.2f}) supera a sustentação de {defender.get('label')} ({def_conf:.2f})."
                )
            elif def_conf >= att_conf + 0.10:
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
        else:
            # Nenhum tem fonte verificada
            verdict = "CONFRONTATION_INCONCLUSIVE"
            justification = (
                f"Confronto preliminar sem comprovação documental: ambas as alegações mantêm status {att_status}/{def_status} "
                "sem citações literais verificadas no cofre para sustentar refutação factual definitiva."
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
