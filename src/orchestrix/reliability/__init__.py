"""ActionGuard — Reliability Gateway (Lot B).

Toute action Jira générée par l'Ops Agent DOIT passer par ActionGuard.evaluate()
avant exécution. Le gateway combine :
  - Vérifications déterministes (schéma, RBAC applicatif, idempotence, charge)
  - Score ML résiduel sur la trajectoire (option avancée)

Pour le benchmark safe/unsafe, l'environnement est dry-run : un mock executor
simule Jira sur un état synthétique en mémoire.
"""

from orchestrix.reliability.gateway import ActionGuard

__all__ = ["ActionGuard"]
