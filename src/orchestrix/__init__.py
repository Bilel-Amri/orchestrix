"""ORCHESTRIX — Copilote multi-agent pour la gestion de projet.

Pipeline :
    USER → Scoping Agent → Effort + Priority Estimators
                              │
                              ▼
                    Validation humaine du plan
                              │
                              ▼
                       Ops Agent (tool-calling Jira)
                              │
                              ▼
                         ActionGuard
                              │
                              ▼
                         Jira Cloud réel
                              │
                              ▼
                        Risk Agent (surveillance)
"""

__version__ = "0.1.0"
