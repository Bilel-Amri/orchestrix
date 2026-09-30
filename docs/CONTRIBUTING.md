# Guide de contribution — ORCHESTRIX

> Conventions pour Mohamed Amine Gotai (Lot A) et Bilel Amri (Lot B).

## Git workflow

### Branches

| Préfixe | Utilisé par | Description |
|---|---|---|
| `lot-a/*` | Mohamed Amine | Scoping, Risk, Effort, Priority, RAG |
| `lot-b/*` | Bilel | Ops, ActionGuard, Jira, FastAPI, observabilité |
| `feature/*` | Tous | Features communes (schemas, db, evaluation, docs) |
| `fix/*` | Tous | Bug fixes |
| `docs/*` | Tous | Documentation seule |
| `main` | — | Stable, déploiement |
| `develop` | — | Intégration continue |

### Règle d'or

> **On ne touche JAMAIS aux fichiers de l'autre lot sans PR review explicite.**

Si tu dois modifier un fichier d'un autre lot (ex: Mohamed Amine doit changer un schema) :
1. Ouvre une PR avec tag `cross-lot`
2. Mentionne l'autre owner dans la description
3. Attends son approval avant merge

### Commits

Format : `<type>(<scope>): <subject>`

```bash
feat(scoping): add RAG evidence retrieval
fix(actionguard): handle missing assignee gracefully
docs(readme): update quickstart
test(schemas): add validation tests for effort_estimate
chore(deps): bump langgraph to 0.2.5
```

## Code style

```bash
# Formatter
ruff format src/ tests/

# Lint
ruff check src/ tests/

# Type-check
mypy src/orchestrix --ignore-missing-imports
```

## Tests

```bash
# Tous les tests unitaires
pytest tests/unit -v

# Tests d'intégration (PostgreSQL requis)
docker compose -f docker/docker-compose.yml up postgres -d
pytest tests/integration -v

# Avec coverage
pytest --cov=src/orchestrix --cov-report=html
```

## Ajouter un dataset

1. Placer le fichier dans `data/raw/<source>/`
2. `dvc add data/raw/<source>/<file>.csv`
3. Commit le `.dvc` file (PAS le data file)
4. `dvc push` (vers le remote configuré)

## Schemas partagés — règles de modification

Les schemas dans `src/orchestrix/schemas/` sont des **interfaces stables**.

Toute modification :
1. Ouvrir une PR avec tag `schema-change`
2. Lister TOUS les consommateurs impactés (grep sur le repo)
3. Mettre à jour tests, docs, et l'autre lot en coordination
4. Ne JAMAIS supprimer un champ sans migration

## Tracking des expériences

Toutes les expériences (entraînement de modèles, runs d'ablation, runs d'évaluation) doivent être logguées dans MLflow :

```python
import mlflow

with mlflow.start_run(run_name="effort-xgb-v1"):
    mlflow.log_params({"model": "xgboost", "max_depth": 6})
    mlflow.log_metrics({"mae": 4.2, "rmse": 6.1, "mape": 0.18})
    mlflow.sklearn.log_model(model, "model")
```

## Avant de push

- [ ] Code formaté (`ruff format`)
- [ ] Pas de lint error (`ruff check`)
- [ ] Tests passent (`pytest tests/unit`)
- [ ] Si nouveau module : ajouter dans README
- [ ] Si modification de schema : PR `schema-change`
- [ ] Pas de secrets dans le diff (`.env`, API keys)
