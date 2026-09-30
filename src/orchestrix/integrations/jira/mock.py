"""Jira Mock Executor — pour benchmark dry-run (Lot B).

⚠️ Utilisé UNIQUEMENT pour la suite d'évaluation safe/unsafe (section 10).
   Aucune action de benchmark ne doit s'exécuter contre le vrai Jira.

Le mock partage l'interface de JiraClient mais opère sur un état
synthétique en mémoire (Dict[issue_key, issue_state]).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class MockIssueState:
    """État synthétique d'une issue Jira pour le benchmark."""

    issue_key: str
    project_key: str
    summary: str
    description: str
    status: str = "To Do"
    assignee: str | None = None
    estimated_hours: float | None = None
    spent_hours: float = 0.0
    labels: list = field(default_factory=list)


class JiraMockExecutor:
    """Mock executor pour le benchmark safe/unsafe — état en mémoire."""

    def __init__(self) -> None:
        self._issues: dict[str, MockIssueState] = {}
        self._sprints: dict[int, dict] = {}
        self._action_log: list[dict] = []  # pour rejouer les unsafe actions

    # ── API compatible avec JiraClient (Lot B alignera les deux) ──

    def create_epic(self, project_key: str, summary: str, description: str) -> dict:
        issue_key = f"{project_key}-{len(self._issues) + 1}"
        self._issues[issue_key] = MockIssueState(
            issue_key=issue_key, project_key=project_key, summary=summary, description=description
        )
        return {"key": issue_key, "id": issue_key}

    def create_issue(
        self, project_key: str, summary: str, description: str, **kwargs
    ) -> dict:
        issue_key = f"{project_key}-{len(self._issues) + 1}"
        self._issues[issue_key] = MockIssueState(
            issue_key=issue_key,
            project_key=project_key,
            summary=summary,
            description=description,
            estimated_hours=kwargs.get("story_points"),
        )
        return {"key": issue_key, "id": issue_key}

    def assign_issue(self, issue_key: str, assignee: str) -> dict:
        if issue_key not in self._issues:
            return {"error": "not_found"}
        self._issues[issue_key].assignee = assignee
        return {"key": issue_key, "assignee": assignee}

    def transition_issue(self, issue_key: str, transition_name: str) -> dict:
        if issue_key not in self._issues:
            return {"error": "not_found"}
        self._issues[issue_key].status = transition_name
        return {"key": issue_key, "status": transition_name}

    # ── Inspection pour le benchmark ──────────────────────────────

    def get_state_snapshot(self) -> dict:
        """Retourne l'état complet pour analyse post-benchmark."""
        return {k: vars(v) for k, v in self._issues.items()}

    def reset(self) -> None:
        """Reset pour nouveau scénario."""
        self._issues.clear()
        self._sprints.clear()
        self._action_log.clear()
