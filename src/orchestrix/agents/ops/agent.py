"""Ops Agent — squelette à implémenter (Lot B).

RÔLE :
    Plan approuvé → pour chaque Task, proposer une ActionProposal Jira
                  → soumettre à ActionGuard → si ALLOW, exécuter via JiraClient

CONTRATS :
    - Entrée : Plan (schemas/plan.py) marqué status="approved"
    - Sortie : itérable de (ActionProposal, ActionDecision, ExecutionResult)
    - Configuration : .env (Jira credentials, project key)
    - Chaque action doit passer par ActionGuard.evaluate() AVANT exécution

INTERFACES DISPONIBLES :
    - JiraClient : src/orchestrix/integrations/jira/client.py  (à implémenter)
    - ActionGuard : src/orchestrix/reliability/gateway.py  (à implémenter)

⚠️ AUCUNE action ne doit être exécutée sans être passée par ActionGuard.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass

from orchestrix.schemas.decision import ActionDecision, ActionProposal
from orchestrix.schemas.plan import Plan

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Résultat de l'exécution d'une action Jira après passage par ActionGuard."""

    proposal: ActionProposal
    decision: ActionDecision
    jira_response: dict | None = None
    error: str | None = None
    succeeded: bool = False


class OpsAgent:
    """Ops Agent — traduit un Plan approuvé en actions Jira exécutées."""

    def __init__(self) -> None:
        # self.jira = JiraClient()  # TODO: instancier
        # self.guard = ActionGuard()  # TODO: instancier
        pass

    def plan_to_proposals(self, plan: Plan) -> Iterator[ActionProposal]:
        """Convertit un Plan en propositions d'actions Jira.

        Pour chaque Epic :
          - create_epic
        Pour chaque Task dans l'ordre topologique des dépendances :
          - create_issue
          - assign_issue (matching compétences + charge via TeamProfile)
          - create_sprint  (une fois par epic)

        Args:
            plan: plan approuvé par le chef de projet

        Yields:
            ActionProposal — à soumettre à ActionGuard.evaluate()
        """
        raise NotImplementedError("OpsAgent.plan_to_proposals : voir docstring.")

    def execute_plan(
        self,
        plan: Plan,
        dry_run: bool = False,
    ) -> list[ExecutionResult]:
        """Boucle complète : propose → ActionGuard → exécute.

        Args:
            plan: plan approuvé
            dry_run: si True, n'exécute JAMAIS l'action Jira réelle (utilisé pour le benchmark)

        Returns:
            Liste des résultats d'exécution
        """
        raise NotImplementedError("OpsAgent.execute_plan : voir docstring.")
