"""Schemas liés à la génération de plans (Lot A — Scoping Agent output)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class EffortEstimate(BaseModel):
    """Sortie du service ML d'estimation d'effort (entraîné sur JOSSE)."""

    hours: float = Field(..., ge=0, le=1000, description="Effort estimé en heures")
    confidence: float = Field(..., ge=0, le=1, description="Confiance du modèle")
    model_id: str = Field(..., description="Référence MLflow du modèle utilisé")
    model_version: str = Field(..., description="Version du modèle")

    @field_validator("confidence")
    @classmethod
    def round_confidence(cls, v: float) -> float:
        return round(v, 3)


class PriorityComplexity(BaseModel):
    """Sortie du service ML de priorisation/complexité (entraîné sur Itemlet)."""

    priority: Literal["low", "medium", "high", "critical"]
    complexity: Literal["trivial", "simple", "moderate", "complex", "epic"]
    priority_score: float = Field(..., ge=0, le=1)
    complexity_score: float = Field(..., ge=0, le=1)
    model_id: str
    model_version: str


class Task(BaseModel):
    """Une tâche dans le plan (output du Scoping Agent)."""

    id: UUID = Field(default_factory=uuid4)
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=10)
    dependencies: list[UUID] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)

    # Annotations ML (remplies par les services, pas par le LLM)
    effort_estimate: EffortEstimate | None = None
    priority_complexity: PriorityComplexity | None = None

    # Traçabilité — pour l'évaluation humaine
    rationale: str = Field(
        "",
        description="Pourquoi cette tâche est dans le plan (ancrée à une preuve ?)",
    )
    supporting_evidence_ids: list[str] = Field(
        default_factory=list,
        description="IDs des preuves RAG qui soutiennent cette tâche",
    )


class Epic(BaseModel):
    """Un regroupement logique de tâches."""

    id: UUID = Field(default_factory=uuid4)
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=10)
    tasks: list[Task] = Field(default_factory=list)


class Plan(BaseModel):
    """Plan complet produit par le Scoping Agent (Lot A output)."""

    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    brief: str = Field(..., description="Description initiale du projet par le chef de projet")
    epics: list[Epic] = Field(default_factory=list)
    status: Literal["draft", "awaiting_review", "approved", "rejected", "executing"] = "draft"

    @property
    def all_tasks(self) -> list[Task]:
        return [task for epic in self.epics for task in epic.tasks]


class PlanGenerationRequest(BaseModel):
    """Input : un brief projet en langage naturel."""

    brief: str = Field(..., min_length=20, description="Description projet en langage naturel")
    include_rag: bool = Field(default=True)
    include_estimated_effort: bool = Field(default=True)
    include_prioritization: bool = Field(default=True)
    llm_provider_override: str | None = None


class PlanGenerationResponse(BaseModel):
    """Output : le plan généré + métadonnées."""

    plan: Plan
    generation_metadata: dict = Field(default_factory=dict)
    retrieved_evidence_count: int = 0
    prompt_version: str
    llm_model: str
