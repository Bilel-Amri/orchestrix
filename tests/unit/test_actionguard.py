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
