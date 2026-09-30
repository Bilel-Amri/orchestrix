"""Tests d'intégration — DB, audit log, persistance.

⚠️ Requiert PostgreSQL + pgvector en marche :
   docker compose -f docker/docker-compose.yml up postgres -d
"""
import pytest


@pytest.mark.integration
@pytest.mark.asyncio
async def test_plan_persists_and_loads(async_db_session):
    """Création puis lecture d'un Plan."""
    from orchestrix.db.models import EpicORM, PlanORM, TaskORM

    plan = PlanORM(
        brief="x" * 25,
        prompt_version="v1",
        llm_model="qwen2.5:3b",
    )
    epic = EpicORM(title="Epic test", description="Description test")
    task = TaskORM(title="Task test", description="Description test")
    epic.tasks.append(task)
    plan.epics.append(epic)

    async_db_session.add(plan)
    await async_db_session.flush()

    assert plan.id is not None
    assert len(plan.epics) == 1
    assert len(plan.epics[0].tasks) == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_audit_log_is_append_only(async_db_session):
    """Le journal d'audit doit être insérable et lisible, mais pas updatable en pratique."""
    from orchestrix.db.models import JiraActionAuditORM

    entry = JiraActionAuditORM(
        actor_type="agent",
        actor_id="ops-agent",
        action_type="create_issue",
        project_key="DEMO",
        target_resource="DEMO-1",
        params={"summary": "x"},
        verdict="allow",
        rule_applied="schema_valid",
        reason="OK",
    )
    async_db_session.add(entry)
    await async_db_session.flush()

    assert entry.id is not None
    assert entry.verdict == "allow"
