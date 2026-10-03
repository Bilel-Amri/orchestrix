"""Tests ActionGuard — squelette (Lot B).

Quand ActionGuard.evaluate() sera implémenté :
  - test que les safe_actions du benchmark passent avec verdict=allow
  - test que les unsafe_actions sont bloquées
  - test que les ambiguous_actions déclenchent verdict=review
  - test que le dry-run mode ne touche jamais la vraie API Jira
"""

from typing import get_args

import pytest

from orchestrix.integrations.jira.mock import JiraMockExecutor
from orchestrix.reliability.gateway import SCHEMA_MAP, ActionGuard
from orchestrix.schemas.actions import (
    AddCommentParams,
    AssignIssueParams,
    CreateEpicParams,
    CreateIssueParams,
    CreateSprintParams,
    TransitionIssueParams,
    UpdateFieldParams,
)
from orchestrix.schemas.decision import ActionProposal


def _proposal(action_type: str, params: dict) -> ActionProposal:
    """Construit une proposition valide au niveau enveloppe."""
    return ActionProposal(
        proposed_by="ops-agent",
        action_type=action_type,
        project_key="DEMO",
        params=params,
        user_id="alice",
        user_role="developer",
    )


class TestJiraMockExecutor:
    """Le mock doit être stable avant même qu'ActionGuard soit implémenté."""

    def test_create_issue_increments_key(self):
        mock = JiraMockExecutor()
        r1 = mock.create_issue("DEMO", "Issue 1", "Description 1")
        r2 = mock.create_issue("DEMO", "Issue 2", "Description 2")
        assert r1["key"] != r2["key"]
        assert r1["key"].startswith("DEMO-")
        assert r2["key"].startswith("DEMO-")

    def test_assign_issue_updates_state(self):
        mock = JiraMockExecutor()
        mock.create_issue("DEMO", "Test", "Test")
        # Get the created key
        state = mock.get_state_snapshot()
        issue_key = list(state.keys())[0]
        mock.assign_issue(issue_key, "alice@team.com")
        assert mock.get_state_snapshot()[issue_key]["assignee"] == "alice@team.com"

    def test_reset_clears_state(self):
        mock = JiraMockExecutor()
        mock.create_issue("DEMO", "Test", "Test")
        assert len(mock.get_state_snapshot()) > 0
        mock.reset()
        assert mock.get_state_snapshot() == {}

    def test_no_real_jira_call(self):
        """Vérifier qu'aucun appel réseau n'est fait — c'est un mock pur."""
        mock = JiraMockExecutor()
        # Si on a une exception de type 'no JiraClient initialized', c'est correct
        # Le mock ne devrait JAMAIS avoir besoin de credentials
        try:
            mock.create_issue("ANY", "x", "x")  # n'importe quelle clé
        except Exception as e:
            pytest.fail(f"Mock should not require credentials, got: {e}")

    def test_keys_monotonic_per_project_and_no_reuse_after_delete(self):
        """Clés monotones par projet — un delete ne réutilise jamais une clé."""
        mock = JiraMockExecutor()
        a1 = mock.create_issue("AAA", "a1", "d")["key"]
        b1 = mock.create_issue("BBB", "b1", "d")["key"]
        a2 = mock.create_issue("AAA", "a2", "d")["key"]
        assert (a1, a2, b1) == ("AAA-1", "AAA-2", "BBB-1")
        mock.delete_issue(a2)
        a3 = mock.create_issue("AAA", "a3", "d")["key"]
        assert a3 == "AAA-3"  # AAA-2 n'est pas recyclée

    def test_transition_and_get_issue_roundtrip(self):
        mock = JiraMockExecutor()
        key = mock.create_issue("DEMO", "T", "Desc")["key"]
        mock.transition_issue(key, "In Progress")
        fields = mock.get_issue(key)["fields"]
        assert fields["status"]["name"] == "In Progress"

    def test_add_comment_appends(self):
        mock = JiraMockExecutor()
        key = mock.create_issue("DEMO", "T", "Desc")["key"]
        mock.add_comment(key, "première")
        mock.add_comment(key, "deuxième")
        state = mock.get_state_snapshot()[key]
        assert [c["body"] for c in state["comments"]] == ["première", "deuxième"]

    def test_get_issue_shape_with_epic_and_labels(self):
        mock = JiraMockExecutor()
        epic = mock.create_epic("DEMO", "E1", "Epic desc", labels=["plan"])
        task = mock.create_issue("DEMO", "T1", "Task desc", epic_key=epic["key"], labels=["plan"])
        fields = mock.get_issue(task["key"])["fields"]
        assert fields["parent"] == {"key": epic["key"]}
        assert fields["labels"] == ["plan"]
        assert fields["issuetype"]["name"] == "Epic" or fields["issuetype"]["name"] == "Task"

    def test_search_issues_filters_by_project_and_label(self):
        mock = JiraMockExecutor()
        mock.create_issue("DEMO", "in", "d", labels=["plan"])
        mock.create_issue("OTHER", "out", "d", labels=["plan"])
        mock.create_issue("DEMO", "nolabel", "d", labels=[])
        res = mock.search_issues('project = DEMO AND labels = "plan"')
        keys = [r["key"] for r in res]
        assert len(keys) == 1
        assert mock.get_issue(keys[0])["fields"]["summary"] == "in"

    def test_unknown_issue_raises_keyerror(self):
        mock = JiraMockExecutor()
        with pytest.raises(KeyError):
            mock.get_issue("DEMO-999")
        with pytest.raises(KeyError):
            mock.transition_issue("NOPE-1", "Done")

    def test_create_sprint_ids_unique(self):
        mock = JiraMockExecutor()
        s1 = mock.create_sprint(1, "Sprint 1")
        s2 = mock.create_sprint(1, "Sprint 2")
        assert s1["id"] != s2["id"]


class TestSchemaMap:
    """La table de routage doit couvrir exactement les 7 action_type du Literal."""

    def test_maps_each_action_type_to_its_schema(self):
        assert SCHEMA_MAP == {
            "create_epic": CreateEpicParams,
            "create_issue": CreateIssueParams,
            "create_sprint": CreateSprintParams,
            "assign_issue": AssignIssueParams,
            "transition_issue": TransitionIssueParams,
            "add_comment": AddCommentParams,
            "update_field": UpdateFieldParams,
        }

    def test_covers_every_action_type_of_the_proposal_literal(self):
        declared = set(get_args(ActionProposal.model_fields["action_type"].annotation))
        assert set(SCHEMA_MAP) == declared


class TestCheckSchema:
    """Règle 1 — validation des params contre la grammaire de l'action."""

    def test_valid_create_issue_passes(self):
        ok, reason = ActionGuard()._check_schema(
            _proposal(
                "create_issue",
                {
                    "summary": "Bug paiement Safari",
                    "description": "Repro 17.4",
                    "issue_type": "Bug",
                },
            )
        )
        assert ok is True
        assert reason == ""

    def test_invalid_create_issue_params_fails(self):
        ok, reason = ActionGuard()._check_schema(
            _proposal("create_issue", {"description": "il manque summary"})
        )
        assert ok is False
        assert "create_issue" in reason
        assert "summary" in reason

    def test_unknown_extra_field_fails(self):
        ok, reason = ActionGuard()._check_schema(
            _proposal(
                "create_issue",
                {"summary": "S", "description": "D", "priority": "critical"},
            )
        )
        assert ok is False
        assert "priority" in reason

    def test_unknown_action_type_fails(self):
        # ActionProposal.action_type est un Literal : on contourne l'enveloppe
        # pour vérifier que la règle elle-même est fail-closed.
        proposal = _proposal("create_issue", {"summary": "S", "description": "D"})
        object.__setattr__(proposal, "action_type", "delete_project")

        ok, reason = ActionGuard()._check_schema(proposal)
        assert ok is False
        assert "delete_project" in reason

    @pytest.mark.parametrize(
        ("action_type", "params"),
        [
            ("create_epic", {"summary": "Epic 1", "description": "Desc"}),
            (
                "create_sprint",
                {
                    "board_id": 1,
                    "name": "Sprint 14",
                    "start_date": "2025-10-01",
                    "end_date": "2025-10-14",
                },
            ),
            ("assign_issue", {"issue_key": "DEMO-1", "assignee": "alice@team.com"}),
            ("transition_issue", {"issue_key": "DEMO-1", "transition": "In Progress"}),
            ("add_comment", {"issue_key": "DEMO-1", "body": "vu"}),
            ("update_field", {"issue_key": "DEMO-1", "field": "summary", "value": "x"}),
        ],
    )
    def test_each_action_type_valid_params_pass(self, action_type, params):
        ok, reason = ActionGuard()._check_schema(_proposal(action_type, params))
        assert ok is True, reason
        assert reason == ""

    @pytest.mark.parametrize(
        ("action_type", "params", "expected"),
        [
            ("create_epic", {"summary": "Epic 1"}, "description"),
            ("create_sprint", {"board_id": 1, "name": "S", "start_date": "2025-10-01"}, "end_date"),
            ("assign_issue", {"issue_key": "nope", "assignee": "alice"}, "issue_key"),
            ("transition_issue", {"issue_key": "DEMO-1"}, "transition"),
            ("add_comment", {"issue_key": "DEMO-1", "body": "   "}, "body"),
            ("update_field", {"issue_key": "DEMO-1", "field": "summary"}, "value"),
        ],
    )
    def test_each_action_type_invalid_params_fail(self, action_type, params, expected):
        ok, reason = ActionGuard()._check_schema(_proposal(action_type, params))
        assert ok is False
        assert expected in reason

    def test_params_of_another_action_are_not_accepted(self):
        """Un dict valide pour create_issue ne doit pas passer pour add_comment."""
        ok, reason = ActionGuard()._check_schema(
            _proposal("add_comment", {"summary": "S", "description": "D"})
        )
        assert ok is False
        assert "issue_key" in reason

    def test_empty_params_fail_for_action_with_required_fields(self):
        ok, reason = ActionGuard()._check_schema(_proposal("create_issue", {}))
        assert ok is False
        assert reason

    def test_structural_invariant_enforced(self):
        ok, reason = ActionGuard()._check_schema(
            _proposal(
                "create_sprint",
                {
                    "board_id": 1,
                    "name": "Sprint",
                    "start_date": "2025-10-14",
                    "end_date": "2025-10-01",
                },
            )
        )
        assert ok is False
        assert "end_date" in reason

    def test_is_side_effect_free(self):
        """Appeler la règle ne doit rien modifier : ni la proposal, ni self."""
        guard = ActionGuard()
        params = {"summary": "S", "description": "D"}
        proposal = _proposal("create_issue", params)

        before_proposal = proposal.model_dump()
        before_params = dict(params)
        before_state = vars(guard).copy()

        assert guard._check_schema(proposal)[0] is True

        assert proposal.model_dump() == before_proposal
        assert params == before_params
        assert vars(guard) == before_state


@pytest.mark.skip(reason="ActionGuard.evaluate() not implemented yet")
class TestActionGuardSafeActions:
    def test_safe_issue_creation_passes(self):
        guard = ActionGuard()
        proposal = ActionProposal(
            proposed_by="ops-agent",
            action_type="create_issue",
            project_key="DEMO",
            params={"summary": "New", "description": "Desc"},
            user_id="alice",
            user_role="developer",
        )
        decision = guard.evaluate(proposal)  # type: ignore
        assert decision.verdict == "allow"


@pytest.mark.skip(reason="ActionGuard.evaluate() not implemented yet")
class TestActionGuardUnsafeActions:
    def test_duplicate_issue_blocked(self):
        pass

    def test_overloaded_user_blocked(self):
        pass

    def test_prompt_injection_blocked(self):
        pass


class TestCheckRBAC:
    def _proposal(self, action_type, params, role, user="alice"):
        return ActionProposal(
            proposed_by="ops-agent",
            action_type=action_type,
            project_key="DEMO",
            params=params,
            user_id=user,
            user_role=role,
        )

    def test_developer_can_create_issue(self):
        guard = ActionGuard()
        p = self._proposal(
            "create_issue",
            {"summary": "Implement login"},
            "developer",
        )
        allowed, reason = guard._check_rbac(p)
        assert allowed is True
        assert reason == ""

    def test_developer_can_add_comment(self):
        guard = ActionGuard()
        p = self._proposal(
            "add_comment",
            {"issue_key": "DEMO-1", "body": "Done"},
            "developer",
        )
        allowed, reason = guard._check_rbac(p)
        assert allowed is True

    def test_developer_cannot_create_sprint(self):
        guard = ActionGuard()
        p = self._proposal(
            "create_sprint",
            {"board_id": 1, "name": "S1", "start_date": "2026-10-05", "end_date": "2026-10-19"},
            "developer",
        )
        allowed, reason = guard._check_rbac(p)
        assert allowed is False
        assert "non autorisé" in reason

    def test_viewer_cannot_create_issue(self):
        guard = ActionGuard()
        p = self._proposal(
            "create_issue",
            {"summary": "Test"},
            "viewer",
            user="bob",
        )
        allowed, reason = guard._check_rbac(p)
        assert allowed is False
        assert "non autorisé" in reason

    def test_project_manager_can_create_sprint(self):
        guard = ActionGuard()
        p = self._proposal(
            "create_sprint",
            {"board_id": 1, "name": "S1", "start_date": "2026-10-05", "end_date": "2026-10-19"},
            "project_manager",
            user="pm",
        )
        allowed, reason = guard._check_rbac(p)
        assert allowed is True

    def test_unknown_role_is_blocked(self):
        guard = ActionGuard()
        p = self._proposal(
            "create_issue",
            {"summary": "Test"},
            "unknown_role",
            user="eve",
        )
        allowed, reason = guard._check_rbac(p)
        assert allowed is False
        assert "rôle RBAC inconnu" in reason

    def test_unknown_action_is_blocked(self):
        guard = ActionGuard()
        p = self._proposal(
            "create_issue",
            {"summary": "Test"},
            "developer",
        )
        object.__setattr__(p, "action_type", "delete_everything")
        allowed, reason = guard._check_rbac(p)
        assert allowed is False
        assert "action_type inconnu" in reason
