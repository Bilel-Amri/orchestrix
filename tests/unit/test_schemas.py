"""Tests unitaires des schemas Pydantic (interfaces stables)."""

import pytest
from pydantic import ValidationError

from orchestrix.schemas.plan import (
    EffortEstimate,
    Plan,
    PlanGenerationRequest,
    PriorityComplexity,
    Task,
)


class TestPlanGenerationRequest:
    def test_minimal_valid(self):
        req = PlanGenerationRequest(brief="x" * 25)
        assert req.brief is not None
        assert req.include_rag is True

    def test_brief_too_short_raises(self):
        with pytest.raises(ValidationError):
            PlanGenerationRequest(brief="too short")

    def test_defaults(self):
        req = PlanGenerationRequest(brief="x" * 25)
        assert req.include_estimated_effort is True
        assert req.include_prioritization is True
        assert req.llm_provider_override is None


class TestEffortEstimate:
    def test_valid(self):
        e = EffortEstimate(hours=8.0, confidence=0.85, model_id="effort-v1", model_version="1.0")
        assert e.hours == 8.0
        assert e.confidence == 0.85

    def test_negative_hours_rejected(self):
        with pytest.raises(ValidationError):
            EffortEstimate(hours=-1, confidence=0.5, model_id="x", model_version="1")

    def test_confidence_clamped(self):
        with pytest.raises(ValidationError):
            EffortEstimate(hours=5, confidence=2.0, model_id="x", model_version="1")


class TestPriorityComplexity:
    @pytest.mark.parametrize(
        "priority",
        ["low", "medium", "high", "critical"],
    )
    def test_valid_priorities(self, priority):
        pc = PriorityComplexity(
            priority=priority,
            complexity="moderate",
            priority_score=0.5,
            complexity_score=0.5,
            model_id="prio-v1",
            model_version="1",
        )
        assert pc.priority == priority

    def test_invalid_priority_rejected(self):
        with pytest.raises(ValidationError):
            PriorityComplexity(
                priority="urgent",  # not in literal
                complexity="moderate",
                priority_score=0.5,
                complexity_score=0.5,
                model_id="x",
                model_version="1",
            )


class TestTask:
    def test_minimal_task(self):
        t = Task(title="Setup repo", description="Initialize git and CI")
        assert t.id is not None
        assert t.dependencies == []
        assert t.effort_estimate is None
        assert t.supporting_evidence_ids == []

    def test_with_annotations(self):
        t = Task(
            title="Setup repo",
            description="Initialize git and CI",
            effort_estimate=EffortEstimate(
                hours=4, confidence=0.9, model_id="effort", model_version="1"
            ),
        )
        assert t.effort_estimate.hours == 4


class TestPlan:
    def test_empty_plan(self):
        p = Plan(brief="x" * 25)
        assert p.epics == []
        assert p.status == "draft"
        assert p.all_tasks == []

    def test_all_tasks_flatten(self):
        p = Plan(
            brief="x" * 25,
            epics=[
                {
                    "title": "Epic 1",
                    "description": "First epic description",
                    "tasks": [
                        {"title": "Task 1", "description": "First task description"},
                        {"title": "Task 2", "description": "Second task description"},
                    ],
                },
                {
                    "title": "Epic 2",
                    "description": "Second epic description",
                    "tasks": [
                        {"title": "Task 3", "description": "Third task description"},
                    ],
                },
            ],
        )
        assert len(p.all_tasks) == 3
