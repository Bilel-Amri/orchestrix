"""Jira Mock Executor — pour benchmark dry-run (Lot B).

⚠️ Utilisé UNIQUEMENT pour la suite d'évaluation safe/unsafe (section 10).
   Aucune action de benchmark ne doit s'exécuter contre le vrai Jira.

Le mock partage l'interface de JiraClient mais opère sur un état
synthétique en mémoire (Dict[issue_key, issue_state]).

Garanties :
  - Aucun appel réseau, aucun credential requis (mock pur)
  - Clés monotones PAR projet (DEMO-1, DEMO-2, ... ) — pas de réutilisation
    après un delete (comportement plus proche du vrai Jira)
  - JQL supporté en mode "lite" : filtres `project = KEY` et `labels = "..."`
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

_KEY_RE = re.compile(r"^([A-Z][A-Z0-9]*)-(\d+)$")


@dataclass
class MockIssueState:
    """État synthétique d'une issue Jira pour le benchmark."""

    issue_key: str
    project_key: str
    summary: str
    description: str
    issue_type: str = "Task"
    status: str = "To Do"
    assignee: str | None = None
    estimated_hours: float | None = None
    labels: list = field(default_factory=list)
    comments: list = field(default_factory=list)
    epic_key: str | None = None


class JiraMockExecutor:
    """Mock executor pour le benchmark safe/unsafe — état en mémoire.

    Interface alignée sur JiraClient : create_epic, create_issue,
    assign_issue, transition_issue, add_comment, delete_issue,
    get_issue, search_issues, create_sprint.
    """

    def __init__(self) -> None:
        self._issues: dict[str, MockIssueState] = {}
        self._sprints: dict[int, dict] = {}
        self._counters: dict[str, int] = {}  # clé = project_key, jamais décrémentée
        self._next_sprint_id = 1

    # ── Helpers internes ──────────────────────────────────────────

    def _next_key(self, project_key: str) -> str:
        n = self._counters.get(project_key, 0) + 1
        self._counters[project_key] = n
        return f"{project_key}-{n}"

    def _register(self, issue: MockIssueState) -> dict[str, str]:
        self._issues[issue.issue_key] = issue
        return {"key": issue.issue_key, "id": issue.issue_key}

    @staticmethod
    def _parse_key(issue_key: str) -> tuple[str, int]:
        m = _KEY_RE.match(issue_key)
        if not m:
            raise ValueError(f"Clé Jira invalide : {issue_key!r}")
        return m.group(1), int(m.group(2))

    # ── Création ─────────────────────────────────────────────────

    def create_epic(
        self, project_key: str, summary: str, description: str, labels: list | None = None
    ) -> dict:
        issue = MockIssueState(
            issue_key=self._next_key(project_key),
            project_key=project_key,
            summary=summary,
            description=description,
            issue_type="Epic",
            labels=list(labels or []),
        )
        return self._register(issue)

    def create_issue(
        self,
        project_key: str,
        summary: str,
        description: str,
        issue_type: str = "Task",
        epic_key: str | None = None,
        story_points: float | None = None,
        labels: list | None = None,
    ) -> dict:
        issue = MockIssueState(
            issue_key=self._next_key(project_key),
            project_key=project_key,
            summary=summary,
            description=description,
            issue_type=issue_type,
            estimated_hours=story_points,
            labels=list(labels or []),
            epic_key=epic_key,
        )
        return self._register(issue)

    def create_sprint(
        self,
        board_id: int,
        name: str,
        start_date: str | None = None,
        end_date: str | None = None,
        goal: str | None = None,
    ) -> dict:
        sprint_id = self._next_sprint_id
        self._next_sprint_id += 1
        self._sprints[sprint_id] = {
            "id": sprint_id,
            "board_id": board_id,
            "name": name,
            "start_date": start_date,
            "end_date": end_date,
            "goal": goal,
            "state": "future",
        }
        return {"id": sprint_id, "name": name}

    # ── Mutation ─────────────────────────────────────────────────

    def _get_or_fail(self, issue_key: str) -> MockIssueState:
        issue = self._issues.get(issue_key)
        if issue is None:
            raise KeyError(f"Issue inconnue : {issue_key}")
        return issue

    def assign_issue(self, issue_key: str, assignee: str) -> dict:
        self._get_or_fail(issue_key).assignee = assignee
        return {"key": issue_key, "assignee": assignee}

    def transition_issue(self, issue_key: str, transition_name: str) -> dict:
        self._get_or_fail(issue_key).status = transition_name
        return {"key": issue_key, "status": transition_name}

    def add_comment(self, issue_key: str, body: str) -> dict:
        issue = self._get_or_fail(issue_key)
        issue.comments.append({"author": "mock", "body": body})
        return {"key": issue_key, "id": f"comment-{len(issue.comments)}"}

    def delete_issue(self, issue_key: str) -> None:
        self._get_or_fail(issue_key)
        del self._issues[issue_key]

    # ── Lecture ──────────────────────────────────────────────────

    def get_issue(self, issue_key: str) -> dict[str, Any]:
        issue = self._get_or_fail(issue_key)
        return {
            "key": issue.issue_key,
            "fields": {
                "summary": issue.summary,
                "description": issue.description,
                "issuetype": {"name": issue.issue_type},
                "status": {"name": issue.status},
                "assignee": {"account_id": issue.assignee} if issue.assignee else None,
                "labels": list(issue.labels),
                "parent": {"key": issue.epic_key} if issue.epic_key else None,
            },
        }

    def search_issues(self, jql: str, max_results: int = 50) -> list[dict[str, Any]]:
        """JQL-lite : `project = KEY`, `labels = "x"`, combinés par AND."""
        project_match = re.search(r"project\s*=\s*([A-Z][A-Z0-9]*)", jql)
        label_match = re.search(r'labels\s*=\s*"([^"]+)"', jql)
        results = []
        for issue in self._issues.values():
            if project_match and issue.project_key != project_match.group(1):
                continue
            if label_match and label_match.group(1) not in issue.labels:
                continue
            results.append({"key": issue.issue_key})
            if len(results) >= max_results:
                break
        return results

    # ── Inspection pour le benchmark ─────────────────────────────

    def get_state_snapshot(self) -> dict:
        """Retourne l'état complet pour analyse post-benchmark."""
        return {k: vars(v) for k, v in self._issues.items()}

    def get_action_log(self) -> list[dict]:
        """Journal des actions simulées (pour rejouer les unsafe actions)."""
        return [vars(s) for s in self._sprints.values()]  # placeholder, étendu au besoin

    def reset(self) -> None:
        """Reset pour nouveau scénario. Les compteurs de clés sont conservés."""
        self._issues.clear()
        self._sprints.clear()
