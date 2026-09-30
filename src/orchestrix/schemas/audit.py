"""Schemas pour le journal d'audit (Lot B — append-only PostgreSQL)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class AuditLogEntry(BaseModel):
    """Une entrée du journal d'audit (immutable)."""

    id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Acteur
    actor_type: str = Field(..., description="'agent', 'human', 'system'")
    actor_id: str = Field(..., description="Identifiant de l'acteur")

    # Action
    action_type: str
    target_resource: str = Field(..., description="ex: 'PROJ-123' pour une issue Jira")
    params: dict[str, Any] = Field(default_factory=dict)

    # Décision ActionGuard
    verdict: str | None = None
    rule_applied: str | None = None
    reason: str | None = None

    # Trace complète pour reproduction
    trace_id: str | None = None
    plan_id: UUID | None = None
