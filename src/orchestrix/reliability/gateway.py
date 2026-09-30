"""ActionGuard — squelette à implémenter (Lot B).

RÈGLES DÉTERMINISTES (toujours actives) :
  1. Schema validation     — params conformes au schéma Jira attendu
  2. RBAC applicatif        — user_role a le droit de faire cette action
  3. Idempotence            — pas de doublon (même action déjà exécutée)
  4. Charge utilisateur     — quota quotidien / hebdomadaire respecté
  5. Cohérence d'état       — ex: ne pas assigner une issue déjà closed
  6. Sécurité prompt-injection — valeurs retournées par Jira ne contiennent
                                  pas d'instructions cachées

SCORE ML RÉSIDUEL (option avancée) :
  Limité aux anomalies de trajectoire non déjà encodées par les règles
  déterministes (séquence d'appels individuellement valides mais anormale).

MODES D'EXÉCUTION :
  - Production : ALLOW → vrai appel Jira Cloud Free
  - Benchmark  : ALLOW → mock executor sur état synthétique en mémoire
                (AUCUNE action réelle ne doit s'exécuter pendant le benchmark)
"""

from __future__ import annotations

import logging

from orchestrix.schemas.decision import ActionDecision, ActionProposal

logger = logging.getLogger(__name__)


class ActionGuard:
    """Reliability Gateway — toutes les actions Jira passent par evaluate()."""

    def __init__(self, enable_residual_ml: bool = False) -> None:
        self.enable_residual_ml = enable_residual_ml
        # self.idempotency_cache = ...
        # self.user_quota_tracker = ...
        # self.residual_ml_model = None  # si activé

    async def evaluate(self, proposal: ActionProposal) -> ActionDecision:
        """Évalue une proposition d'action et retourne une décision.

        Returns:
            ActionDecision avec verdict ∈ {allow, review, block}
        """
        raise NotImplementedError("ActionGuard.evaluate : voir docstring.")

    # ── Règles déterministes (à implémenter une par une) ──────────

    def _check_schema(self, proposal: ActionProposal) -> tuple[bool, str]:
        """Vérifie que les params sont conformes au schéma Jira de l'action."""
        raise NotImplementedError

    def _check_rbac(self, proposal: ActionProposal) -> tuple[bool, str]:
        """Vérifie que le user_role a le droit d'effectuer cette action."""
        raise NotImplementedError

    def _check_idempotency(self, proposal: ActionProposal) -> tuple[bool, str]:
        """Vérifie qu'une action identique n'a pas déjà été exécutée récemment."""
        raise NotImplementedError

    def _check_quota(self, proposal: ActionProposal) -> tuple[bool, str]:
        """Vérifie que l'utilisateur n'a pas dépassé son quota journalier/hebdo."""
        raise NotImplementedError

    def _check_state_consistency(self, proposal: ActionProposal) -> tuple[bool, str]:
        """Vérifie que l'état Jira permet cette action (ex: pas assigner closed)."""
        raise NotImplementedError

    def _check_prompt_injection(self, proposal: ActionProposal) -> tuple[bool, str]:
        """Vérifie que les valeurs de params ne contiennent pas d'injection."""
        raise NotImplementedError

    # ── ML résiduel (option avancée) ──────────────────────────────

    def _compute_residual_risk(self, proposal: ActionProposal) -> float:
        """Score ML de risque sur la trajectoire (séquence d'actions récentes).

        Doit apprendre UNIQUEMENT ce que les règles déterministes ne capturent
        pas. Si les features encodent les mêmes informations que les règles,
        le modèle ne démontre rien — c'est de la circularité.
        """
        raise NotImplementedError
