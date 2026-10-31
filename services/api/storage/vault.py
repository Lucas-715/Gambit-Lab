"""
Private Document Vault & Integrity Registry — Gambit Lab 2.0
Cofres isolados (Side A / Side B), hash SHA-256 de artefatos,
manifesto congelado e controle de acesso mínimo para arbitragem.
(ADR-006, RF-04, RF-05, RF-08, RN-13, RN-14, RN-16, AC-09, AC-11)
"""
import hashlib
import uuid
import datetime
from typing import Dict, Any, List, Optional


class DocumentAccessForbiddenError(Exception):
    """Lançada quando um ator tenta acessar documentos privados do lado oposto (HTTP 403)."""
    pass


class DocumentVault:
    def __init__(self):
        # artifact_id -> Artifact Data
        self._artifacts: Dict[str, Dict[str, Any]] = {}
        # session_id -> { "is_locked": bool, "side_a_manifest": List[str], "side_b_manifest": List[str] }
        self._session_locks: Dict[str, Dict[str, Any]] = {}

    def ingest_document(
        self,
        session_id: str,
        name: str,
        content: str,
        mime_type: str = "text/plain",
        owner_side: str = "public"
    ) -> Dict[str, Any]:
        """
        Recebe texto de um documento, calcula o hash SHA-256 e registra o artefato.
        """
        sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
        artifact_id = f"art_{uuid.uuid4().hex[:12]}"

        artifact = {
            "id": artifact_id,
            "session_id": session_id,
            "name": name,
            "sha256": sha256,
            "mime_type": mime_type,
            "owner_side": owner_side,  # 'white', 'black', ou 'public'
            "content": content,
            "char_count": len(content),
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        self._artifacts[artifact_id] = artifact
        return artifact

    def get_artifact(self, artifact_id: str, requesting_side: Optional[str] = None) -> Dict[str, Any]:
        if artifact_id not in self._artifacts:
            raise KeyError(f"Artefato {artifact_id} não encontrado.")

        art = self._artifacts[artifact_id]
        owner = art["owner_side"]

        # Se for público, qualquer lado pode ver
        if owner == "public":
            return art

        # Se houver restrição de lado e não for o dono nem árbitro autorizado:
        if requesting_side and requesting_side != owner and requesting_side != "arbitrator":
            raise DocumentAccessForbiddenError(
                f"Acesso negado: o artefato {artifact_id} pertence ao cofre privado do lado '{owner}'."
            )
        return art

    def lock_session_vaults(self, session_id: str) -> Dict[str, Any]:
        """
        Congela os manifestos dos cofres pré-partida (RN-14, AC-12).
        Retorna o manifesto de hashes imutáveis.
        """
        session_arts = [a for a in self._artifacts.values() if a["session_id"] == session_id]
        manifest_a = [a["sha256"] for a in session_arts if a["owner_side"] == "white"]
        manifest_b = [a["sha256"] for a in session_arts if a["owner_side"] == "black"]
        manifest_pub = [a["sha256"] for a in session_arts if a["owner_side"] == "public"]

        lock_data = {
            "is_locked": True,
            "white_manifest": manifest_a,
            "black_manifest": manifest_b,
            "public_manifest": manifest_pub,
            "locked_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        self._session_locks[session_id] = lock_data
        return lock_data

    def verify_quote_exists(self, artifact_id: str, quote_text: str) -> bool:
        """
        Verifica se a citação alegada realmente consta no texto do documento (RF-29, AC-09).
        """
        if artifact_id not in self._artifacts:
            return False
        content = self._artifacts[artifact_id]["content"]
        # Normalização simples de quebras de linha e espaços para comparação robusta
        norm_content = " ".join(content.split())
        norm_quote = " ".join(quote_text.split())
        return norm_quote in norm_content

    def list_artifacts_for_session(self, session_id: str, requesting_side: Optional[str] = None) -> List[Dict[str, Any]]:
        results = []
        for art in self._artifacts.values():
            if art["session_id"] != session_id:
                continue
            if requesting_side and art["owner_side"] not in ("public", requesting_side, "arbitrator"):
                continue
            # Retorna metadados sem o corpo bruto inteiro
            item = art.copy()
            item["content_preview"] = art["content"][:200]
            del item["content"]
            results.append(item)
        return results
