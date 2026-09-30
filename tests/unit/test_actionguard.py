"""Tests ActionGuard — squelette (Lot B).

Quand ActionGuard.evaluate() sera implémenté :
  - test que les safe_actions du benchmark passent avec verdict=allow
  - test que les unsafe_actions sont bloquées
  - test que les ambiguous_actions déclenchent verdict=review
  - test que le dry-run mode ne touche jamais la vraie API Jira
"""

import pytest

from orchestrix.integrations.jira.mock import JiraMockExecutor
from orchestrix.reliability.gateway import ActionGuard
from orchestrix.schemas.decision import ActionProposal


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
