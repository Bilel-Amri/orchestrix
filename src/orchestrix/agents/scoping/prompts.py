"""Prompt templates pour le Scoping Agent.

4 versions correspondent aux 4 premières conditions d'ablation :
  - prompt_minimal       (condition A)
  - prompt_structured    (condition B, C, D, E)
  - prompt_with_rag      (condition C, E — passé via include_rag=True)

Toutes les versions partagent le même schéma JSON de sortie imposé.
"""

from __future__ import annotations

import json
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage

from orchestrix.schemas.plan import PlanGenerationRequest

# Schéma JSON que le LLM DOIT respecter (condition B minimum).
PLAN_JSON_SCHEMA = {
    "type": "object",
    "required": ["brief", "epics"],
    "properties": {
        "brief": {"type": "string"},
        "epics": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["title", "description", "tasks"],
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "tasks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["title", "description"],
                            "properties": {
                                "title": {"type": "string"},
                                "description": {"type": "string"},
                                "required_skills": {"type": "array", "items": {"type": "string"}},
                                "rationale": {"type": "string"},
                            },
                        },
                    },
                },
            },
        },
    },
}


def build_scoping_prompt(
    request: PlanGenerationRequest,
    retrieved_evidence: list[str],
    ablation_condition: Literal["A", "B", "C", "D", "E"] = "C",
) -> list:
    """Construit la liste de messages système + humain pour le LLM.

    Args:
        request: requête de génération de plan
        retrieved_evidence: chunks RAG récupérés (peut être vide en condition A/B/D)
        ablation_condition: détermine le niveau de structuration du prompt

    Returns:
        Liste de messages LangChain
    """
    system_content = _build_system_prompt(ablation_condition)
    human_content = _build_human_prompt(request, retrieved_evidence, ablation_condition)

    return [
        SystemMessage(content=system_content),
        HumanMessage(content=human_content),
    ]


def _build_system_prompt(condition: str) -> str:
    """Le system prompt varie selon la condition d'ablation."""
    if condition == "A":
        # Baseline — pas de schéma imposé
        return "Tu es un assistant de gestion de projet. Décris le projet en tâches structurées."

    # B, C, D, E — schéma JSON imposé
    base = (
        "Tu es un Scoping Agent pour la gestion de projet logiciel. "
        "À partir d'un brief en langage naturel, tu produis un plan structuré "
        "d'epics et de tâches au format JSON strict.\n\n"
        f"SCHÉMA JSON À RESPECTER IMPÉRATIVEMENT :\n{json.dumps(PLAN_JSON_SCHEMA, indent=2)}\n\n"
        "RÈGLES :\n"
        "  1. Tu réponds UNIQUEMENT avec un JSON valide conforme au schéma.\n"
        "  2. Chaque tâche doit avoir un titre clair et une description actionnable.\n"
        "  3. Liste explicitement les compétences requises (required_skills).\n"
        "  4. Si des preuves historiques te sont fournies, indique pour chaque tâche "
        "     si elle est ancrée à une preuve et pourquoi (champ rationale)."
    )
    return base


def _build_human_prompt(
    request: PlanGenerationRequest,
    retrieved_evidence: list[str],
    condition: str,
) -> str:
    """Le human prompt inclut le brief et, optionnellement, les preuves RAG."""
    parts = [f"BREF DU CHEF DE PROJET :\n\n{request.brief}\n"]

    if retrieved_evidence and condition in ("C", "E"):
        parts.append("\nPREUVES HISTORIQUES PERTINENTES (à utiliser pour ancrer les tâches) :\n")
        for i, ev in enumerate(retrieved_evidence, 1):
            parts.append(f"\n[{i}] {ev}")

    parts.append(
        "\n\nProduis maintenant le plan JSON conforme au schéma. N'inclus aucun texte hors du JSON."
    )
    return "\n".join(parts)
