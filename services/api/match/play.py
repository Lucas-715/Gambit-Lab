"""
Estágio 5 do Research Match — geração da partida COMPLETA nos motores determinísticos.

Regras de encerramento (nunca um número fixo de lances):
  Xadrez: xeque-mate; empate por regra (afogamento, material insuficiente, repetição, 50/75 lances);
          resignação formal (déficit material decisivo e sustentado).
  Go:     dois passes consecutivos → pontuação por área com komi; ou resignação não é usada.
  Orçamento: se `plies_budget` esgota antes do fim formal, o estado fica BUDGET_EXHAUSTED
             (retomável) e NENHUM vencedor é inventado.
O estágio é retomável: o estado de jogo vive em `sess["_match_internal"]["play"]` e nos motores da sessão.
"""
import copy
import hashlib
from typing import Any, Dict, List, Optional

import chess

from packages.game_rules.chess_engine import EpistemicChessEngine
from packages.game_rules.go_engine import GoEngine9x9
from services.api.match.chess_player import ChessPlayer, material_cp, material_diff_white_cp
from services.api.match.go_player import GoPlayer
import datetime
from services.api.models.schemas import (
    BoardPositionSchema,
    MoveAuditPayloadSchema,
    MatchPlyRecordSchema,
    PieceHistoryEntrySchema,
)

RESIGN_DEFICIT_CP = 800        # ≈ uma Dama de desvantagem
RESIGN_STREAK = 3              # turnos consecutivos do próprio lado nessa condição
RESIGN_MIN_PLY = 24



class PlayMixin:
    DEFAULT_AUTO_RESIGN: bool = False
    enable_auto_resignation: bool = False
    epistemic_gating_enabled: bool = False

    def _build_control_audit(
        self,
        sess: Dict[str, Any],
        ply_idx: int,
        acting_color: str,
        att: Optional[Dict[str, Any]],
        cap: Optional[Dict[str, Any]],
        quote_txt: Optional[str],
        is_cap: bool,
    ) -> Dict[str, Any]:
        # A board move is not a control test. Criteria must come from the
        # investigation scope; never infer compliance from a quote or capture.
        claim = (att or {}).get("claim") or sess["title"]
        verified = any(
            ref.get("verified") and ref.get("quote_text") == quote_txt
            for ref in (att or {}).get("supporting_artifacts", [])
        ) if quote_txt else False
        return {
            "control_id": (att or {}).get("piece_id", "scope"),
            "name": claim,
            "requirement": sess["title"],
            "expected_criteria": "Critério de aceitação documental ainda não validado para esta alegação.",
            "finding": (
                "Trecho localizado na fonte; pertinência e suficiência para o controle requerem avaliação."
                if verified else "Evidência documental verificada insuficiente para avaliar este controle."
            ),
            "risk_level": "NÃO AVALIADO",
            "compliance_status": "INCONCLUSIVE",
            "recommendation": "Definir escopo e critério de aceitação; verificar evidências de implementação e exceções.",
            "evidence_quote": quote_txt or "",
        }
    # ------------------------------------------------------------------ schemas de tabuleiro
    @staticmethod
    def _chess_board_schema(engine: EpistemicChessEngine) -> BoardPositionSchema:
        d = engine.to_dict()
        return BoardPositionSchema(
            game="chess",
            fen=d["fen"],
            to_move=d["turn"],
            turn=d["fullmove"],
            ply_count=d["ply_count"],
            last_move=d.get("last_move"),
            is_game_over=d["is_game_over"],
            game_result=d.get("game_result"),
            is_check=d.get("is_check", False),
            diagnostic_reason=d.get("diagnostic_reason"),
        )

    @staticmethod
    def _go_board_schema(engine: GoEngine9x9) -> BoardPositionSchema:
        d = engine.to_dict()
        return BoardPositionSchema(
            game="go",
            stones=d["stones"],
            to_move=d["turn"],
            turn=(d["ply_count"] // 2) + 1,
            ply_count=d["ply_count"],
            last_move=d.get("last_move"),
            captured_white=d.get("captured_by_black", 0),
            captured_black=d.get("captured_by_white", 0),
            komi=d.get("komi", 6.5),
            is_game_over=d["is_game_over"],
            game_result=d.get("game_result"),
        )

    # ------------------------------------------------------------------ estado de jogo retomável
    def _get_play_state(self, sess: Dict[str, Any], mstate: Dict[str, Any]) -> Dict[str, Any]:
        internal = sess["_match_internal"]
        if internal.get("play"):
            return internal["play"]
        seed = hashlib.sha256(sess["id"].encode("utf-8")).hexdigest()[:16]
        play: Dict[str, Any] = {
            "seed": seed,
            "finished": False,
            "termination": None,
            "winner_color": None,
            "resigned_color": None,
            "resign_streak": {"white": 0, "black": 0},
            "recent_uci": [],
            "sq_to_pid": {},
            "coord_to_gid": {},
            "highlights": [],
            "prev_momentum": 0.5,
        }
        if sess["game"] == "chess":
            self.sm.chess_engines[sess["id"]] = EpistemicChessEngine()
            play["sq_to_pid"] = {
                p["initial_coord"]: p["piece_id"] for p in mstate["pieces"] if p.get("initial_coord")
            }
        else:
            self.sm.go_engines[sess["id"]] = GoEngine9x9()
        internal["play"] = play
        return play

    # ------------------------------------------------------------------ estágio 5
    def _stage_5_generate_match(self, sess: Dict[str, Any], mstate: Dict[str, Any]) -> str:
        play = self._get_play_state(sess, mstate)
        start_plies = len(mstate["timeline"])

        if sess["game"] == "chess":
            self._play_chess(sess, mstate, play)
        else:
            self._play_go(sess, mstate, play)

        if not play['finished']:
            self._adjudicate_match(sess, mstate, play)

        mstate["plies_played"] = len(mstate["timeline"])
        mstate["game_finished"] = bool(play["finished"])
        mstate["resumable"] = not play["finished"]
        sess["_match_internal"]["confrontation_highlights"] = play["highlights"]

        new_plies = mstate["plies_played"] - start_plies
        if play["finished"]:
            return (
                f"Partida concluída por regra ({play['termination']}) com {mstate['plies_played']} lances "
                f"({new_plies} nesta execução)."
            )
        return (
            f"Orçamento de {mstate['plies_budget']} lances esgotado sem encerramento formal: "
            f"{mstate['plies_played']} lances jogados; partida retomável, nenhum vencedor atribuído."
        )

    def _adjudicate_match(self, sess, mstate, play):
        """Tournament closing rule; never claims an unfinished board is checkmate."""
        if sess['game'] == 'chess':
            board = self.sm.chess_engines[sess['id']].board
            outcome = board.outcome(claim_draw=True)
            if outcome:
                play.update(finished=True, termination=outcome.termination.name.lower(),
                            winner_color=None if outcome.winner is None else 'white' if outcome.winner else 'black')
                return
            white, black = material_cp(board, chess.WHITE), material_cp(board, chess.BLACK)
            method = 'Adjudicação por material: peão 100, cavalo 320, bispo 330, torre 500, dama 900; igualdade é empate.'
        else:
            black, white = self.sm.go_engines[sess['id']].calculate_area_score()
            method = 'Adjudicação por área na posição de encerramento, incluindo o komi das Brancas.'
        winner = 'white' if white > black else 'black' if black > white else None
        play.update(finished=True, termination='adjudication', winner_color=winner)
        play['adjudication'] = {'white_score': white, 'black_score': black, 'method': method,
                                'scheduled_plies': mstate['plies_budget'], 'actual_plies': len(mstate['timeline'])}
        self.sm._append_session_event(sess['id'], 'MATCH_ADJUDICATED', {
            **play['adjudication'], 'winner_color': winner,
            'reason': 'Encerramento definitivo pela regra de duração declarada antes da pesquisa.',
        })

    # ------------------------------------------------------------------ Xadrez
    def _play_chess(self, sess: Dict[str, Any], mstate: Dict[str, Any], play: Dict[str, Any]) -> None:
        engine: EpistemicChessEngine = self.sm.chess_engines[sess["id"]]
        board = engine.board
        player = ChessPlayer(play["seed"], depth=2)
        pieces_by_id = {p["piece_id"]: p for p in mstate["pieces"]}
        sq_to_pid: Dict[str, str] = play["sq_to_pid"]

        while not play["finished"] and engine.ply_count < mstate["plies_budget"]:
            outcome = board.outcome(claim_draw=True)
            if outcome is not None:
                play["finished"] = True
                play["termination"] = outcome.termination.name.lower()
                play["winner_color"] = (
                    None if outcome.winner is None else ("white" if outcome.winner == chess.WHITE else "black")
                )
                break

            acting_color = engine.turn
            acting_side = "pro" if acting_color == mstate["pro_color"] else "contra"

            # v2.3 C04: Resignação automática desabilitada por padrão; só ativa se explícito
            auto_resign_on = getattr(self, "enable_auto_resignation", False) or sess.get("enable_auto_resignation", False)
            mine = chess.WHITE if acting_color == "white" else chess.BLACK
            deficit = material_cp(board, not mine) - material_cp(board, mine)
            if auto_resign_on and engine.ply_count >= RESIGN_MIN_PLY and deficit >= RESIGN_DEFICIT_CP:
                play["resign_streak"][acting_color] += 1
            else:
                play["resign_streak"][acting_color] = 0
            if auto_resign_on and play["resign_streak"][acting_color] >= RESIGN_STREAK:
                play["finished"] = True
                play["termination"] = "resignation"
                play["resigned_color"] = acting_color
                play["winner_color"] = "black" if acting_color == "white" else "white"
                self.sm._append_session_event(
                    sess["id"],
                    "MATCH_RESIGNATION",
                    {
                        "resigned_color": acting_color,
                        "thesis_side": acting_side,
                        "ply_count": engine.ply_count,
                        "material_deficit_cp": deficit,
                    },
                )
                play["highlights"].append(
                    f"Lance #{engine.ply_count}: {acting_color} resigna com déficit material de {deficit} cp."
                )
                break

            ply_idx = engine.ply_count + 1
            bias = {}
            for sq_name, pid in sq_to_pid.items():
                doc = pieces_by_id.get(pid)
                if doc:
                    bias[chess.parse_square(sq_name)] = (doc["confidence_score"] - 0.5) * 30.0
            ranked = player.rank_moves(board, bias)
            mv, block_note, clash_info = self._gate_chess_move(sess, board, ranked, sq_to_pid, pieces_by_id, ply_idx)
            self._apply_chess_move(sess, mstate, play, engine, mv, block_note, ply_idx, acting_side, acting_color, pieces_by_id, clash_info)

    def _gate_chess_move(self, sess, board, ranked, sq_to_pid, pieces_by_id, ply_idx):
        """
        No Xadrez Epistêmico (v2.5), capturas são condicionadas à autorização do SemanticClashEngine.
        Se a defesa do defensor for bem-sucedida ou o Rei estiver protegido por subteses ativas,
        a captura é rejeitada, a tentativa é registrada e o motor busca o próximo lance legal admissível.
        """
        session_id = sess["id"]
        all_pieces = list(pieces_by_id.values())
        first_block: Optional[str] = None
        first_clash_res: Optional[Dict[str, Any]] = None

        for score, mv in ranked:
            if not board.is_capture(mv):
                # Lance posicional de avanço/reorganização é livre
                return mv, first_block, first_clash_res

            att_sq = chess.square_name(mv.from_square)
            def_sq = chess.square_name(mv.to_square)
            if board.is_en_passant(mv):
                def_sq = chess.square_name(chess.square(chess.square_file(mv.to_square), chess.square_rank(mv.from_square)))

            att = pieces_by_id.get(sq_to_pid.get(att_sq, ""))
            dfn = pieces_by_id.get(sq_to_pid.get(def_sq, ""))

            if not att or not dfn:
                return mv, first_block, first_clash_res

            # Executa a arbitragem semântica rigorosa (v2.5)
            clash_res = self.sm.clash_engine.evaluate_confrontation(
                session_id=session_id,
                attacker=att,
                defender=dfn,
                from_coord=att_sq,
                to_coord=def_sq,
                board_fen=board.fen(),
                all_pieces=all_pieces,
            )

            verdict = clash_res.get("verdict")
            if verdict == "CAPTURE_AUTHORIZED":
                # Captura autorizada pela refutação documental comprovada!
                return mv, first_block, clash_res

            # Captura rejeitada: a defesa resistiu ou o Rei está protegido
            fail_note = f"Tentativa de captura {att_sq} → {def_sq} rejeitada: {clash_res.get('justification')}"
            if first_block is None:
                first_block = fail_note
                first_clash_res = clash_res

            # Registra tentativa fracassada no histórico de confrontos (Critério 8)
            attempt_entry = {
                "ply": ply_idx,
                "move": board.san(mv),
                "attacker_piece_id": att["piece_id"],
                "defender_piece_id": dfn["piece_id"],
                "from_coord": att_sq,
                "to_coord": def_sq,
                "verdict": verdict,
                "justification": clash_res.get("justification"),
                "is_king_protected": clash_res.get("is_king_protected", False),
                "captured": False,
            }
            att.setdefault("confrontation_history", []).append(attempt_entry)
            dfn.setdefault("confrontation_history", []).append(attempt_entry)

            att.setdefault("history", []).append(
                PieceHistoryEntrySchema(
                    ply=ply_idx,
                    move_label=board.san(mv),
                    from_coord=att_sq,
                    to_coord=def_sq,
                    event_kind="CONFRONTATION_BLOCKED",
                    summary=fail_note,
                    arbiter_verdict=verdict,
                ).model_dump()
            )

        # Se todas as capturas foram rejeitadas, busca lance não capturante legal
        non_caps = [m for m in board.legal_moves if not board.is_capture(m)]
        if non_caps:
            return non_caps[0], first_block, first_clash_res

        # Caso extremo: apenas capturas rejeitadas disponíveis
        return ranked[0][1], first_block, first_clash_res

    def _apply_chess_move(self, sess, mstate, play, engine, mv, block_note, ply_idx, acting_side, acting_color, pieces_by_id, clash_info=None):
        sq_to_pid = play["sq_to_pid"]
        board = engine.board
        from_sq = chess.square_name(mv.from_square)
        to_sq = chess.square_name(mv.to_square)
        is_ep = board.is_en_passant(mv)
        is_castle = board.is_castling(mv)
        is_cap = board.is_capture(mv)
        cap_sq = to_sq
        if is_ep:
            cap_sq = chess.square_name(chess.square(chess.square_file(mv.to_square), chess.square_rank(mv.from_square)))
        attacker_pid = sq_to_pid.get(from_sq)
        captured_pid = sq_to_pid.get(cap_sq) if is_cap else None
        att = pieces_by_id.get(attacker_pid) if attacker_pid else None
        cap = pieces_by_id.get(captured_pid) if captured_pid else None

        res = engine.validate_and_apply_move(mv.uci())
        if not res.legal:  # defesa: nunca deveria ocorrer, pois o lance veio de board.legal_moves
            raise RuntimeError(f"Motor rejeitou lance legal {mv.uci()}: {res.error}")
        play["recent_uci"].append(mv.uci())

        if is_cap:
            sq_to_pid.pop(cap_sq, None)
        sq_to_pid.pop(from_sq, None)
        if attacker_pid:
            sq_to_pid[to_sq] = attacker_pid
            att["current_coord"] = to_sq
        if is_castle:
            rook_moves = {"g1": ("h1", "f1"), "c1": ("a1", "d1"), "g8": ("h8", "f8"), "c8": ("a8", "d8")}
            if to_sq in rook_moves:
                r_from, r_to = rook_moves[to_sq]
                rpid = sq_to_pid.pop(r_from, None)
                if rpid:
                    sq_to_pid[r_to] = rpid
                    pieces_by_id[rpid]["current_coord"] = r_to

        quote_txt = art_title = art_id = None
        if att and att["supporting_artifacts"]:
            ref = att["supporting_artifacts"][0]
            if ref.get("played_at_ply") is None:
                ref["played_at_ply"] = ply_idx
            art_title, art_id, quote_txt = ref.get("title"), ref.get("artifact_id"), ref.get("quote_text")

        note = block_note
        if is_cap and cap and att:
            cap["alive"] = False
            cap["board_status"] = "captured"
            cap["current_coord"] = None
            cap["captured_at_ply"] = ply_idx
            cap["captured_by_piece_id"] = att["piece_id"]
            for aref in att["supporting_artifacts"][:1]:
                cap["counter_artifacts"].append(copy.deepcopy(aref))

            clash_verdict = clash_info.get("verdict", "CAPTURE_AUTHORIZED") if clash_info else "CAPTURE_AUTHORIZED"
            clash_just = clash_info.get("justification", f"Refutação argumentativa bem-sucedida em {to_sq}.") if clash_info else f"Captura autorizada por refutação documental."

            note = f"Capturada no lance #{ply_idx} ({res.san}) por {att['label']}: {clash_just}"
            cap["fall_explanation"] = note

            confrontation_record = {
                "ply": ply_idx,
                "move": res.san,
                "attacker_piece_id": att["piece_id"],
                "defender_piece_id": cap["piece_id"],
                "from_coord": from_sq,
                "to_coord": to_sq,
                "verdict": clash_verdict,
                "justification": clash_just,
                "is_king_protected": False,
                "captured": True,
            }
            att.setdefault("confrontation_history", []).append(confrontation_record)
            cap.setdefault("confrontation_history", []).append(confrontation_record)

            cap["history"].append(
                PieceHistoryEntrySchema(
                    ply=ply_idx, move_label=res.san, from_coord=from_sq, to_coord=to_sq,
                    event_kind="PIECE_CAPTURED", summary=note, arbiter_verdict=clash_verdict,
                ).model_dump()
            )
            play["highlights"].append(f"Lance #{ply_idx} ({res.san}): {note}")
        if att:
            att.setdefault("board_status", "active")
            att["history"].append(
                PieceHistoryEntrySchema(
                    ply=ply_idx, move_label=res.san, from_coord=from_sq, to_coord=to_sq,
                    event_kind="CONFRONTATION_WON" if is_cap else "ADVANCE",
                    summary=(f"Capturou {cap['label']} em {to_sq} após refutação comprovada." if (is_cap and cap)
                             else f"Posicionou '{att['role']}' em {to_sq}."),
                    arbiter_verdict=clash_info.get("verdict", "CONFRONTATION_WON") if (is_cap and clash_info) else att["epistemic_status"],
                ).model_dump()
            )

        board_schema = self._chess_board_schema(engine)
        sess["board"] = board_schema.model_dump()
        sess["ply_count"] = sess["investigation_step_index"] = engine.ply_count
        ev = self._record_ply_claim_and_event(
            sess=sess, ply_idx=ply_idx, acting_side=acting_side, acting_color=acting_color,
            move_raw=mv.uci(), san_label=res.san, piece_doc=att, confrontation_note=note,
        )

        diff_white = material_diff_white_cp(engine.board)
        diff_pro = diff_white if mstate["pro_color"] == "white" else -diff_white
        momentum = round(1.0 / (1.0 + 10 ** (-diff_pro / 400.0)), 3)
        ctrl_audit = (
            self._build_control_audit(sess, ply_idx, acting_color, att, cap, quote_txt, is_cap)
            if sess.get("mode") == "audit"
            else None
        )
        # v2.3 C11: Construção do payload auditável completo
        audit_payload = MoveAuditPayloadSchema(
            session_id=sess["id"],
            ply=ply_idx,
            game="chess",
            move={
                "uci": mv.uci(),
                "san": res.san,
                "from": from_sq,
                "to": to_sq,
                "color": acting_color,
                "kind": "capture" if is_cap else "advance",
            },
            piece={
                "id": att["piece_id"] if att else "unknown",
                "role": att["role"] if att else "",
                "label": att["label"] if att else "",
                "claim_id": (att.get("claim_id") or att["piece_id"]) if att else "",
                "claim_statement": att["claim"] if att else "",
            },
            opponent={
                "piece_id": cap["piece_id"],
                "role": cap["role"],
                "label": cap["label"],
                "claim_id": (cap.get("claim_id") or cap["piece_id"]) if cap else "",
                "claim_statement": cap["claim"] if cap else "",
            } if (is_cap and cap) else None,
            evidence={
                "attacker_artifact_ids": [a.get("artifact_id") for a in (att.get("supporting_artifacts") or []) if a.get("artifact_id")] if att else [],
                "defender_artifact_ids": [a.get("artifact_id") for a in (cap.get("supporting_artifacts") or []) if a.get("artifact_id")] if (is_cap and cap) else [],
                "quotes": [quote_txt] if quote_txt else [],
                "source_status": "SOURCE_VERIFIED" if quote_txt and att and any(a.get("verified") and a.get("quote_text") == quote_txt for a in att.get("supporting_artifacts", [])) else "UNVERIFIED",
            },
            argument_verdict={
                "status": (clash_info.get("verdict") if clash_info else "CAPTURE_AUTHORIZED") if is_cap else (att.get("epistemic_status", "SOURCE_VERIFIED") if att else "UNVERIFIED"),
                "reason": (
                    (clash_info.get("justification") if clash_info else "Captura autorizada por refutação documental.")
                    if is_cap
                    else f"Avanço posicional de {att['label']} no lance #{ply_idx}."
                ) if att else "Movimento registrado.",
                "reviewer": "semantic_clash_engine" if is_cap else "arbiter_engine",
                "evaluated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            },
            board_outcome={
                "physical_capture": is_cap,
                "check": engine.board.is_check(),
                "mate": engine.board.is_checkmate(),
                "fen_after": engine.board.fen(),
            },
            event_seq=ev.get("seq", ply_idx),
            event_hash=ev.get("hash") or ev.get("event_hash"),
            move_event_seq=ev.get("move_seq", ply_idx),
            control_audit=ctrl_audit,
        )

        mstate["timeline"].append(
            MatchPlyRecordSchema(
                ply=ply_idx, event_seq=ev["seq"], move_event_seq=ev.get("move_seq", ply_idx), side=acting_side, color=acting_color,
                move=mv.uci(), san=res.san, from_coord=from_sq, to_coord=to_sq,
                piece_id=att["piece_id"] if att else "unknown",
                piece_label=att["label"] if att else acting_color,
                piece_role=att["role"] if att else "Análise",
                claim_statement=att["claim"] if att else sess["title"],
                quote_text=quote_txt, artifact_title=art_title, artifact_id=art_id,
                epistemic_verdict=att["epistemic_status"] if att else "HYPOTHESIS",
                is_capture=is_cap, epistemic_blocked=bool(block_note),
                captured_piece_id=cap["piece_id"] if cap else None,
                captured_piece_label=cap["label"] if cap else None,
                confrontation_summary=note, pro_momentum=momentum, board_snapshot=board_schema,
                piece_coords_snapshot={p["piece_id"]: p["current_coord"] for p in mstate["pieces"]},
                audit_payload=audit_payload,
                control_audit=ctrl_audit,
            ).model_dump()
        )

    # ------------------------------------------------------------------ Go
    def _play_go(self, sess: Dict[str, Any], mstate: Dict[str, Any], play: Dict[str, Any]) -> None:
        engine: GoEngine9x9 = self.sm.go_engines[sess["id"]]
        player = GoPlayer(play["seed"])
        pieces_by_id = {p["piece_id"]: p for p in mstate["pieces"]}
        groups = {
            "pro": [p for p in mstate["pieces"] if p["side"] == "pro"],
            "contra": [p for p in mstate["pieces"] if p["side"] == "contra"],
        }
        coord_to_gid: Dict[str, str] = play["coord_to_gid"]

        while not play["finished"] and engine.ply_count < mstate["plies_budget"]:
            if engine.is_game_over:
                play["finished"] = True
                break
            ply_idx = engine.ply_count + 1
            acting_color = "black" if engine.turn == "B" else "white"
            acting_side = "pro" if acting_color == mstate["pro_color"] else "contra"
            coord = player.choose(engine, ply_idx)
            res = engine.play_move(coord)
            if not res.legal:
                raise RuntimeError(f"Motor Go rejeitou jogada escolhida {coord}: {res.error}")

            if res.is_pass:
                active = groups[acting_side][0]
                note = "Passe: sem jogada útil restante para este lado (fronteiras consolidadas)."
            else:
                gid = player.nearest_group_id(res.coord_str, groups[acting_side], engine)
                active = pieces_by_id[gid]
                active["stones"].append(res.coord_str)
                active["current_coord"] = res.coord_str
                coord_to_gid[res.coord_str] = gid
                note = None

            quote_txt = art_title = art_id = None
            if active["supporting_artifacts"] and not res.is_pass:
                ref = active["supporting_artifacts"][0]
                if ref.get("played_at_ply") is None:
                    ref["played_at_ply"] = ply_idx
                art_title, art_id, quote_txt = ref.get("title"), ref.get("artifact_id"), ref.get("quote_text")

            cap_gid = cap_label = None
            if res.is_capture and res.captured_stones:
                for cc, rr in res.captured_stones:
                    cap_coord = engine.format_coord(cc, rr)
                    gid2 = coord_to_gid.pop(cap_coord, None)
                    if gid2 and gid2 in pieces_by_id:
                        gdoc = pieces_by_id[gid2]
                        if cap_coord in gdoc["stones"]:
                            gdoc["stones"].remove(cap_coord)
                        cap_gid, cap_label = gid2, gdoc["label"]
                        if not gdoc["stones"]:
                            gdoc["alive"] = False
                            gdoc["captured_at_ply"] = ply_idx
                            gdoc["captured_by_piece_id"] = active["piece_id"]
                            gdoc["current_coord"] = None
                        # v2.3 C02: Captura em Go é territorial; não é refutação da tese
                        gdoc["fall_explanation"] = f"Pedra(s) capturada(s) por cerco territorial em {res.coord_str} no lance #{ply_idx}."
                        for aref in active["supporting_artifacts"][:1]:
                            gdoc["counter_artifacts"].append(copy.deepcopy(aref))
                        note = gdoc["fall_explanation"]
                        play["highlights"].append(f"Jogada #{ply_idx} ({res.coord_str}): {note}")

            active["history"].append(
                PieceHistoryEntrySchema(
                    ply=ply_idx, move_label=res.coord_str, to_coord=None if res.is_pass else res.coord_str,
                    event_kind="CONFRONTATION_WON" if res.is_capture else "TERRITORY_PRESSURE",
                    summary=note or f"Expandiu '{active['role']}' em {res.coord_str}.",
                    arbiter_verdict=active["epistemic_status"],
                ).model_dump()
            )

            board_schema = self._go_board_schema(engine)
            sess["board"] = board_schema.model_dump()
            sess["ply_count"] = sess["investigation_step_index"] = engine.ply_count
            ev = self._record_ply_claim_and_event(
                sess=sess, ply_idx=ply_idx, acting_side=acting_side, acting_color=acting_color,
                move_raw=res.coord_str, san_label=res.coord_str, piece_doc=active, confrontation_note=note,
            )

            b_sc, w_sc = engine.calculate_area_score()
            pro_sc, con_sc = (b_sc, w_sc) if mstate["pro_color"] == "black" else (w_sc, b_sc)
            momentum = round(min(0.97, max(0.03, pro_sc / max(1.0, pro_sc + con_sc))), 3)
            go_ctrl_audit = (
                self._build_control_audit(sess, ply_idx, acting_color, active, None, quote_txt, res.is_capture)
                if sess.get("mode") == "audit"
                else None
            )
            go_audit_payload = MoveAuditPayloadSchema(
                session_id=sess["id"],
                ply=ply_idx,
                game="go",
                move={
                    "uci": res.coord_str,
                    "san": res.coord_str,
                    "from": None,
                    "to": None if res.is_pass else res.coord_str,
                    "color": acting_color,
                    "kind": "pass" if res.is_pass else ("capture" if res.is_capture else "placement"),
                },
                piece={
                    "id": active["piece_id"],
                    "role": active["role"],
                    "label": active["label"],
                    "claim_id": active.get("claim_id") or active["piece_id"],
                    "claim_statement": active["claim"],
                },
                opponent={
                    "piece_id": cap_gid,
                    "role": cap_label or "",
                    "label": cap_label or "",
                    "claim_id": cap_gid,
                    "claim_statement": "",
                } if (res.is_capture and cap_gid) else None,
                evidence={
                    "attacker_artifact_ids": [a.get("artifact_id") for a in (active.get("supporting_artifacts") or []) if a.get("artifact_id")],
                    "defender_artifact_ids": [],
                    "quotes": [quote_txt] if quote_txt else [],
                    "source_status": "SOURCE_VERIFIED" if quote_txt and any(a.get("verified") and a.get("quote_text") == quote_txt for a in active.get("supporting_artifacts", [])) else "UNVERIFIED",
                },
                argument_verdict={
                    "status": "INCONCLUSIVE" if res.is_capture else active.get("epistemic_status", "SOURCE_VERIFIED"),
                    "reason": (
                        "Captura territorial de pedras; refutação factual independente não avaliada nesta jogada."
                        if res.is_capture
                        else ("Passe de jogada." if res.is_pass else f"Posicionamento territorial em {res.coord_str}.")
                    ),
                    "reviewer": "arbiter_engine",
                    "evaluated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                },
                board_outcome={
                    "physical_capture": res.is_capture,
                    "check": False,
                    "mate": False,
                    "captured_black": engine.captured_by_white,
                    "captured_white": engine.captured_by_black,
                },
                event_seq=ev.get("seq", ply_idx),
                event_hash=ev.get("hash") or ev.get("event_hash"),
                move_event_seq=ev.get("move_seq", ply_idx),
                control_audit=go_ctrl_audit,
            )

            mstate["timeline"].append(
                MatchPlyRecordSchema(
                    ply=ply_idx, event_seq=ev["seq"], move_event_seq=ev.get("move_seq", ply_idx), side=acting_side, color=acting_color,
                    move=res.coord_str, san=res.coord_str, to_coord=None if res.is_pass else res.coord_str,
                    piece_id=active["piece_id"], piece_label=active["label"], piece_role=active["role"],
                    claim_statement=active["claim"], quote_text=quote_txt, artifact_title=art_title,
                    artifact_id=art_id, epistemic_verdict=active["epistemic_status"],
                    is_capture=res.is_capture, captured_piece_id=cap_gid, captured_piece_label=cap_label,
                    confrontation_summary=note, pro_momentum=momentum, board_snapshot=board_schema,
                    piece_coords_snapshot={p["piece_id"]: p["current_coord"] for p in mstate["pieces"]},
                    piece_stones_snapshot={p["piece_id"]: list(p["stones"]) for p in mstate["pieces"]},
                    audit_payload=go_audit_payload,
                    control_audit=go_ctrl_audit,
                ).model_dump()
            )

            if engine.is_game_over:
                play["finished"] = True
                play["termination"] = "two_consecutive_passes"
                wc = "black" if str(engine.game_result).startswith("B") else "white"
                play["winner_color"] = wc
                break

