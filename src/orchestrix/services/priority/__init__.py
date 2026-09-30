"""Priority / Complexity Estimator — service ML (Lot A).

Entraîné et évalué sur Itemlet (727 282 issues, 108 features, 19 domaines).
Compare LogReg / RF / XGBoost / TabTransformer (cf. section 8.1).

⚠️ Itemlet est utilisé UNIQUEMENT pour priorisation et complexité.
   Pour l'effort, c'est JOSSE exclusivement.
"""

from orchestrix.services.priority.estimator import PriorityComplexityEstimator

__all__ = ["PriorityComplexityEstimator"]
