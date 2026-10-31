"""
Private Document Vault & Integrity Registry — Gambit Lab Nocturne (R1.0)
Cofres isolados (Side A / Side B), hash SHA-256 de artefatos e snapshots web,
manifesto congelado, localização exata de offset de citações e controle de acesso 403.
(ADR-006, RF-04, RF-05, RF-08, RN-13, RN-14, RN-16, AC-09, AC-11, AT-14, AT-19)
"""
import hashlib
import uuid
import datetime
from typing import Dict, Any, List, Optional, Tuple


class DocumentAccessForbiddenError(Exception):
    """Lançada quando um ator tenta acessar documentos privados do lado oposto (HTTP 403)."""
    pass


class DocumentVault:
    def __init__(self):
        # artifact_id -> Artifact Data
        self._artifacts: Dict[str, Dict[str, Any]] = {}
        # session_id -> { "is_locked": bool, "white_manifest": List[str], ... }
        self._session_locks: Dict[str, Dict[str, Any]] = {}

    def ingest_document(
        self,
        session_id: str,
        name: str,
        content: str,
        mime_type: str = "text/plain",
        owner_side: str = "public",
        source_type: str = "document",
        url: Optional[str] = None,
        canonical_url: Optional[str] = None,
        domain: Optional[str] = None,
        retrieved_at: Optional[str] = None,
        accessible: bool = True,
    ) -> Dict[str, Any]:
        """
        Recebe texto de um documento ou snapshot web auditável, calcula o hash SHA-256 e registra o artefato.
        """
        sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
        # Evita duplicar exatamente o mesmo conteúdo na mesma sessão e cofre
        for existing in self._artifacts.values():
            if (
                existing["session_id"] == session_id
                and existing["sha256"] == sha256
                and existing["owner_side"] == owner_side
            ):
                return existing

        artifact_id = f"art_{uuid.uuid4().hex[:12]}"
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        artifact = {
            "id": artifact_id,
            "session_id": session_id,
            "name": name,
            "sha256": sha256,
            "mime_type": mime_type,
            "owner_side": owner_side,  # 'white', 'black', ou 'public'
            "source_type": source_type,  # 'document' ou 'web'
            "url": url,
            "canonical_url": canonical_url,
            "domain": domain,
            "retrieved_at": retrieved_at or (now if source_type == "web" else None),
            "accessible": accessible,
            "content": content,
            "char_count": len(content),
            "created_at": now,
        }
        self._artifacts[artifact_id] = artifact
        return artifact

    def get_artifact(self, artifact_id: str, requesting_side: Optional[str] = None) -> Dict[str, Any]:
        if artifact_id not in self._artifacts:
            raise KeyError(f"Artefato {artifact_id} não encontrado.")

        art = self._artifacts[artifact_id]
        owner = art["owner_side"]

        if owner == "public":
            return art

        if requesting_side and requesting_side != owner and requesting_side != "arbitrator":
            raise DocumentAccessForbiddenError(
                f"Acesso negado: o artefato {artifact_id} pertence ao cofre privado do lado '{owner}'."
            )
        return art

    def get_accessible_artifacts_with_content(
        self, session_id: str, requesting_side: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retorna artefatos acessíveis ao lado solicitante (incluindo conteúdo para verificação/agente autorizado)."""
        results = []
        for art in self._artifacts.values():
            if art["session_id"] != session_id:
                continue
            if requesting_side and art["owner_side"] not in ("public", requesting_side, "arbitrator"):
                continue
            results.append(art)
        return results

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
            "locked_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        self._session_locks[session_id] = lock_data
        return lock_data

    def find_verified_quote_offset(self, artifact_id: str, quote_text: str) -> Tuple[bool, Optional[str]]:
        """
        Localiza literalmente a citação alegada no texto normalizado do documento e retorna (verificado, offset).
        Rejeita citações vazias ou curtas demais (< 4 caracteres úteis).
        """
        if not artifact_id or artifact_id not in self._artifacts or not quote_text:
            return False, None
        norm_quote = " ".join(quote_text.split()).strip()
        if len(norm_quote) < 4:
            return False, None
        content = self._artifacts[artifact_id]["content"]
        norm_content = " ".join(content.split())
        idx = norm_content.find(norm_quote)
        if idx >= 0:
            return True, f"chars {idx}..{idx + len(norm_quote)}"
        # Tentativa secundária case-insensitive mantendo literalidade de palavras
        idx_ci = norm_content.lower().find(norm_quote.lower())
        if idx_ci >= 0:
            return True, f"chars {idx_ci}..{idx_ci + len(norm_quote)}"
        return False, None

    def verify_quote_exists(self, artifact_id: str, quote_text: str) -> bool:
        """
        Verifica se a citação alegada realmente consta no texto do documento (RF-29, AC-09, AT-14).
        """
        if artifact_id not in self._artifacts:
            raise KeyError(f"Artefato {artifact_id} não encontrado.")
        verified, _ = self.find_verified_quote_offset(artifact_id, quote_text)
        return verified

    def list_artifacts_for_session(
        self, session_id: str, requesting_side: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        results = []
        for art in self._artifacts.values():
            if art["session_id"] != session_id:
                continue
            if requesting_side and art["owner_side"] not in ("public", requesting_side, "arbitrator"):
                continue
            item = art.copy()
            item["content_preview"] = art["content"][:240]
            del item["content"]
            results.append(item)
        return results
