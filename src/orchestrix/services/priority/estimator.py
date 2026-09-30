"""Priority / Complexity Estimator — squelette (Lot A)."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from orchestrix.schemas.plan import PriorityComplexity, Task

logger = logging.getLogger(__name__)


class PriorityComplexityEstimator:
    """Service ML de priorisation et classification de complexité."""

    def __init__(self, model_uri: str | None = None) -> None:
        self.model = None

    def train(self, train_data_path: Path, **hyperparams) -> dict:
        """Entraîne sur Itemlet.

        Returns:
            dict avec metrics (Precision@K, Recall@K, F1, NDCG) + model_uri
        """
        raise NotImplementedError

    def predict(self, task: Task) -> PriorityComplexity:
        """Prédit priorité + complexité pour une tâche."""
        raise NotImplementedError

    def evaluate(self, test_data_path: Path) -> dict[str, float]:
        """Évalue sur le test set."""
        raise NotImplementedError

    @staticmethod
    def load_itemlet_subset(path: Path, n_rows: int | None = None) -> pd.DataFrame:
        """Charge un sous-ensemble d'Itemlet (parquet).

        Format attendu après preprocessing :
          - sprint_metadata_*, priority, complexity
        """
        df = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path, nrows=n_rows)
        return df
