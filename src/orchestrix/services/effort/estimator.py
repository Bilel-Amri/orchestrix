"""Effort Estimator — squelette à implémenter (Lot A).

Métriques cibles (section 8.1 de la proposition) :
  - MAE, RMSE, MAPE
  - sur un sous-ensemble held-out de JOSSE

Modèles à comparer :
  - Ridge / Linear Regression (baseline)
  - Random Forest
  - XGBoost

Tracking : chaque modèle loggué dans MLflow avec :
  - params (hyperparams du modèle)
  - metrics (MAE, RMSE, MAPE)
  - artifacts (le modèle sérialisé, feature importance si dispo)
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from orchestrix.schemas.plan import EffortEstimate, Task

logger = logging.getLogger(__name__)


class EffortEstimator:
    """Service ML d'estimation d'effort."""

    def __init__(self, model_uri: str | None = None) -> None:
        """Charge un modèle depuis MLflow Registry, ou None si non spécifié."""
        # TODO: self.model = mlflow.sklearn.load_model(model_uri) if model_uri else None
        self.model = None

    def train(self, train_data_path: Path, **hyperparams) -> dict:
        """Entraîne le modèle sur JOSSE.

        Args:
            train_data_path: chemin vers le CSV JOSSE préprocessé
            **hyperparams: hyperparamètres du modèle

        Returns:
            dict avec metrics (MAE, RMSE, MAPE) + model_uri MLflow
        """
        raise NotImplementedError("EffortEstimator.train : voir docstring.")

    def predict(self, task: Task) -> EffortEstimate:
        """Prédit l'effort pour une tâche.

        Args:
            task: tâche à annoter (utilise title, description, required_skills)

        Returns:
            EffortEstimate avec hours + confidence + model_id + model_version
        """
        raise NotImplementedError("EffortEstimator.predict : voir docstring.")

    def evaluate(self, test_data_path: Path) -> dict[str, float]:
        """Évalue sur le test set."""
        raise NotImplementedError("EffortEstimator.evaluate : voir docstring.")

    @staticmethod
    def load_josse_subset(path: Path, n_rows: int | None = None) -> pd.DataFrame:
        """Charge un sous-ensemble de JOSSE.

        Format attendu après preprocessing :
          - issue_key, summary, description, required_skills, effort_hours
        """
        df = pd.read_csv(path, nrows=n_rows)
        return df
