"""Schemas liés aux décisions ActionGuard (Lot B — Reliability Gateway)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

DecisionVerdict = Literal["allow", "review", "block"]


class ActionProposal(BaseModel):
    """Action Jira proposée par l'Ops Agent que ActionGuard doit évaluer."""

    id: UUID = Field(default_factory=uuid4)
    proposed_at: datetime = Field(default_factory=datetime.utcnow)
    proposed_by: str = Field(..., description="Identifiant de l'agent émetteur")

    # Catégorisation de l'action
    action_type: Literal[
        "create_epic",
        "create_issue",
        "create_sprint",
        "assign_issue",
        "transition_issue",
        "add_comment",
        "update_field",
    ]
    project_key: str = Field(..., description="Clé du projet Jira cible")

    # Paramètres spécifiques à l'action
    params: dict = Field(
        default_factory=dict,
        description="Paramètres structurés de l'action (champs Jira)",
    )

    # Métadonnées d'intention
    rationale: str = Field("", description="Pourquoi l'agent propose cette action")
    linked_plan_id: UUID | None = None
    linked_task_id: UUID | None = None

    # Identité applicative (pas Jira natif)
    user_id: str = Field(..., description="ID utilisateur dans notre système RBAC")
    user_role: str = Field(..., description="Rôle applicatif de l'utilisateur")


class ActionDecision(BaseModel):
    """Décision rendue par ActionGuard."""

    proposal_id: UUID
    decided_at: datetime = Field(default_factory=datetime.utcnow)

    verdict: DecisionVerdict
    reason: str = Field(..., description="Justification de la décision (auditable)")
    rule_applied: str = Field(..., description="Identifiant de la règle ActionGuard déclenchée")

    # Si verdict=review, indique qui doit reviewer
    human_reviewer_required: bool = False
    human_reviewer_role: str | None = None

    # Si ML résiduel activé (option avancée), score de risque
    residual_risk_score: float | None = Field(
        None, ge=0, le=1, description="Score ML de risque résiduel"
    )
