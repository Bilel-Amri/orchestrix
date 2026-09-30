"""Risk Agent — squelette à implémenter (Lot A).

RÔLE :
    Pour chaque issue Jira ouverte, à l'instant t :
      1. Extraire les features comportementales disponibles à t
         (durée d'ouverture, cycle time jusqu'à t, réouvertures, blocages,
          commentaires NLP, **volume d'issues actives de l'assigné** comme
          proxy de charge — PAS de capacité temps-réel car non disponible
          dans Public Jira)
      2. Appeler le modèle de risque (LogReg / RF / XGBoost / Isolation Forest)
      3. Comparer au seuil de résolution prolongée
      4. Émettre une RiskAlert si dépassement

CIBLE DE PRÉDICTION :
    y = 1 si l'issue dépasse un seuil de résolution prolongée
    Le seuil est défini sur le train set uniquement, puis gelé.

SPLITS SANS FUITE (section 9 de la proposition) :
    1. Temporel : passé → futur (principal)
    2. Projets tenus à l'écart : projets A–N → projet O (jamais vu)
    3. Combinaisons inédites (exploratoire)
"""
from __future__ import annotations

import logging
from datetime import datetime

from orchestrix.schemas.risk import RiskAlert, RiskScore

logger = logging.getLogger(__name__)


class RiskAgent:
    """Risk Agent — surveillance continue."""

    def __init__(self) -> None:
        # self.model = load_model_from_mlflow(...)
        # self.feature_pipeline = FeaturePipeline()
        pass

    def compute_features(self, issue_key: str, snapshot_at: datetime) -> dict:
        """Extrait les features comportementales d'une issue à l'instant t.

        ⚠️ RÈGLE : aucune feature ne doit provenir d'un instant postérieur à t.

        Features à calculer :
          - durée d'ouverture actuelle (now - created_at, bornée par t)
          - cycle time observé jusqu'à t
          - nombre de réouvertures jusqu'à t
          - nombre de blocages jusqu'à t
          - signal des commentaires jusqu'à t (NLP optionnel)
          - volume d'issues actives de l'assigné (proxy historique)
        """
        raise NotImplementedError("RiskAgent.compute_features : voir docstring.")

    def predict(self, issue_key: str, snapshot_at: datetime | None = None) -> RiskScore:
        """Prédit le risque de résolution prolongée pour une issue."""
        raise NotImplementedError("RiskAgent.predict : voir docstring.")

    def alert_if_high(self, risk: RiskScore, threshold: float = 0.7) -> RiskAlert | None:
        """Émet une alerte si le score dépasse le seuil."""
        raise NotImplementedError("RiskAgent.alert_if_high : voir docstring.")

    def run_continuous_scan(self, project_key: str) -> list[RiskAlert]:
        """Scan toutes les issues ouvertes d'un projet et émet les alertes."""
        raise NotImplementedError("RiskAgent.run_continuous_scan : voir docstring.")
