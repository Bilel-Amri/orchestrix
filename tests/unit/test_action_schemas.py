"""Tests des schémas de params par action Jira (règle 1 — Schema).

Les cas valides sont tirés du benchmark `safe_unsafe_actions.json` ;
les cas invalides prouvent que le schéma rejette tôt (fail-closed).
"""

import pytest
from pydantic import ValidationError

from orchestrix.schemas.actions import (
    AddCommentParams,
    AssignIssueParams,
    CreateEpicParams,
    CreateIssueParams,
    CreateSprintParams,
    TransitionIssueParams,
    UpdateFieldParams,
)


class TestCreateIssueParams:
    def test_safe_001_valid(self):
        p = CreateIssueParams(
            summary="Bug : bouton paiement Safari 17",
            description="Reproduction : Safari 17.4, mobile.",
            issue_type="Bug",
            labels=["bug", "frontend"],
        )
        assert p.issue_type == "Bug"
        assert p.labels == ["bug", "frontend"]

    def test_minimal_defaults(self):
        p = CreateIssueParams(summary="New", description="Desc")
        assert p.issue_type == "Task"
        assert p.epic_key is None
        assert p.labels == []
        assert p.story_points is None

    def test_missing_summary_rejected(self):
        with pytest.raises(ValidationError):
            CreateIssueParams(description="Desc")

    def test_blank_summary_rejected(self):
        with pytest.raises(ValidationError):
            CreateIssueParams(summary="   ", description="Desc")

    def test_invalid_epic_key_rejected(self):
        with pytest.raises(ValidationError):
            CreateIssueParams(summary="S", description="D", epic_key="not-a-key")

    def test_negative_story_points_rejected(self):
        with pytest.raises(ValidationError):
            CreateIssueParams(summary="S", description="D", story_points=-1)

    def test_unknown_field_rejected(self):
        with pytest.raises(ValidationError):
            CreateIssueParams(summary="S", description="D", priority="critical")


class TestCreateEpicParams:
    def test_valid(self):
        p = CreateEpicParams(summary="Epic 1", description="Description longue")
        assert p.labels == []

    def test_missing_description_rejected(self):
        with pytest.raises(ValidationError):
            CreateEpicParams(summary="Epic 1")


class TestCreateSprintParams:
    def test_safe_003_valid(self):
        p = CreateSprintParams(
            board_id=1,
            name="Sprint 14 — Q4 2025",
            start_date="2025-10-01",
            end_date="2025-10-14",
            goal="Livrer la feature de paiement",
        )
        assert p.start_date < p.end_date

    def test_unsafe_006_inverted_dates_rejected(self):
        with pytest.raises(ValidationError):
            CreateSprintParams(
                board_id=1,
                name="Sprint impossible",
                start_date="2025-12-31",
                end_date="2025-10-01",
            )

    def test_equal_dates_rejected(self):
        with pytest.raises(ValidationError):
            CreateSprintParams(board_id=1, name="S", start_date="2025-10-01", end_date="2025-10-01")

    def test_non_positive_board_id_rejected(self):
        with pytest.raises(ValidationError):
            CreateSprintParams(board_id=0, name="S", start_date="2025-10-01", end_date="2025-10-14")


class TestAssignIssueParams:
    def test_safe_002_valid(self):
        p = AssignIssueParams(issue_key="DEMO-42", assignee="alice@team.com", estimated_hours=5)
        assert p.estimated_hours == 5

    def test_unsafe_002_heavy_load_is_schema_valid(self):
        # 60h n'est PAS une erreur de schéma : c'est la règle 4 (charge) qui bloque.
        p = AssignIssueParams(issue_key="DEMO-100", assignee="bob@team.com", estimated_hours=60)
        assert p.estimated_hours == 60

    def test_invalid_issue_key_rejected(self):
        with pytest.raises(ValidationError):
            AssignIssueParams(issue_key="demo-42", assignee="alice@team.com")

    def test_negative_hours_rejected(self):
        with pytest.raises(ValidationError):
            AssignIssueParams(issue_key="DEMO-42", assignee="a@b.com", estimated_hours=-1)


class TestTransitionIssueParams:
    def test_valid(self):
        p = TransitionIssueParams(issue_key="DEMO-10", transition="In Progress")
        assert p.transition == "In Progress"

    def test_missing_transition_rejected(self):
        with pytest.raises(ValidationError):
            TransitionIssueParams(issue_key="DEMO-10")


class TestAddCommentParams:
    def test_valid(self):
        p = AddCommentParams(issue_key="DEMO-1", body="premier")
        assert p.body == "premier"

    def test_empty_body_rejected(self):
        with pytest.raises(ValidationError):
            AddCommentParams(issue_key="DEMO-1", body="")


class TestUpdateFieldParams:
    def test_valid(self):
        p = UpdateFieldParams(issue_key="DEMO-999", field="resolution", value="Won't Fix")
        assert p.value == "Won't Fix"

    def test_missing_field_rejected(self):
        with pytest.raises(ValidationError):
            UpdateFieldParams(issue_key="DEMO-999", value="x")
