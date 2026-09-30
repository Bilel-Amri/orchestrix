"""Modèles SQLAlchemy pour la persistance.

Tables principales :
  - plans / epics / tasks      (Lot A — sortie Scoping Agent)
  - jira_actions_log            (Lot B — journal append-only ActionGuard)
  - risk_scores                 (Lot A — output Risk Agent)
  - benchmark_results           (commun — résultats d'évaluation)
  - team_profiles               (Lot B — synthetic team data)
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from orchestrix.db import Base


class PlanORM(Base):
    __tablename__ = "plans"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    brief: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    prompt_version: Mapped[str] = mapped_column(String(64), default="v1")
    llm_model: Mapped[str] = mapped_column(String(128))

    epics: Mapped[list[EpicORM]] = relationship(back_populates="plan", cascade="all, delete-orphan")


class EpicORM(Base):
    __tablename__ = "epics"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("plans.id"))
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    plan: Mapped[PlanORM] = relationship(back_populates="epics")
    tasks: Mapped[list[TaskORM]] = relationship(back_populates="epic", cascade="all, delete-orphan")


class TaskORM(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    epic_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("epics.id"))
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    priority: Mapped[str | None] = mapped_column(String(16), nullable=True)
    complexity: Mapped[str | None] = mapped_column(String(16), nullable=True)
    required_skills: Mapped[list] = mapped_column(JSON, default=list)
    dependencies: Mapped[list] = mapped_column(JSON, default=list)

    epic: Mapped[EpicORM] = relationship(back_populates="tasks")


class JiraActionAuditORM(Base):
    """Journal append-only — toute action Jira évaluée par ActionGuard."""

    __tablename__ = "jira_action_audit"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    actor_type: Mapped[str] = mapped_column(String(32))
    actor_id: Mapped[str] = mapped_column(String(128))
    action_type: Mapped[str] = mapped_column(String(64), index=True)
    project_key: Mapped[str] = mapped_column(String(32), index=True)
    target_resource: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    params: Mapped[dict] = mapped_column(JSON, default=dict)

    verdict: Mapped[str] = mapped_column(String(16), index=True)
    rule_applied: Mapped[str] = mapped_column(String(128))
    reason: Mapped[str] = mapped_column(Text)
    residual_risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    plan_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True, index=True
    )


class RiskScoreORM(Base):
    __tablename__ = "risk_scores"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    issue_key: Mapped[str] = mapped_column(String(64), index=True)
    project_key: Mapped[str] = mapped_column(String(32), index=True)
    risk_score: Mapped[float] = mapped_column(Float)
    predicted_prolonged: Mapped[bool] = mapped_column(Boolean)
    contributing_factors: Mapped[list] = mapped_column(JSON, default=list)
    model_id: Mapped[str] = mapped_column(String(128))
    model_version: Mapped[str] = mapped_column(String(64))
    features_snapshot_at: Mapped[datetime] = mapped_column(DateTime)


class BenchmarkResultORM(Base):
    """Résultat d'un run d'évaluation (RQ1-RQ4)."""

    __tablename__ = "benchmark_results"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    run_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    condition: Mapped[str] = mapped_column(String(8))  # 'A', 'B', 'C', 'D', 'E' ou 'baseline'
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    sample_count: Mapped[int] = mapped_column(Integer)


class TeamProfileORM(Base):
    """Profils d'équipe synthétiques (3-4 profils fictifs documentés)."""

    __tablename__ = "team_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(64))
    skills: Mapped[list] = mapped_column(JSON, default=list)
    weekly_capacity_hours: Mapped[int] = mapped_column(Integer, default=40)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)


class EvidenceORM(Base):
    """Preuve RAG indexée (pour hybrid retrieval avec metadata source/type)."""

    __tablename__ = "evidence"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source: Mapped[str] = mapped_column(
        String(32), index=True
    )  # 'josse' | 'itemlet' | 'public_jira' | 'policy'
    type: Mapped[str] = mapped_column(
        String(32), index=True
    )  # 'task' | 'issue_metadata' | 'dependency' | 'comment' | 'policy'
    content: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    embedding = mapped_column(Vector(384))  # dimension de all-MiniLM-L6-v2
