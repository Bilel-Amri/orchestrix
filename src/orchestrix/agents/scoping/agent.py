"""Scoping Agent — squelette à implémenter.

RÔLE :
    USER brief → retrieve_evidence → LLM_call (structured JSON) → validate →
                annotate_with_ML → return Plan

CONTRATS À RESPECTER :
    - Entrée : PlanGenerationRequest (src/orchestrix/schemas/plan.py)
    - Sortie : Plan (mêmes schemas)
    - Configuration : .env + src/orchestrix/config/
    - Tracking : tous les runs dans MLflow (mlflow.log_param, mlflow.log_metric)

INTERFACES DISPONIBLES :
    - LLMClient : src/orchestrix/agents/_llm_client.py
    - RAG hybrid retrieval : src/orchestrix/rag/retrieve.py  (à implémenter)
    - Effort Estimator : src/orchestrix/services/effort/estimator.py  (à entraîner)
    - Priority Estimator : src/orchestrix/services/priority/estimator.py  (à entraîner)

ABLATION A→E (section 8.3 de la proposition) :
    A — SLM base + prompt minimal
    B — SLM base + prompt structuré (schéma JSON imposé)
    C — SLM base + prompt structuré + RAG
    D — SLM base + prompt structuré + QLoRA fine-tune
    E — SLM base + prompt structuré + QLoRA fine-tune + RAG

    Chaque condition doit être testable séparément via --ablation-condition.
"""
from __future__ import annotations

import logging
from typing import Literal

from orchestrix.agents._llm_client import LLMClient
from orchestrix.agents.scoping.prompts import build_scoping_prompt
from orchestrix.schemas.plan import Plan, PlanGenerationRequest, PlanGenerationResponse

logger = logging.getLogger(__name__)


class ScopingAgent:
    """Scoping Agent — orchestrateur LangGraph (à implémenter)."""

    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm or LLMClient()
        self.graph = None  # TODO: construire le LangGraph state machine

    async def generate_plan(
        self,
        request: PlanGenerationRequest,
        ablation_condition: Literal["A", "B", "C", "D", "E"] = "C",
    ) -> PlanGenerationResponse:
        """Génère un plan depuis un brief.

        Args:
            request: brief + flags
            ablation_condition: condition d'ablation A→E

        Returns:
            Plan + métadonnées de génération

        TODO:
            1. Récupérer preuves RAG si ablation_condition ∈ {C, E} ou request.include_rag
            2. Construire le prompt selon ablation_condition
            3. Appeler self.llm.invoke(messages)
            4. Parser et valider le JSON via Pydantic
            5. Si erreur de validation → retry une fois avec prompt de correction
            6. Appeler Effort + Priority Estimators si request.include_*
            7. Tracer dans MLflow (params: ablation_condition, model, prompt_version;
               metrics: json_validity, anchored_evidence_count)
            8. Retourner PlanGenerationResponse
        """
        logger.info(
            "generate_plan called: brief_len=%d, ablation=%s, rag=%s",
            len(request.brief),
            ablation_condition,
            request.include_rag,
        )
        raise NotImplementedError(
            "ScopingAgent.generate_plan : voir docstring pour étapes à implémenter."
        )

    def _build_messages(self, request: PlanGenerationRequest, retrieved_evidence: list[str]):
        """Construit la liste de messages pour le LLM."""
        return build_scoping_prompt(request, retrieved_evidence)
