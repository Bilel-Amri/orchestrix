#!/usr/bin/env bash
# Démarre Orchestrix AVEC le modèle de complexité, sans Docker.
#
#   ./demarrer.sh                    → interface sur http://localhost:8402
#   ./demarrer.sh --port 9000        → un autre port
#   PORT_MODELE=8600 ./demarrer.sh   → un autre port pour le service du modèle
#
# Le script s'arrête proprement (Ctrl+C ferme les deux processus).
set -euo pipefail

ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${PYTHON:-python3}"
PORT_MODELE="${PORT_MODELE:-8500}"
ARTEFACT="$ICI/service_modele/modele/model_bundle.joblib"

echo "── Orchestrix + modèle de complexité ──────────────────────────"

# 1. Le fichier du modèle est-il là ?
if [ ! -f "$ARTEFACT" ]; then
  echo "✗ Fichier du modèle introuvable :"
  echo "    $ARTEFACT"
  echo
  echo "  Copiez votre fichier à cet emplacement :"
  echo "    cp model_bundle.joblib \"$ICI/service_modele/modele/\""
  echo
  echo "  Sans modèle, la plateforme fonctionne quand même :"
  echo "    python3 -m orchestrix --ui"
  exit 1
fi
echo "✓ modèle trouvé : $(du -h "$ARTEFACT" | cut -f1)"

# 2. Les dépendances du service (scikit-learn) sont-elles là ?
if ! "$PY" -c "import sklearn, joblib" >/dev/null 2>&1; then
  echo "→ installation des dépendances du service (une seule fois)…"
  "$PY" -m pip install --quiet -r "$ICI/service_modele/requirements.txt" || {
    echo "✗ installation impossible. Essayez :"
    echo "    $PY -m pip install scikit-learn joblib"
    echo "  ou utilisez Docker : docker compose up --build"
    exit 1
  }
fi
echo "✓ dépendances du service présentes"

# 3. Démarrage du service du modèle en tâche de fond
DOSSIER_MODELE="$(dirname "$ARTEFACT")" PORT="$PORT_MODELE" HOTE=127.0.0.1 \
  "$PY" "$ICI/service_modele/serveur.py" &
PID_MODELE=$!
trap 'kill "$PID_MODELE" 2>/dev/null || true' EXIT INT TERM

# 4. On attend qu'il réponde vraiment
PRET=0
for _ in $(seq 1 60); do
  if "$PY" - "$PORT_MODELE" <<'ATTENTE' >/dev/null 2>&1
import sys, urllib.request
urllib.request.urlopen(f"http://127.0.0.1:{sys.argv[1]}/sante", timeout=1).read()
ATTENTE
  then PRET=1; break; fi
  sleep 0.5
done

if [ "$PRET" = "1" ]; then
  echo "✓ service du modèle : http://127.0.0.1:$PORT_MODELE/sante"
else
  echo "⚠ le service du modèle ne répond pas — la plateforme utilisera les règles internes"
fi

# 5. La plateforme, au premier plan
echo "→ interface : lancement…"
cd "$ICI"
URL_MODELE="http://127.0.0.1:$PORT_MODELE" \
  "$PY" -m orchestrix --ui "$@"
