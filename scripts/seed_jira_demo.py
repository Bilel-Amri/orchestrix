"""Seed du projet démo Jira Cloud Free (Lot B — Semaine 1).

Crée un plan de démonstration (epics + tasks) dans un projet Jira
team-managed, avec label `orchestrix-demo-plan-v1` pour l'idempotence.

Prérequis (guide : docs/jira_demo_setup.md) :
  1. Site Atlassian gratuit (ex: https://orchestrix.atlassian.net)
  2. Projet Scrum "ORCHESTRIX Demo", clé DEMO, team-managed
  3. API token : https://id.atlassian.com/manage-profile/security/api-tokens
  4. .env rempli : JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN

Usage :
  python scripts/seed_jira_demo.py             # seed si absent
  python scripts/seed_jira_demo.py --dry-run   # vérifie connexion + projet, ne crée rien
  python scripts/seed_jira_demo.py --force     # re-seed même si déjà présent
  python scripts/seed_jira_demo.py --reset     # supprime les issues démo (destructif)
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Any

from orchestrix.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

LABEL = "orchestrix-demo-plan-v1"

# (summary, description, est_hours, priority, complexity)
DEMO_EPICS: list[dict[str, Any]] = [
    {
        "summary": "E1 — Intégration paiement en ligne",
        "description": "Ajouter Stripe comme moyen de paiement dans le tunnel de commande.",
        "tasks": [
            (
                "Créer compte Stripe + récupérer clés API",
                "Compte test, clés stockées de façon sécurisée.",
                1.0,
                "P1",
                "S",
            ),
            (
                "Endpoint POST /payments (PaymentIntent)",
                "Validation montant/devise, gestion des erreurs.",
                4.0,
                "P1",
                "M",
            ),
            (
                "Webhook Stripe + réconciliation statuts",
                "Signature webhook, idempotence, màj commande.",
                8.0,
                "P2",
                "L",
            ),
        ],
    },
    {
        "summary": "E2 — Notifications temps réel",
        "description": "Prévenir l'utilisateur des événements importants (paiement, stock, support).",
        "tasks": [
            (
                "Choisir le bus d'événements (Redis vs Kafka)",
                "POC des deux options, matrice de décision.",
                2.0,
                "P2",
                "S",
            ),
            (
                "Service de notifications in-app + email",
                "Templates, retry, dead-letter queue.",
                6.0,
                "P2",
                "M",
            ),
        ],
    },
    {
        "summary": "E3 — Hardening sécurité",
        "description": "Checklist OWASP, rate limiting, audit des dépendances.",
        "tasks": [
            (
                "Rate limiting sur les endpoints publics",
                "Redis token bucket, 429 + Retry-After.",
                4.0,
                "P1",
                "M",
            ),
            (
                "Audit des dépendances (pip-audit) en CI",
                "Échec de CI sur CVE high/critical.",
                2.0,
                "P2",
                "S",
            ),
        ],
    },
]

STANDALONE_TASKS: list[tuple[str, str, float, str, str]] = [
    (
        "Configurer le CI (lint + tests)",
        "GitHub Actions : ruff + pytest, badge README.",
        2.0,
        "P2",
        "S",
    ),
    (
        "Rédiger le runbook de déploiement",
        "Procédure de release + rollback documentée.",
        1.0,
        "P3",
        "S",
    ),
]

TOTAL_EXPECTED = sum(len(e["tasks"]) for e in DEMO_EPICS) + len(STANDALONE_TASKS)


def build_client() -> Any:
    """Construit le JiraClient ou sort avec un message actionable."""
    try:
        from orchestrix.integrations.jira.client import JiraClient

        return JiraClient()
    except ValueError as exc:
        logger.error("%s", exc)
        logger.info("Suivre docs/jira_demo_setup.md puis remplir .env.")
        sys.exit(1)


def demo_plan_exists(client: Any, project_key: str) -> bool:
    jql = f'project = {project_key} AND labels = "{LABEL}"'
    return len(client.search_issues(jql, max_results=1)) > 0


def cleanup_created(client: Any, keys: list[str]) -> None:
    """Best-effort : supprime les issues créées si le seed échoue à mi-chemin."""
    for key in keys:
        try:
            client.delete_issue(key)
            logger.warning("Rollback : %s supprimée", key)
        except Exception as exc:  # noqa: BLE001
            logger.error("Rollback impossible pour %s : %s", key, exc)


def seed(client: Any, project_key: str, force: bool) -> None:
    if not client.project_exists(project_key):
        logger.error(
            "Projet %s introuvable. Le créer à la main (gratuit, type Scrum) — voir docs/jira_demo_setup.md",
            project_key,
        )
        sys.exit(1)

    if not force and demo_plan_exists(client, project_key):
        logger.info(
            "Plan démo déjà présent dans %s — rien à faire (--force pour re-seed).", project_key
        )
        return

    if force and demo_plan_exists(client, project_key):
        logger.info("--force : reset du plan existant avant re-seed.")
        reset(client, project_key)

    created: list[str] = []
    try:
        for epic in DEMO_EPICS:
            epic_res = client.create_epic(
                project_key, epic["summary"], epic["description"], labels=[LABEL]
            )
            created.append(epic_res["key"])
            for summary, desc, hours, priority, complexity in epic["tasks"]:
                desc_full = (
                    f"{desc}\n\n"
                    f"Estimation : {hours}h | Priorité : {priority} | Complexité : {complexity}"
                )
                task = client.create_issue(
                    project_key,
                    summary,
                    desc_full,
                    epic_key=epic_res["key"],
                    labels=[LABEL],
                )
                created.append(task["key"])
        for summary, desc, hours, priority, complexity in STANDALONE_TASKS:
            desc_full = (
                f"{desc}\n\n"
                f"Estimation : {hours}h | Priorité : {priority} | Complexité : {complexity}"
            )
            task = client.create_issue(project_key, summary, desc_full, labels=[LABEL])
            created.append(task["key"])
    except Exception:
        logger.exception("Seed échoué — rollback des issues créées.")
        cleanup_created(client, created)
        sys.exit(1)

    logger.info(
        "Seed terminé : %d epics + %d tasks créés dans %s.",
        len(DEMO_EPICS),
        TOTAL_EXPECTED,
        project_key,
    )
    logger.info("Issues créées : %s", ", ".join(created))


def reset(client: Any, project_key: str) -> None:
    """Supprime toutes les issues portant le label démo. ⚠️ destructif."""
    jql = f'project = {project_key} AND labels = "{LABEL}"'
    issues = client.search_issues(jql, max_results=100)
    for issue in issues:
        try:
            client.delete_issue(issue["key"])
        except Exception as exc:  # noqa: BLE001
            logger.error("Suppression impossible pour %s : %s", issue["key"], exc)
    logger.info("Reset terminé : %d issues supprimées dans %s.", len(issues), project_key)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed / check / reset du projet démo Jira.")
    parser.add_argument(
        "--dry-run", action="store_true", help="vérifie connexion + projet, ne crée rien"
    )
    parser.add_argument(
        "--force", action="store_true", help="re-seed même si le plan démo existe déjà"
    )
    parser.add_argument(
        "--reset", action="store_true", help="supprime les issues démo (destructif)"
    )
    args = parser.parse_args()

    client = build_client()
    settings = get_settings()
    project_key = settings.jira_demo_project_key
    client.check_connection()

    if args.dry_run:
        exists = client.project_exists(project_key)
        logger.info("Projet %s : %s", project_key, "trouvé" if exists else "ABSENT")
        logger.info(
            "Plan démo présent : %s", demo_plan_exists(client, project_key) if exists else "n/a"
        )
        return

    if args.reset:
        reset(client, project_key)
        return

    seed(client, project_key, force=args.force)


if __name__ == "__main__":
    main()
