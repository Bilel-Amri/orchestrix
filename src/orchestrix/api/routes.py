"""Routes FastAPI — stubs à compléter.

Chaque route est définie comme un placeholder qui retourne 501 Not Implemented.
À remplir au fur et à mesure de l'implémentation.

L'API est le CONTRAT entre le Lot A et le Lot B :
  - Le Lot A ne touche QUE les routes /agent/*
  - Le Lot B ne touche QUE les routes /ops/*, /audit/*
  - Le Risk Agent (Lot A) gère /risk/*
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException

from orchestrix.schemas.audit import AuditLogEntry
from orchestrix.schemas.plan import PlanGenerationRequest, PlanGenerationResponse
from orchestrix.schemas.risk import RiskAlert, RiskScore

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════
# LOT A — Scoping Agent endpoints
# ════════════════════════════════════════════════════════════════════
scoping_router = APIRouter()


@scoping_router.post("/invoke", response_model=PlanGenerationResponse)
async def invoke_scoping_agent(request: PlanGenerationRequest) -> PlanGenerationResponse:
    """Génère un plan depuis un brief projet.

    Body: PlanGenerationRequest (brief + flags)
    Returns: Plan + métadonnées de génération
    """
    raise HTTPException(status_code=501, detail="Scoping Agent : à implémenter (Lot A)")


# ════════════════════════════════════════════════════════════════════
# LOT B — Ops Agent + ActionGuard endpoints
# ════════════════════════════════════════════════════════════════════
ops_router = APIRouter()


@ops_router.post("/execute")
async def execute_plan(plan_id: UUID) -> dict:
    """Exécute un plan approuvé. Chaque action passe par ActionGuard."""
    raise HTTPException(status_code=501, detail="Ops Agent : à implémenter (Lot B)")


@ops_router.post("/review/{decision_id}")
async def submit_review(
    decision_id: UUID, approved: bool, reviewer_id: str, reason: str = ""
) -> dict:
    """Soumet une revue humaine sur une décision ActionGuard en attente."""
    raise HTTPException(status_code=501, detail="À implémenter (Lot B)")


# ════════════════════════════════════════════════════════════════════
# LOT A — Risk Agent endpoints
# ════════════════════════════════════════════════════════════════════
risk_router = APIRouter()


@risk_router.get("/issues/{issue_key}", response_model=RiskScore)
async def get_latest_risk(issue_key: str) -> RiskScore:
    """Dernier RiskScore pour une issue Jira."""
    raise HTTPException(status_code=501, detail="Risk Agent : à implémenter (Lot A)")


@risk_router.get("/alerts", response_model=list[RiskAlert])
async def list_active_alerts() -> list[RiskAlert]:
    """Liste des alertes de risque actives (non encore acquittées)."""
    raise HTTPException(status_code=501, detail="Risk Agent : à implémenter (Lot A)")


# ════════════════════════════════════════════════════════════════════
# LOT B — Audit endpoints
# ════════════════════════════════════════════════════════════════════
audit_router = APIRouter()


@audit_router.get("/recent", response_model=list[AuditLogEntry])
async def get_recent_audit(limit: int = 100) -> list[AuditLogEntry]:
    """Dernières entrées du journal d'audit (lecture seule)."""
    raise HTTPException(status_code=501, detail="À implémenter (Lot B)")
