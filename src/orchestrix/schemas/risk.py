"""Schemas pour le Risk Agent (Lot A — surveillance continue)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class RiskScore(BaseModel):
    """Score de risque produit par le Risk Agent pour une issue Jira."""

    id: UUID = Field(default_factory=uuid4)
    computed_at: datetime = Field(default_factory=datetime.utcnow)

    issue_key: str = Field(..., description="ex: 'PROJ-123'")
    project_key: str

    # Cible de prédiction : y = 1 si l'issue dépasse un seuil de résolution prolongée
    risk_score: float = Field(..., ge=0, le=1, description="Probabilité de résolution prolongée")
    predicted_prolonged: bool

    # Explicabilité
    contributing_factors: list[dict] = Field(
        default_factory=list,
        description="Top features contribuant au score (SHAP-like)",
    )
    model_id: str
    model_version: str

    # À partir du moment de prédiction t — pas de fuite temporelle
    features_snapshot_at: datetime = Field(
        ...,
        description="Instant t des features utilisées (jamais après)",
    )


class RiskAlert(BaseModel):
    """Alerte envoyée au chef de projet quand un score dépasse un seuil."""

    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    issue_key: str
    project_key: str
    risk_score: float
    severity: str = Field(..., description="'low' | 'medium' | 'high' | 'critical'")
    message: str
    recommended_action: str | None = None
