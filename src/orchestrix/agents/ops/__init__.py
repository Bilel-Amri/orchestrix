"""Ops Agent — Lot B.

Traduit un Plan approuvé en appels d'API Jira (create_epic, create_issue,
create_sprint, assign_issue). Chaque appel passe par ActionGuard avant
exécution réelle.
"""

from orchestrix.agents.ops.agent import OpsAgent

__all__ = ["OpsAgent"]
