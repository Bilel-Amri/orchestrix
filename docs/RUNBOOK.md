# RUNBOOK — opérations courantes

> Pour Bilel Amri et Mohamed Amine Gotai — au quotidien pendant le développement.

## Démarrer une session de travail

```bash
cd ~/projects/orchestrix
git pull
./scripts/start.sh
# dans 3 terminaux séparés :
uvicorn orchestrix.api.main:app --reload --port 8000
streamlit run src/orchestrix/dashboard/app.py
mlflow ui --host 0.0.0.0 --port 5000
```

## Quand l'API renvoie 500

```bash
# Vérifier les logs du conteneur API
docker compose -f docker/docker-compose.yml logs -f api

# Vérifier que la DB est up
docker compose -f docker/docker-compose.yml ps
docker compose -f docker/docker-compose.yml exec postgres pg_isready -U orchestrix

# Re-créer les tables (⚠️ drop toutes les données)
python scripts/init_db.py drop
python scripts/init_db.py
python scripts/populate_team_profiles.py
```

## Quand MLflow ne voit pas un run

```bash
# Vérifier la variable d'env
echo $MLFLOW_TRACKING_URI  # doit être http://localhost:5000

# Tester la connexion
curl http://localhost:5000/api/2.0/mlflow/experiments/list

# Si la valeur pointe vers un fichier SQLite local au lieu du serveur
# → soit démarrer mlflow server, soit changer MLFLOW_TRACKING_URI
```

## Lancer une évaluation complète

```bash
# Mode dev : run rapide sur petit benchmark
python -m orchestrix.evaluation.cli run \
  --benchmark data/benchmarks/safe_unsafe_actions.json \
  --output evaluation/reports/dev.json \
  --mode dev

# Mode CI : run rapide pour la pipeline
python -m orchestrix.evaluation.cli run \
  --benchmark data/benchmarks/safe_unsafe_actions.json \
  --output evaluation/reports/ci_run.json \
  --mode ci

# Comparer au baseline
python -m orchestrix.evaluation.cli compare \
  --current evaluation/reports/ci_run.json \
  --baseline evaluation/reports/baseline.json \
  --gate-config .github/eval_gate.json
```

## Réinitialiser complètement la stack

```bash
docker compose -f docker/docker-compose.yml down -v
./scripts/start.sh
```

## Ajouter un nouveau dataset

```bash
# 1. Placer dans data/raw/<source>/
cp mon_dataset.csv data/raw/josse/

# 2. Ajouter au tracking DVC
dvc add data/raw/josse/mon_dataset.csv

# 3. Commit (le .dvc file, PAS le data file)
git add data/raw/josse/mon_dataset.csv.dvc .gitignore
git commit -m "data: add JOSSE subset for effort training"

# 4. Push vers le remote (Google Drive / S3)
dvc push
```

## Quand on veut tester ActionGuard sans toucher au vrai Jira

```bash
# Utiliser le mock executor — JAMAIS de vrais credentials Jira
# Le mock partage l'interface mais opère en mémoire
python -m pytest tests/unit/test_actionguard.py -v
```

## Déboguer un run MLflow

```bash
# Voir tous les runs
mlflow runs list --experiment-id 0

# Comparer 2 runs
mlflow runs compare --run-id <id1> --run-id <id2>

# Télécharger un modèle
mlflow artifacts download --run-id <id> --artifact-path model
```

## Avant la démo PFE

Checklist :
- [ ] Tous les tests passent (`pytest tests/`)
- [ ] Pas de lint error (`ruff check src/`)
- [ ] README à jour
- [ ] ARCHITECTURE.md à jour
- [ ] Plan d'évaluation exécutable d'un seul coup
- [ ] Dashboard Streamlit fonctionnel
- [ ] Demo Jira Cloud Free configuré et nettoyé (guide : docs/jira_demo_setup.md, seed : `python scripts/seed_jira_demo.py`)
- [ ] MLflow UI accessible et présentable
