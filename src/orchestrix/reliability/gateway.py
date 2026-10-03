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

from pydantic import ValidationError

from orchestrix.schemas.actions import (
    AddCommentParams,
    AssignIssueParams,
    CreateEpicParams,
    CreateIssueParams,
    CreateSprintParams,
    TransitionIssueParams,
    UpdateFieldParams,
    _ActionParams,
)
from orchestrix.schemas.decision import ActionDecision, ActionProposal

logger = logging.getLogger(__name__)

# Règle 1 — table de routage action_type → grammaire de params.
# Entrée manquante = grammaire désynchronisée du router : fail-closed, pas de repli.
SCHEMA_MAP: dict[str, type[_ActionParams]] = {
    "create_epic": CreateEpicParams,
    "create_issue": CreateIssueParams,
    "create_sprint": CreateSprintParams,
    "assign_issue": AssignIssueParams,
    "transition_issue": TransitionIssueParams,
    "add_comment": AddCommentParams,
    "update_field": UpdateFieldParams,
}

# Static application-level RBAC policy.
# This is OUR application policy, not Jira's native permission system.
# The LLM never modifies this policy.
# Unknown roles/actions are denied by default (fail-closed).
RBAC_POLICY: dict[str, frozenset[str]] = {
    "viewer": frozenset(),
    "developer": frozenset(
        {
            "create_issue",
            "transition_issue",
            "add_comment",
            "update_field",
        }
    ),
    "project_manager": frozenset(SCHEMA_MAP),
    "admin": frozenset(SCHEMA_MAP),
}


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
        """Vérifie que les params sont conformes au schéma Jira de l'action.

        Règle PURE : lit `proposal.action_type` / `proposal.params` et la table
        `SCHEMA_MAP`, ne modifie AUCUN état (ni la proposal, ni self, ni cache).
        C'est la première porte du gateway : elle doit être sûre à appeler sur
        une proposition invalide, donc avant toute règle à effet de bord.

        Returns:
            (True, "") si les params sont valides, sinon (False, raison auditable).
        """
        model = SCHEMA_MAP.get(proposal.action_type)
        if model is None:
            known = ", ".join(sorted(SCHEMA_MAP))
            return False, (f"action_type inconnu: {proposal.action_type!r} (connus: {known})")

        try:
            model.model_validate(proposal.params)
        except ValidationError as exc:
            details = "; ".join(
                f"{'.'.join(str(loc) for loc in err['loc']) or '<racine>'}: {err['msg']}"
                for err in exc.errors()
            )
            return False, (
                f"params invalides pour {proposal.action_type!r} ({model.__name__}): {details}"
            )

        return True, ""

    def _check_rbac(self, proposal: ActionProposal) -> tuple[bool, str]:
        """Check whether the user's application role may perform the action.

        Deterministic. Side-effect free.
        Returns (True, "") when authorized, (False, reason) otherwise.
        """
        role = proposal.user_role
        action_type = proposal.action_type
        if action_type not in SCHEMA_MAP:
            return False, f"action_type inconnu: {action_type!r}"
        allowed_actions = RBAC_POLICY.get(role)
        if allowed_actions is None:
            return False, f"rôle RBAC inconnu: {role!r}"
        if action_type not in allowed_actions:
            return False, (f"rôle {role!r} non autorisé à effectuer l'action {action_type!r}")
        return True, ""

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
