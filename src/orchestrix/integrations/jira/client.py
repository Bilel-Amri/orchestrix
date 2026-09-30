"""Jira Cloud REST API client — squelette (Lot B).

⚠️ NE JAMAIS appeler ces méthodes directement sans passer par ActionGuard.

Limites Jira Free à respecter :
  - ≤ 10 utilisateurs
  - 2 Go de stockage
  - Pas de permissions / rôles personnalisables
  - Pas de journal d'audit natif
  - Possibilité de désactivation pour inactivité

C'est pourquoi le RBAC et le journal d'audit sont implémentés côté applicatif.
"""

from __future__ import annotations

import logging
from typing import Any

from atlassian import Jira

from orchestrix.config import get_settings

logger = logging.getLogger(__name__)


class JiraClient:
    """Wrapper autour de l'API Jira Cloud REST v3."""

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.jira_base_url or not settings.jira_api_token:
            raise ValueError(
                "Jira credentials missing — set JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN in .env"
            )
        self._client = Jira(
            url=settings.jira_base_url,
            username=settings.jira_email,
            password=settings.jira_api_token,
            cloud=True,
        )

    # ── Opérations CRUD sur les issues ───────────────────────────

    def create_epic(self, project_key: str, summary: str, description: str) -> dict[str, Any]:
        raise NotImplementedError

    def create_issue(
        self,
        project_key: str,
        summary: str,
        description: str,
        issue_type: str = "Task",
        epic_key: str | None = None,
        story_points: float | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    def assign_issue(self, issue_key: str, assignee_account_id: str) -> dict[str, Any]:
        raise NotImplementedError

    def transition_issue(self, issue_key: str, transition_name: str) -> dict[str, Any]:
        raise NotImplementedError

    def add_comment(self, issue_key: str, body: str) -> dict[str, Any]:
        raise NotImplementedError

    # ── Sprints ────────────────────────────────────────────────────

    def create_sprint(
        self,
        board_id: int,
        name: str,
        start_date: str | None = None,
        end_date: str | None = None,
        goal: str | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    # ── Lecture ───────────────────────────────────────────────────

    def get_issue(self, issue_key: str) -> dict[str, Any]:
        raise NotImplementedError

    def search_issues(self, jql: str, max_results: int = 50) -> list[dict[str, Any]]:
        raise NotImplementedError
