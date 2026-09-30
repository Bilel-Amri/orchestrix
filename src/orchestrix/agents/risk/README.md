# Risk Agent — Lot A

## Rôle

Pour chaque issue Jira ouverte, calcule à l'instant **t** une probabilité de **résolution prolongée**, et émet une alerte au chef de projet si elle dépasse un seuil.

## Pipeline

```
[Issue Jira ouverte]
        │
        ▼
[compute_features]  ← features à l'instant t (snapshot_at)
        │   - durée d'ouverture actuelle
        │   - cycle time observé jusqu'à t
        │   - nb réouvertures jusqu'à t
        │   - nb blocages jusqu'à t
        │   - signal commentaires jusqu'à t (NLP, avancé)
        │   - volume d'issues actives de l'assigné (proxy historique)
        │
        │   ⚠️ AUCUNE feature après t (pas de fuite temporelle)
        ▼
[predict]  ← modèle MLflow Registry
        │   - modèles : LogReg / RF / XGBoost / Isolation Forest (avancé)
        │   - cible : y = 1 si durée > seuil (défini sur train, gelé)
        ▼
[RiskScore]
        │
        ▼
[alert_if_high] → RiskAlert si score > seuil
```

## Cible de prédiction

**y = 1 si l'issue dépasse un seuil de résolution prolongée**

- Le seuil est un **quantile du temps de résolution historique** conditionné au type de projet
- Défini sur le **train set uniquement**, gelé avant le test
- Justification du choix de "résolution prolongée" plutôt que "retard" : Jira historique n'a pas toujours d'échéance planifiée

## Splits sans fuite

| Split | Principe | Rôle |
|---|---|---|
| **Temporel (principal)** | passé → futur | Vraie prédiction |
| **Projets tenus à l'écart** | projets A–N → projet O jamais vu | Robustesse inter-projets |
| **Combinaisons inédites** | familles connues → combinaisons nouvelles | Exploration |

## Ce qui doit être implémenté

1. **Feature pipeline** (`compute_features`)
   - Lire depuis `risk_scores` ou calculer depuis l'API Jira (avec cache)
   - Snapshot temporel strict (`features_snapshot_at`)

2. **Modèles comparés** (dans `services/risk/`)
   - LogReg, Random Forest, XGBoost
   - Isolation Forest (anomaly detection, non-supervisé, avancé)
   - Tracking MLflow pour chaque

3. **Alertes** (`alert_if_high`)
   - Stocker dans `risk_scores` et `audit_log`
   - Notifier via Streamlit dashboard

4. **Tests** (`tests/unit/agents/test_risk.py`)
   - Test de l'extraction de features (avec mock temporal data)
   - Test qu'aucune feature post-t n'est utilisée
   - Test du seuil

## ⚠️ Note méthodologique importante

La "charge actuelle de l'assigné" au sens d'une capacité temps-réel (ex. "17h restantes cette semaine") **n'est pas disponible dans Public Jira**. On utilise un **proxy historique observable** : volume d'issues actives de l'assigné, fréquence d'assignations récentes.

Cette distinction est explicite pour éviter de sur-interpréter la feature.
