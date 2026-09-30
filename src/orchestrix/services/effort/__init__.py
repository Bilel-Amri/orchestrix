"""Effort Estimator — service ML (Lot A).

Entraîné et évalué sur JOSSE.
Compare Ridge / Linear / Random Forest / XGBoost (cf. section 8.1 de la proposition).

⚠️ JOSSE est utilisé UNIQUEMENT pour l'effort.
   Itemlet a des champs d'effort mais son article 2026 précise qu'ils
   sont des proxys déclaratifs, pas des mesures validées.
"""
from orchestrix.services.effort.estimator import EffortEstimator

__all__ = ["EffortEstimator"]
