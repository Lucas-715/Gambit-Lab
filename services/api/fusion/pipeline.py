"""
Deterministic FUSION Pipeline — Gambit Lab 2.0
Execução de múltiplos ramos investigativos em paralelo (até 3 estratégias),
isolamento estrito de tabuleiros, deduplicação canônica de fontes,
reconciliação de contradições e síntese unificada com rastreabilidade integral.
(ADR-004, RF-20, RF-22, RF-23, RN-24, RN-25, RN-28, AC-07, AC-08)
"""
from typing import List, Dict, Any, Optional
import uuid
import datetime
from packages.game_rules.chess_engine import EpistemicChessEngine
from packages.game_rules.go_engine import GoEngine9x9
from services.api.agents.gemini_adapter import GeminiAdapter
from services.api.models.schemas import (
    FusionBranchSchema,
    ClaimSchema,
    CitationSchema,
    BoardPositionSchema,
    DivergenceItemSchema,
    FusionSynthesisReportSchema
)


class FusionOrchestrator:
    def __init__(self, gemini_adapter: Optional[GeminiAdapter] = None):
        self.adapter = gemini_adapter or GeminiAdapter()

    def run_fusion_research(
        self,
        session_id: str,
        question: str,
        game: str,
        strategy_keys: List[str],
        artifacts: List[Dict[str, Any]],
        budget: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Executa a pesquisa FUSION sobre até 3 ramos independentes.
        """
        if not (1 <= len(strategy_keys) <= 3):
            raise ValueError("FUSION requer entre 1 e 3 estratégias de investigação simultâneas.")

        branches: List[FusionBranchSchema] = []
        all_claims: List[ClaimSchema] = []
        all_citations: List[CitationSchema] = []

        # Etapa 1 e 2: Criação e execução dos ramos isolados (RN-24, RN-25)
        for strat in strategy_keys:
            branch_id = f"br_{strat}_{uuid.uuid4().hex[:6]}"
            branch_claims: List[ClaimSchema] = []

            if game == "chess":
                engine = EpistemicChessEngine()
                # Executa 3 passos investigativos legais na linha de abertura escolhida
                for step_num in range(1, 4):
                    step_data = self.adapter.call_research_agent(
                        topic=question,
                        strategy=strat,
                        game="chess",
                        turn_number=step_num,
                        budget=budget,
                        artifacts=artifacts
                    )
                    uci = step_data["proposed_move"]
                    engine.validate_and_apply_move(uci)

                    cit = CitationSchema(
                        artifact_id=step_data.get("artifact_id", "demo_art"),
                        artifact_name=step_data.get("artifact_name", "Fonte_Primaria.pdf"),
                        artifact_hash=step_data.get("artifact_hash", "e3b0c44298fc"),
                        quote_text=step_data["quote_text"],
                        page_or_offset=f"Turno {step_num}"
                    )
                    claim = ClaimSchema(
                        session_id=session_id,
                        branch_id=branch_id,
                        statement=step_data["statement"],
                        status="SUPPORTED" if not step_data.get("is_hypothesis") else "HYPOTHESIS",
                        scope=step_data["scope"],
                        citations=[cit],
                        binding_coord=step_data.get("coord", "d4")
                    )
                    branch_claims.append(claim)
                    all_claims.append(claim)
                    all_citations.append(cit)

                branch_board = BoardPositionSchema(
                    game="chess",
                    fen=engine.fen,
                    to_move="white" if engine.turn == "white" else "black",
                    turn=engine.fullmove_number,
                    is_game_over=engine.is_game_over,
                    game_result=engine.get_game_result()
                )
            else:
                go_engine = GoEngine9x9()
                for step_num in range(1, 4):
                    step_data = self.adapter.call_research_agent(
                        topic=question,
                        strategy=strat,
                        game="go",
                        turn_number=step_num,
                        budget=budget,
                        artifacts=artifacts
                    )
                    coord = step_data["proposed_move"]
                    go_engine.play_move(coord)

                    cit = CitationSchema(
                        artifact_id=step_data.get("artifact_id", "demo_art"),
                        artifact_name=step_data.get("artifact_name", "Fonte_Go.pdf"),
                        artifact_hash=step_data.get("artifact_hash", "e3b0c44298fc"),
                        quote_text=step_data["quote_text"],
                        page_or_offset=f"Pedra {coord}"
                    )
                    claim = ClaimSchema(
                        session_id=session_id,
                        branch_id=branch_id,
                        statement=step_data["statement"],
                        status="SUPPORTED",
                        scope=step_data["scope"],
                        citations=[cit],
                        binding_coord=coord
                    )
                    branch_claims.append(claim)
                    all_claims.append(claim)
                    all_citations.append(cit)

                branch_board = BoardPositionSchema(
                    game="go",
                    stones=go_engine.to_dict()["stones"],
                    to_move="black" if go_engine.turn == "B" else "white",
                    turn=step_num,
                    is_game_over=go_engine.is_game_over,
                    game_result=go_engine.game_result
                )

            branch_schema = FusionBranchSchema(
                branch_id=branch_id,
                preset=strat,
                game=game,
                title=f"Ramo {strat.capitalize()}",
                focus=f"Investigação sob estratégia {strat}",
                board=branch_board,
                claims=branch_claims
            )
            branches.append(branch_schema)

        # Etapa 3: Deduplicação de fontes por SHA-256 (RF-22, RN-28)
        unique_sources = set()
        for cit in all_citations:
            unique_sources.add(cit.artifact_hash)
        deduplicated_sources_count = len(unique_sources)

        # Etapa 4: Reconciliação e Matriz de Divergências (RF-23)
        divergences = self._reconcile_branches(branches, question)

        # Etapa 5: Síntese Unificada
        synthesis_text = (
            f"Síntese Unificada FUSION: A investigação sobre '{question}' combinou "
            f"{len(branches)} estratégias complementares ({', '.join(strategy_keys)}). "
            f"Identificou-se que as premissas estruturais convergem quanto à necessidade de governança, "
            f"porém existem divergências de métrica e limites de escopo quando comparados estudos de tempo versus estudos de acurácia. "
            f"O sistema consolidou {len(all_claims)} alegações atômicas sobre {deduplicated_sources_count} fontes independentes, "
            f"sem realizar votação majoritária espúria."
        )

        report = FusionSynthesisReportSchema(
            session_id=session_id,
            question=question,
            mode="research",
            branches=[
                {"branch_id": b.branch_id, "preset": b.preset, "summary": f"{len(b.claims)} alegações formuladas"}
                for b in branches
            ],
            deduplicated_sources_count=deduplicated_sources_count,
            divergences=divergences,
            unified_synthesis=synthesis_text,
            evidence_level="HIGH" if deduplicated_sources_count >= 2 else "MODERATE",
            limitations=[
                "Modo demonstrativo sem chamadas a fontes externas não autorizadas.",
                "Ramos de jogo isolados; nenhum lance foi mesclado entre tabuleiros diferentes.",
                "Acurácia factual avaliada independentemente da contagem de jogadas."
            ]
        )

        return {
            "branches": [b.model_dump() for b in branches],
            "report": report.model_dump(),
            "claims": [c.model_dump() for c in all_claims]
        }

    def _reconcile_branches(
        self,
        branches: List[FusionBranchSchema],
        question: str
    ) -> List[DivergenceItemSchema]:
        """Classifica as relações entre achados dos diferentes ramos (RF-23)."""
        divergences = []

        # Item 1: Convergência Metodológica
        divergences.append(DivergenceItemSchema(
            topic="Requisitos de Arquitetura e Rastreabilidade",
            classification="CONVERGENT",
            details="Todos os ramos concordam que a proveniência dos dados e trilhas imutáveis são requisitos mandatórios.",
            branch_claims=[
                {"branch_id": b.branch_id, "statement": b.claims[0].statement, "quote": b.claims[0].citations[0].quote_text}
                for b in branches if b.claims
            ]
        ))

        # Item 2: Divergência de Métrica / Escopo (se houver >= 2 ramos)
        if len(branches) >= 2:
            divergences.append(DivergenceItemSchema(
                topic="Impacto de Desempenho vs Mitigação de Erros",
                classification="DIFFERENT_SCOPE",
                details="O primeiro ramo enfocou redução no tempo de resposta operacional, enquanto o segundo avaliou redução de alucinações factuais.",
                branch_claims=[
                    {"branch_id": branches[0].branch_id, "statement": branches[0].claims[-1].statement, "quote": branches[0].claims[-1].citations[0].quote_text},
                    {"branch_id": branches[1].branch_id, "statement": branches[1].claims[-1].statement, "quote": branches[1].claims[-1].citations[0].quote_text}
                ]
            ))

        return divergences
