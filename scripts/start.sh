#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════════════════╗
# ║  ORCHESTRIX — Démarrage local complet                                ║
# ║                                                                      ║
# ║  Usage :  ./scripts/start.sh                                         ║
# ╚══════════════════════════════════════════════════════════════════════╝

set -euo pipefail

cd "$(dirname "$0")/.."

bold() { printf "\033[1m%s\033[0m\n" "$*"; }
green() { printf "\033[0;32m%s\033[0m\n" "$*"; }
yellow() { printf "\033[0;33m%s\033[0m\n" "$*"; }

bold "═══ ORCHESTRIX · démarrage local ═══"
echo

# 1) Vérifier .env
if [ ! -f ".env" ]; then
  yellow "⚠ .env manquant — copie .env.example → .env"
  cp .env.example .env
  yellow "→ Édite .env avec tes credentials Jira avant de continuer"
fi

# 2) Activer venv si présent
if [ -d ".venv" ]; then
  source .venv/bin/activate
  green "✓ venv activé"
fi

# 3) Démarrer Docker stack
bold "→ Démarrage de la stack Docker (postgres, redis, mlflow, langfuse)..."
docker compose -f docker/docker-compose.yml up -d
sleep 5

# 4) Init DB
bold "→ Initialisation de la base..."
python scripts/init_db.py

# 5) Populate team profiles
bold "→ Peuplement des profils d'équipe..."
python scripts/populate_team_profiles.py

# 6) Pull datasets si DVC remote configuré
if [ -f ".dvc/config" ] && grep -q "remote" ".dvc/config"; then
  bold "→ dvc pull des datasets..."
  dvc pull || yellow "⚠ dvc pull a échoué (vérifier remote dans .dvc/config)"
else
  yellow "⚠ Pas de remote DVC configuré — datasets à pull manuellement"
fi

green ""
green "✓ Stack démarrée"
echo
bold "Services disponibles :"
echo "  - PostgreSQL      : localhost:5432"
echo "  - Redis           : localhost:6379"
echo "  - MLflow UI       : http://localhost:5000"
echo "  - Langfuse UI     : http://localhost:3000"
echo "  - API ORCHESTRIX  : à lancer dans un terminal séparé"
echo "  - Dashboard       : à lancer dans un terminal séparé"
echo
bold "Prochaines étapes :"
echo "  uvicorn orchestrix.api.main:app --reload --port 8000"
echo "  streamlit run src/orchestrix/dashboard/app.py"
