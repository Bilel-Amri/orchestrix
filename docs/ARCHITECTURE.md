# ORCHESTRIX — Architecture détaillée

> Ce document complète le README et la proposition. Il est destiné aux développeurs qui implémentent le système.

## Vue d'ensemble

```
USER ──▶ Scoping Agent ──▶ Effort + Priority Estimators (services ML)
                                   │
                                   ▼
                         Validation humaine du plan
                                   │
                                   ▼
                          Ops Agent (tool-calling Jira)
                                   │
                                   ▼
                              ActionGuard
                       (déterministe + ML résiduel)
                       ┌──────────┼──────────┐
                       ▼          ▼          ▼
                     ALLOW      REVIEW      BLOCK
                                   │
                                   ▼
                            Jira Cloud réel
                            (ou mock dry-run)
                                   │
                                   ▼
                            Risk Agent
                       (surveillance continue)

AgentOps Control Layer (transverse, NE SONT PAS des agents) :
  - MLflow   - DVC    - GitHub Actions   - Langfuse
```

## Le principe architectural en une phrase

> **L'humain valide l'intention. La couche de fiabilité valide l'exécution.**

Cette phrase est la boussole du projet. Chaque décision technique doit répondre à :
- Est-ce que ça respecte cette séparation ?
- Est-ce que ça aide l'humain à valider plus efficacement ?
- Est-ce que ça aide ActionGuard à valider plus strictement ?

## Les 3 agents (vrais agents, avec boucle de raisonnement)

| Agent | Lot | Rôle | Entrée | Sortie |
|---|---|---|---|---|
| **Scoping** | A | Découpe un brief en plan structuré | Brief + (optionnel) preuves RAG | `Plan` JSON validé |
| **Ops** | B | Traduit un plan approuvé en actions Jira | `Plan` approuvé | Séquence de `ActionProposal` |
| **Risk** | A | Surveille activité et prédit les risques | Issues Jira + features comportementales | `RiskScore` + `RiskAlert` |

## Les 2 services ML (PAS des agents)

| Service | Lot | Modèles | Donnée | Métriques |
|---|---|---|---|---|
| **Effort Estimator** | A | Ridge, RF, XGBoost | JOSSE | MAE, RMSE, MAPE |
| **Priority / Complexity Estimator** | A | LogReg, RF, XGBoost, TabTransformer | Itemlet | Precision@K, F1, NDCG |

Pas de boucle de raisonnement, pas de tool calling — ce sont des **services** que le Scoping Agent appelle pour annoter le plan numériquement.

## Le Reliability Gateway (ActionGuard)

Toutes les actions Jira générées par l'Ops Agent DOIVENT passer par `ActionGuard.evaluate()` avant exécution.

### Règles déterministes (toujours actives)

1. **Schema** — params conformes au schéma Jira de l'action
2. **RBAC applicatif** — user_role a le droit de faire cette action
3. **Idempotence** — pas de doublon (clé = action_type + params normalisés)
4. **Charge** — quota quotidien / hebdomadaire de l'utilisateur
5. **Cohérence d'état** — ex: pas d'assignation sur issue closed
6. **Sécurité prompt-injection** — valeurs de params scannées pour instructions cachées

### Score ML résiduel (option avancée)

Limité aux anomalies de **trajectoire** non déjà encodées par les règles déterministes. Le risque ici est la **circularité** : si les features encodent les mêmes informations que les règles, le ML ne démontre rien.

**Features recommandées** :
- nombre de tool calls dans la trajectoire récente
- séquence d'outils (bigrammes, trigrammes)
- temps entre les appels
- répétitions du même outil
- distance aux trajectoires normales (clustering historique)
- déviation du rôle habituel de l'utilisateur

### Modes d'exécution

- **Production** : verdict=ALLOW → vrai appel API Jira Cloud Free
- **Benchmark** : verdict=ALLOW → `JiraMockExecutor` (état synthétique en mémoire)
  - ⚠️ **Aucune action de benchmark ne doit s'exécuter contre le vrai Jira**

## Le Risk Agent (surveillance continue)

### Cible de prédiction

```
y = 1  si l'issue dépasse un seuil de résolution prolongée
```

Le seuil est un **quantile du temps de résolution historique** conditionné au type de projet, défini sur le train set, puis gelé.

### Features (à l'instant t)

Toutes les features doivent être **disponibles à l'instant t** et issues d'un instant ≤ t.

- durée d'ouverture actuelle (now - created_at, bornée par t)
- cycle time observé jusqu'à t
- nb réouvertures jusqu'à t
- nb blocages jusqu'à t
- signal commentaires jusqu'à t (NLP optionnel)
- **proxy historique de charge** : volume d'issues actives de l'assigné (PAS de capacité temps-réel)

### Splits sans fuite

| Split | Principe | Rôle |
|---|---|---|
| **Temporel (principal)** | passé → futur | Vraie prédiction |
| **Projets tenus à l'écart** | projets A–N → projet O jamais vu | Robustesse inter-projets |
| **Combinaisons inédites** | familles connues → combinaisons nouvelles | Exploration |

## L'AgentOps Control Layer

Couche transverse qui n'est PAS un agent :

- **MLflow** : tracking des expériences + registry des modèles + traces d'inférence
- **DVC** : versionnage des datasets (JOSSE, Itemlet, Public Jira, benchmark, politiques)
- **GitHub Actions** : CI avec evaluation gate bloquant
- **Langfuse** : observabilité des appels LLM
- **OpenTelemetry** : traces d'exécution distribuées
- **PostgreSQL audit_log** : journal append-only de toutes les actions Jira

## Le contrat entre Lot A et Lot B

Les deux lots partagent uniquement le module `src/orchestrix/schemas/`.

```
Lot A produit :                     Lot B consomme :
  - Plan                               │
  - EffortEstimate                     │
  - PriorityComplexity                 ▼
  - RiskScore                       Lot B produit :
  - RiskAlert                          - ActionProposal
                                       - ActionDecision
                                       - ExecutionResult
                                       - AuditLogEntry
```

**Règle** : aucune modification d'un schéma partagé sans coordination (PR avec review des deux côtés).

## Arborescence des dossiers

```
orchestrix/
├── src/orchestrix/
│   ├── agents/         # Lot A (Scoping, Risk) + Lot B (Ops)
│   │   ├── scoping/    # Lot A
│   │   ├── risk/       # Lot A
│   │   └── ops/        # Lot B
│   ├── services/       # Lot A (Effort, Priority)
│   │   ├── effort/
│   │   └── priority/
│   ├── reliability/    # Lot B (ActionGuard)
│   ├── rag/            # Lot A (retrieval hybride)
│   ├── integrations/   # Lot B (Jira client + mock)
│   ├── observability/  # Commun (Langfuse, OTel)
│   ├── api/            # Lot B (FastAPI)
│   ├── dashboard/      # Lot A ou B (Streamlit)
│   ├── db/             # Commun (modèles, migrations)
│   ├── schemas/        # Commun — STABLE, coordination requise
│   ├── config/
│   └── utils/
├── data/
│   ├── raw/            # DVC-tracked
│   ├── processed/
│   ├── benchmarks/
│   └── policies/
├── evaluation/         # Commun (suites + dual-rater)
├── mlflow/             # Tracking config
├── docker/             # docker-compose
├── docs/
├── notebooks/          # EDA
├── scripts/
├── tests/
└── .github/
```

## Pourquoi cette architecture est défendable

Pour chaque exigence du module projet, l'architecture y répond :

| Exigence | Réponse |
|---|---|
| ≥2 étudiants, rôles identifiables | Lot A (Modélisation IA) / Lot B (Systèmes & Fiabilité) |
| ≥3 modèles/algorithmes | Scoping (SLM), Effort (Ridge/RF/XGB), Priority (LogReg/RF/XGB/TabTransformer), Risk (LogReg/RF/XGB/IsolationForest) + ablation A→E |
| Métriques d'évaluation | MAE/RMSE/MAPE, Precision/Recall/F1/NDCG, PR-AUC/calibration, unsafe-action rate, false-block rate, task success, grounding |
| Git + PR | Repo avec revue croisée, 2 reviewers |
| DVC | data/raw/, data/processed/, data/benchmarks/, data/policies/ |
| MLflow | Tracking de toutes les expériences + registry |
| Ressources gratuites | CPU local, Colab/Kaggle (QLoRA avancé), Jira Free |
