#!/usr/bin/env bash
# ============================================================================
# ORCHESTRIX — Initialisation DVC
#
# Usage :
#   ./scripts/dvc_setup.sh        # setup complet (interactive)
#   ./scripts/dvc_setup.sh pull   # pull tous les datasets
#   ./scripts/dvc_setup.sh status # status des datasets
# ============================================================================

set -euo pipefail

cd "$(dirname "$0")/.."

bold() { printf "\033[1m%s\033[0m\n" "$*"; }
green() { printf "\033[0;32m%s\033[0m\n" "$*"; }
yellow() { printf "\033[0;33m%s\033[0m\n" "$*"; }
red() { printf "\033[0;31m%s\033[0m\n" "$*"; }

case "${1:-setup}" in

  setup)
    bold "=== Initialisation DVC pour ORCHESTRIX ==="
    echo

    if [ ! -d ".dvc" ]; then
      bold "→ dvc init"
      dvc init
    else
      yellow "→ .dvc existe déjà, skip init"
    fi

    if [ ! -f ".dvc/config" ]; then
      bold "→ Configuration du remote"
      cp .dvc/config.template .dvc/config
      yellow "→ Édite .dvc/config avec ton remote (Google Drive / S3 / etc.)"
      yellow "→ Puis lance : ./scripts/dvc_setup.sh pull"
    else
      green "→ .dvc/config existe déjà"
    fi

    echo
    bold "Datasets à versionner :"
    echo "  - data/raw/josse/         (effort réel, 193 Mo)"
    echo "  - data/raw/itemlet/       (priorisation/complexité, 107 Mo)"
    echo "  - data/raw/public_jira/   (comportement/risque, 5.8 Go)"
    echo "  - data/benchmarks/        (safe/unsafe action benchmark, ~10 Mo)"
    echo "  - data/policies/          (knowledge base politique, <1 Mo)"
    echo
    bold "Pour ajouter un fichier :"
    echo "  dvc add data/raw/josse/josse.csv"
    echo "  dvc push"
    ;;

  pull)
    bold "=== dvc pull ==="
    dvc pull
    green "✓ Datasets pulled"
    ;;

  status)
    bold "=== dvc status ==="
    dvc status
    ;;

  *)
    red "Usage: $0 {setup|pull|status}"
    exit 1
    ;;
esac
