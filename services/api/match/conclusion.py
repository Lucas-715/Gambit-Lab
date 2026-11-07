"""
Estágios 6 e 7 do Research Match — conclusão com DUPLO RESULTADO e selagem do replay.

Princípios (testados em tests/integration/test_research_match_v2.py):
  * `ludic_result` vem exclusivamente do motor determinístico (xeque-mate, resignação, passes/pontuação, regra de empate).
    Se o orçamento esgotar antes do fim formal => UNDECIDED, sem vencedor inventado.
  * `epistemic_result` vem exclusivamente das evidências verificadas (citação literal) — o placar do tabuleiro NÃO entra.
  * DEMO_OFFLINE nunca produz conclusão epistêmica: o conteúdo é sintético, logo OPEN_HYPOTHESIS.
"""
from typing import Any, Dict, List, Optional, Tuple

from services.api.agents.gemini_adapter import is_future_projection_topic
from services.api.agents.gemini_adapter import BudgetExceededError, ProviderUnavailableError
from services.api.models.schemas import MatchConclusionSchema
from services.api.match.decision import comparison_plan, decide

# v2.3 C03: Unidade de comparação é alegação independente; peso unitário (a verdade não é multiplicada por rei/dama)
ROLE_EPISTEMIC_WEIGHTS = {
    "king": 1.0, "queen": 1.0, "rook": 1.0, "bishop": 1.0, "knight": 1.0, "pawn": 1.0,
    "go_influence": 1.0, "go_territory": 1.0, "go_eyes": 1.0, "go_invasion": 1.0,
    "go_siege": 1.0, "go_connection": 1.0,
}
INCONCLUSIVE_MARGIN = 0.12


def epistemic_scores(pieces: List[Dict[str, Any]]) -> Tuple[float, float, int, int]:
    """
    v2.3 C03: (score_pró, score_contra, fontes_verificadas_pró, fontes_verificadas_contra).
    Unidade de análise: alegação independente e fontes deduplicadas.
    Ponderação unitária sem multiplicação por tipo de peça.
    """
    s = {"pro": 0.0, "contra": 0.0}
    seen_sources = {"pro": set(), "contra": set()}
    seen_claims = {"pro": set(), "contra": set()}

    for p in pieces:
        side = p["side"]
        refs = [a for a in p.get("supporting_artifacts", []) if a.get("verified")]
        # Fontes verificadas são contadas separadamente da sustentação das alegações.
        if p.get("epistemic_status") in ("SOURCE_VERIFIED", "EVIDENCE_REVIEWED", "SUPPORTED") and refs:
            for a in refs:
                h = a.get("sha256") or a.get("url") or a.get("artifact_id")
                if h:
                    seen_sources[side].add(h)
            claim_key = (p.get("claim") or "").strip().lower()
            if p.get("epistemic_status") == "SUPPORTED" and claim_key and claim_key not in seen_claims[side]:
                seen_claims[side].add(claim_key)
                s[side] += 1.0

    return s["pro"], s["contra"], len(seen_sources["pro"]), len(seen_sources["contra"])


class ConclusionMixin:
    def _ludic_outcome(self, sess: Dict[str, Any], mstate: Dict[str, Any], play: Dict[str, Any]) -> Dict[str, Any]:
        if sess.get("_result_interrupted"):
            return {
                "termination_criterion": "INTERRUPTED",
                "termination_reason": "Execução interrompida; resultado parcial baseado nos registros disponíveis. É possível tentar novamente a etapa pendente.",
                "ludic_result": "UNDECIDED", "ludic_score_label": "Sem resultado formal do tabuleiro",
                "winner_side": "none",
            }
        if not play["finished"]:
            n = mstate["plies_played"]
            return {
                "termination_criterion": "BUDGET_EXHAUSTED",
                "termination_reason": (
                    f"Orçamento de {mstate['plies_budget']} lances esgotado após {n} lances sem encerramento formal. "
                    "Partida retomável; nenhum vencedor foi atribuído."
                ),
                "ludic_result": "UNDECIDED",
                "ludic_score_label": "Indecidida (orçamento esgotado — retome para continuar)",
                "winner_side": "none",
            }
        term = play["termination"]
        wc = play["winner_color"]
        if term == 'adjudication':
            label = 'Brancas vencem' if wc == 'white' else 'Pretas vencem' if wc == 'black' else 'Empate'
            return {
                'termination_criterion': 'ADJUDICATED',
                'termination_reason': play['adjudication']['method'] + ' Partida encerrada; não exige lances adicionais.',
                'ludic_result': 'WHITE_WINS' if wc == 'white' else 'BLACK_WINS' if wc == 'black' else 'DRAW',
                'ludic_score_label': label + ' por adjudicação',
                'winner_side': 'draw' if wc is None else 'pro' if wc == mstate['pro_color'] else 'contra',
            }
        if wc is None:
            labels = {
                "stalemate": "Empate por afogamento (1/2-1/2)",
                "insufficient_material": "Empate por material insuficiente (1/2-1/2)",
                "fivefold_repetition": "Empate por repetição quíntupla (1/2-1/2)",
                "threefold_repetition": "Empate por tripla repetição (1/2-1/2)",
                "seventyfive_moves": "Empate pela regra dos 75 lances (1/2-1/2)",
                "fifty_moves": "Empate pela regra dos 50 lances (1/2-1/2)",
            }
            return {
                "termination_criterion": "DRAW_BY_RULE",
                "termination_reason": f"Encerramento por regra oficial: {term}.",
                "ludic_result": "DRAW",
                "ludic_score_label": labels.get(term, f"Empate ({term})"),
                "winner_side": "draw",
            }
        if sess["game"] == "go":
            eng = self.sm.go_engines[sess["id"]]
            b, w = eng.calculate_area_score()
            label = (
                f"{'Pretas' if wc == 'black' else 'Brancas'} vencem por área: "
                f"{b:.1f} (Pretas) a {w:.1f} (Brancas, komi {eng.komi}) — {eng.game_result}"
            )
            reason = "Dois passes consecutivos: partida encerrada e pontuada por área (regras chinesas)."
        elif term == "checkmate":
            label = f"{'Brancas' if wc == 'white' else 'Pretas'} vencem por xeque-mate ({'1-0' if wc == 'white' else '0-1'})"
            reason = "Xeque-mate formalmente validado pelo motor python-chess."
        else:  # resignation
            loser = play["resigned_color"]
            label = f"{'Brancas' if wc == 'white' else 'Pretas'} vencem por resignação de {loser} ({'1-0' if wc == 'white' else '0-1'})"
            reason = (
                f"Resignação formal: déficit material ≥ {800} cp sustentado por 3 turnos consecutivos de {loser}."
            )
        return {
            "termination_criterion": "BOARD_VICTORY",
            "termination_reason": reason,
            "ludic_result": "WHITE_WINS" if wc == "white" else "BLACK_WINS",
            "ludic_score_label": label,
            "winner_side": "pro" if wc == mstate["pro_color"] else "contra",
        }

    def _epistemic_outcome(self, sess: Dict[str, Any], mstate: Dict[str, Any]) -> Dict[str, Any]:
        s_pro, s_con, v_pro, v_con = epistemic_scores(mstate["pieces"])
        total = s_pro + s_con
        pro_n = round(s_pro / total, 3) if total else 0.0
        con_n = round(s_con / total, 3) if total else 0.0
        topic = sess["title"]

        if sess["execution_mode"] == "DEMO_OFFLINE":
            res, label = "OPEN_HYPOTHESIS", "Hipótese aberta (DEMO_OFFLINE: argumentos sintéticos, sem avaliação epistêmica real)"
        elif is_future_projection_topic(topic):
            res, label = "OPEN_HYPOTHESIS", "Hipótese aberta (projeção sobre evento futuro — não decidível factualmente)"
        elif v_pro == 0 and v_con == 0:
            res, label = "OPEN_HYPOTHESIS", "Hipótese aberta (nenhuma fonte com citação literal verificada em nenhum dos cofres)"
        elif total == 0:
            res, label = "INCONCLUSIVE", "Evidências localizadas; sustentação factual das teses ainda não demonstrada"
        elif abs(pro_n - con_n) < INCONCLUSIVE_MARGIN:
            res, label = "INCONCLUSIVE", "Inconclusivo (evidências verificadas equilibradas entre Pró e Contra)"
        elif pro_n > con_n:
            res, label = "PRO_THESIS_SUPPORTED", "Tese Pró mais sustentada por evidências verificadas"
        else:
            res, label = "CONTRA_THESIS_SUPPORTED", "Tese Contra mais sustentada por evidências verificadas"
        return {
            "epistemic_result": res, "epistemic_verdict_label": label,
            "pro_epistemic_score": pro_n, "contra_epistemic_score": con_n,
            "verified_sources_pro": v_pro, "verified_sources_contra": v_con,
        }

    @staticmethod
    def _turning_point(timeline: List[Dict[str, Any]]) -> Tuple[Optional[int], Optional[str]]:
        prev, best, tp = 0.5, -1.0, None
        for item in timeline:
            swing = abs(item["pro_momentum"] - prev) + (0.05 if item.get("is_capture") else 0.0)
            if swing > best and item["move"] != "PASS":
                best, tp = swing, item
            prev = item["pro_momentum"]
            item["is_turning_point"] = False
        if tp is None:
            return None, None
        tp["is_turning_point"] = True
        return tp["ply"], tp.get("confrontation_summary") or (
            f"Lance #{tp['ply']} ({tp['san']}): {tp['piece_label']} provocou a maior oscilação de vantagem do tabuleiro."
        )

    def _stage_6_evaluate_winner(self, sess: Dict[str, Any], mstate: Dict[str, Any]) -> str:
        play = sess["_match_internal"].get("play") or {"finished": False, "highlights": []}
        ludic = self._ludic_outcome(sess, mstate, play)
        epi = self._epistemic_outcome(sess, mstate)
        tp_ply, tp_sum = self._turning_point(mstate["timeline"])
        provisional = ludic["termination_criterion"] in ("BUDGET_EXHAUSTED", "INTERRUPTED")

        synth = self._safe_synthesis(
            force_local=bool(sess.get("_result_interrupted")),
            evidence_records=self._evidence_trace(mstate),
            comparison_plan=mstate.get('comparison_plan') or comparison_plan(sess['title'], sess.get('mode')),
            topic=sess["title"],
            pro_thesis=mstate["pro_thesis"],
            contra_thesis=mstate["contra_thesis"],
            ludic_score_label=ludic["ludic_score_label"],
            epistemic_result=epi["epistemic_result"],
            verified_pro=epi["verified_sources_pro"],
            verified_contra=epi["verified_sources_contra"],
            confrontation_highlights=play["highlights"],
            budget=sess["budget"],
            force_demo=(sess["execution_mode"] == "DEMO_OFFLINE"),
        )
        if synth.get("provider_usage") and synth["provider_usage"].get("source") == "gemini_api":
            sess["provider_usage"] = synth["provider_usage"]

        limitations = list(synth.get("limitations") or [])
        limitations += [
            "O resultado epistêmico considera somente evidências com citação literal verificada; o placar do tabuleiro não entra no cálculo.",
            "A verificação confirma que o trecho existe na fonte, não que ele comprove a tese (relevância depende do agente e de revisão humana).",
        ]
        if sess["execution_mode"] == "DEMO_OFFLINE":
            limitations.append("Execução DEMO_OFFLINE: textos sintéticos de demonstração, sem pesquisa nem modelo reais.")

        decision = decide(mstate.get('comparison_plan') or comparison_plan(sess['title'], sess.get('mode')),
                          synth.get('criterion_reviews', []), self._evidence_trace(mstate),
                          sess['execution_mode'], sess.get('mode'))
        limitations.append('O julgamento por critérios é uma interpretação do árbitro com referências verificadas; sua correção semântica requer revisão. Critérios sem comparação válida não pontuam.')

        mstate["conclusion"] = MatchConclusionSchema(
            **ludic, **epi,
            pro_thesis=mstate["pro_thesis"], contra_thesis=mstate["contra_thesis"],
            turning_point_ply=tp_ply, turning_point_summary=tp_sum,
            is_provisional=provisional,
            final_synthesis=(decision['answer'] + '\n\n' + synth['final_synthesis']) if decision['assessed_criteria'] else decision['answer'],
            key_arguments_pro=synth["key_arguments_pro"],
            key_arguments_contra=synth["key_arguments_contra"],
            limitations=limitations,
            synthesis_source=synth.get("synthesis_source", "provider"),
            decision=decision,
            board_adjudication=play.get('adjudication', {}),
            evidence_trace=self._evidence_trace(mstate),
            next_steps=[
                "Revisar a pertinência e a suficiência de cada trecho em relação à alegação.",
                "Anexar evidências para as alegações sem fonte e registrar os critérios de aceitação."
                if sess.get("mode") == "audit" else
                "Investigar as lacunas e confrontar as alegações com fontes independentes.",
            ],
        ).model_dump()
        return f"Resultado lúdico: {ludic['ludic_score_label']} · Epistêmico: {epi['epistemic_verdict_label']}."

    def _safe_synthesis(self, **kwargs) -> Dict[str, Any]:
        force_local = kwargs.pop("force_local", False)
        try:
            if force_local:
                raise ValueError("Interrupted investigation")
            result = self.sm.gemini_adapter.generate_match_synthesis(**kwargs)
            if (isinstance(result, dict) and isinstance(result.get("final_synthesis"), str)
                    and result["final_synthesis"].strip()
                    and all(isinstance(result.get(k), list) and all(isinstance(v, str) for v in result[k])
                            for k in ("key_arguments_pro", "key_arguments_contra", "limitations"))):
                result["synthesis_source"] = "demo_offline" if kwargs.get("force_demo") else "provider"
                return result
        except (BudgetExceededError, ProviderUnavailableError, ValueError, KeyError, TypeError):
            pass
        verdict_label = {
            "OPEN_HYPOTHESIS": "hipótese em aberto, sem comprovação factual suficiente",
            "INCONCLUSIVE": "inconclusivo; os registros não permitem decidir entre as teses",
            "PRO_THESIS_SUPPORTED": "maior sustentação documental das alegações do lado Pró",
            "CONTRA_THESIS_SUPPORTED": "maior sustentação documental das alegações do lado Contra",
        }.get(kwargs["epistemic_result"], kwargs["epistemic_result"])
        return {
            "synthesis_source": "deterministic_fallback",
            "final_synthesis": (
                f"Investigação encerrada para: {kwargs['topic']}. "
                f"Resultado das evidências: {verdict_label}. "
                f"Fontes verificadas: Pró {kwargs['verified_pro']}; Contra {kwargs['verified_contra']}. "
                "Consulte as alegações e os trechos vinculados abaixo. Uma citação existente não comprova, por si só, a tese."
            ),
            "key_arguments_pro": [], "key_arguments_contra": [],
            "limitations": ["Síntese automática indisponível; resultado produzido a partir dos registros, sem nova geração de argumentos."],
        }

    @staticmethod
    def _evidence_trace(mstate: Dict[str, Any]) -> List[Dict[str, Any]]:
        rows = []
        for piece in mstate.get("pieces", []):
            moves = [t for t in mstate.get("timeline", []) if t.get("piece_id") == piece["piece_id"]]
            rows.append({
                "piece_id": piece["piece_id"], "side": piece["side"],
                "claim": piece.get("claim", ""), "status": piece.get("epistemic_status", "HYPOTHESIS"),
                "evidence": piece.get("supporting_artifacts", []),
                "plies": [t["ply"] for t in moves],
                "event_seqs": [t["event_seq"] for t in moves],
                "finding": next((t["control_audit"] for t in reversed(moves) if t.get("control_audit")), None),
            })
        return rows

    def _stage_7_build_replay(self, sess: Dict[str, Any], mstate: Dict[str, Any]) -> str:
        play = sess["_match_internal"]["play"]
        mstate["is_complete"] = True
        mstate["percent_complete"] = 100
        mstate["status"] = "COMPLETED" if play["finished"] else "BUDGET_EXHAUSTED"
        sess["status"] = mstate["status"]
        conc = mstate["conclusion"]
        self.sm._append_session_event(
            sess["id"],
            "RESEARCH_MATCH_COMPLETED" if play["finished"] else "RESEARCH_MATCH_BUDGET_EXHAUSTED",
            {
                "total_plies": len(mstate["timeline"]),
                "termination_criterion": conc["termination_criterion"],
                "ludic_result": conc["ludic_result"],
                "epistemic_result": conc["epistemic_result"],
                "turning_point_ply": conc["turning_point_ply"],
                "conclusion": conc,
            },
        )
        return (
            f"Replay auditável pronto: {len(mstate['timeline'])} lances encadeados em SHA-256, "
            f"{len(mstate['pieces'])} dossiês de peças."
            + ("" if play["finished"] else " (partida retomável)")
        )

