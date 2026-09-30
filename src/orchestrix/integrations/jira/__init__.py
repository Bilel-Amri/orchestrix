"""Jira Cloud integration — Lot B.

⚠️ Utiliser UNIQUEMENT via ActionGuard.evaluate() — pas d'appel direct.

En environnement de benchmark (dry-run), c'est JiraMockExecutor qui est utilisé.
"""

from orchestrix.integrations.jira.client import JiraClient
from orchestrix.integrations.jira.mock import JiraMockExecutor

__all__ = ["JiraClient", "JiraMockExecutor"]
