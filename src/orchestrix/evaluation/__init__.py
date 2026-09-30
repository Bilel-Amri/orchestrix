"""Evaluation harness — suite d'évaluation des 4 RQs.

Métriques cibles :
  RQ1 — task_success, completeness, dependency_correctness, anchoring, JSON validity
  RQ2 — precision, recall, F1, PR-AUC, calibration (Brier)
  RQ3 — unsafe-action rate, false-block rate, review rate, task success, latency
  RQ4 — regression detection rate sur modifications volontaires

Protocole d'annotation humaine :
  - 30–50 cas finaux évalués indépendamment par les deux étudiants
  - 4 dimensions : complétude, dépendances, ancrage, éléments non justifiés
  - Divergences documentées puis résolues par consensus
"""
