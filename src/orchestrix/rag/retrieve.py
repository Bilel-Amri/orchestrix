"""Hybrid retrieval — squelette à implémenter (Lot A).

Combine :
  1. Recherche vectorielle (pgvector + sentence-transformers/all-MiniLM-L6-v2)
  2. BM25 (via pg_trgm ou rank_bm25)
  3. Filtres metadata (source ∈ {josse, itemlet, public_jira, policy})
  4. Reranking optionnel (cross-encoder/ms-marco-MiniLM-L-6-v2)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    """Un chunk de preuve retourné par le retrieveur."""

    content: str
    source: str  # 'josse' | 'itemlet' | 'public_jira' | 'policy'
    type: str  # 'task' | 'issue_metadata' | 'dependency' | 'comment' | 'policy'
    metadata: dict
    score: float
    chunk_id: str | None = None


def retrieve_evidence(
    query: str,
    top_k: int = 8,
    sources: list[str] | None = None,
    types: list[str] | None = None,
    use_reranker: bool = False,
) -> list[RetrievedChunk]:
    """Récupère les preuves les plus pertinentes pour un brief.

    Args:
        query: brief projet (texte libre)
        top_k: nombre de chunks à retourner
        sources: filtre sur source ∈ ['josse', 'itemlet', 'public_jira', 'policy']
        types: filtre sur type
        use_reranker: si True, applique un cross-encoder reranker

    Returns:
        Liste de RetrievedChunk triés par score décroissant
    """
    raise NotImplementedError("retrieve_evidence : voir README pour le pipeline à implémenter.")


def embed_query(query: str) -> list[float]:
    """Calcule l'embedding d'une requête avec le modèle configuré (.env)."""
    raise NotImplementedError


def index_evidence(chunks: list[dict]) -> int:
    """Index un batch de chunks dans pgvector avec embeddings.

    Chaque chunk doit avoir : content, source, type, metadata.
    Returns: nombre de chunks indexés.
    """
    raise NotImplementedError
