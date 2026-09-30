"""Scoping Agent — Lot A.

Génère un Plan structuré (epics + tasks + dépendances) depuis un brief
en langage naturel. Utilise LangGraph pour orchestrer :
  1. Récupération RAG (multi-sources avec metadata source/type)
  2. Appel LLM avec prompt structuré (schéma JSON imposé)
  3. Validation du JSON (Pydantic)
  4. Annotation par les services ML (Effort + Priority)
  5. Retour du Plan validé
"""
from orchestrix.agents.scoping.agent import ScopingAgent

__all__ = ["ScopingAgent"]
