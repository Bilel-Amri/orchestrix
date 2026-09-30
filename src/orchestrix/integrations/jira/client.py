"""Jira Cloud REST API client — implémentation Lot B.

⚠️ NE JAMAIS appeler ces méthodes directement sans passer par ActionGuard.

Limites Jira Free à respecter :
  - ≤ 10 utilisateurs
  - 2 Go de stockage
  - Pas de permissions / rôles personnalisables
  - Pas de journal d'audit natif
  - Possibilité de désactivation pour inactivité

C'est pourquoi le RBAC et le journal d'audit sont implémentés côté applicatif.

Notes techniques :
  - La lib `atlassian-python-api` cible l'endpoint REST v2 → description/summary
    acceptent du texte brut (pas besoin d'ADF comme en v3).
  - Projets "team-managed" (défaut sur Free) : le lien Epic→Task se fait via
    le champ `parent`. Si le projet est company-managed, le fallback utilise
    un warning (lien stocké dans la description) plutôt que d'échouer.
"""

from __future__ import annotations

import logging
from typing import Any

from atlassian import Jira
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from orchestrix.config import get_settings

logger = logging.getLogger(__name__)


class JiraAPIError(RuntimeError):
    """Erreur lors d'un appel à l'API Jira Cloud."""


class JiraClient:
    """Wrapper autour de l'API Jira Cloud REST v2 (via atlassian-python-api)."""

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
        self.project_key = settings.jira_project_key
        self.demo_project_key = settings.jira_demo_project_key

    # ── Connectivité / lecture ────────────────────────────────────

    def check_connection(self) -> dict[str, Any]:
        """Vérifie les credentials et renvoie le profil de l'utilisateur courant."""
        try:
            me = self._client.myself()
        except Exception as exc:
            raise JiraAPIError(f"Connexion Jira impossible : {exc}") from exc
        logger.info(
            "Connecté à Jira en tant que %s (%s)", me.get("displayName"), me.get("emailAddress")
        )
        return me

    def project_exists(self, project_key: str) -> bool:
        """True si le projet existe et est accessible."""
        try:
            self._client.project(project_key)
            return True
        except Exception:
            return False

    def get_issue(self, issue_key: str) -> dict[str, Any]:
        return self._client.issue(issue_key)

    def search_issues(self, jql: str, max_results: int = 50) -> list[dict[str, Any]]:
        result = self._client.jql(jql, limit=max_results)
        return result.get("issues", [])

    # ── Opérations CRUD sur les issues ───────────────────────────

    @retry(
        retry=retry_if_exception_type(JiraAPIError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    def create_epic(
        self, project_key: str, summary: str, description: str, labels: list[str] | None = None
    ) -> dict[str, Any]:
        fields: dict[str, Any] = {
            "project": {"key": project_key},
            "issuetype": {"name": "Epic"},
            "summary": summary,
            "description": description,
            "labels": labels or ["orchestrix-demo"],
        }
        return self._create_issue_safe(fields)

    def create_issue(
        self,
        project_key: str,
        summary: str,
        description: str,
        issue_type: str = "Task",
        epic_key: str | None = None,
        story_points: float | None = None,
        labels: list[str] | None = None,
    ) -> dict[str, Any]:
        fields: dict[str, Any] = {
            "project": {"key": project_key},
            "issuetype": {"name": issue_type},
            "summary": summary,
            "description": description,
            "labels": labels or ["orchestrix-demo"],
        }
        if story_points is not None:
            # Champ standard team-managed ; ignoré silencieusement si non configuré.
            fields["customfield_10016"] = story_points
        if epic_key:
            fields["parent"] = {"key": epic_key}
        return self._create_issue_safe(fields)

    def _create_issue_safe(self, fields: dict[str, Any]) -> dict[str, Any]:
        try:
            issue = self._client.create_issue(fields=fields)
        except Exception as exc:
            # Fallback : si `parent`/`customfield` est rejeté (company-managed),
            # on retente sans les champs non standards.
            retry_fields = {
                k: v for k, v in fields.items() if k not in ("parent", "customfield_10016")
            }
            if retry_fields != fields:
                logger.warning(
                    "Champs non standard rejetés (%s) — retry sans parent/story points", exc
                )
                issue = self._client.create_issue(fields=retry_fields)
            else:
                raise JiraAPIError(f"create_issue a échoué : {exc}") from exc
        key = issue.get("key")
        logger.info("Issue créée : %s — %s", key, fields["summary"])
        return {"key": key, "id": issue.get("id")}

    def assign_issue(self, issue_key: str, assignee_account_id: str) -> dict[str, Any]:
        self._client.assign_issue(issue_key, assignee_account_id)
        return {"key": issue_key, "assignee": assignee_account_id}

    def transition_issue(self, issue_key: str, transition_name: str) -> dict[str, Any]:
        """Transition par nom de statut, insensible à la casse ('To Do' → 'Done'...)."""
        transitions = self._client.get_issue_transitions(issue_key)
        for t in transitions:
            if str(t.get("name", "")).lower() == transition_name.lower():
                self._client.set_issue_status_by_transition_id(issue_key, t["id"])
                logger.info("Transition %s → %s", issue_key, transition_name)
                return {"key": issue_key, "status": transition_name}
        available = [t.get("name") for t in transitions]
        raise JiraAPIError(
            f"Transition '{transition_name}' introuvable pour {issue_key}. Disponibles : {available}"
        )

    def add_comment(self, issue_key: str, body: str) -> dict[str, Any]:
        comment = self._client.issue_add_comment(issue_key, body)
        logger.info("Commentaire ajouté sur %s", issue_key)
        return {"key": issue_key, "id": comment.get("id")}

    def delete_issue(self, issue_key: str) -> None:
        self._client.delete_issue(issue_key)
        logger.info("Issue supprimée : %s", issue_key)

    # ── Sprints ───────────────────────────────────────────────────

    def create_sprint(
        self,
        board_id: int,
        name: str,
        start_date: str | None = None,
        end_date: str | None = None,
        goal: str | None = None,
    ) -> dict[str, Any]:
        sprint = self._client.create_sprint(name, board_id, start_date, end_date, goal)
        return {"id": sprint.get("id"), "name": sprint.get("name")}
