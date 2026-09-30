"""Risk Agent — Lot A.

Surveille l'activité du projet (issues, transitions, commentaires) et
prédit pour chaque issue sa probabilité de résolution prolongée.
"""
from orchestrix.agents.risk.agent import RiskAgent

__all__ = ["RiskAgent"]
