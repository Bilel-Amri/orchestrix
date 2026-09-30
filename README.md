# ORCHESTRIX

> Copilote multi-agent pour le cadrage, la planification, l'exécution contrôlée et la détection des risques des projets logiciels.
>
> *AI/MLOps/LLMOps PFE — Tek-Up University · AI & Data Science Engineering*

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

---

## Architecture en une phrase

> **L'humain valide l'intention. La couche de fiabilité valide l'exécution.**

```
USER ──▶ Scoping Agent ──▶ Effort + Priority ML services
                                   │
                                   ▼
                         Validation humaine du plan
                                   │
                                   ▼
                            Ops Agent (tool-calling Jira)
                                   │
                                   ▼
                              ActionGuard
                       ┌──────────┼──────────┐
                       ▼          ▼          ▼
                     ALLOW      REVIEW      BLOCK
                                   │
                                   ▼
                            Jira Cloud réel
                                   │
                                   ▼
                            Risk Agent
                       (surveillance continue)
```

**3 agents** (Scoping, Ops, Risk) + **2 services ML** (Effort, Priority) + **1 reliability gateway** (ActionGuard).

---

## Stack technique

| Couche | Outil |
|---|---|
| Orchestration agents | LangGraph |
| Backend API | FastAPI |
| Base de données | PostgreSQL + pgvector |
| Tracking / Registry | MLflow |
| Datasets versionnés | DVC |
| CI/CD | GitHub Actions (evaluation gate) |
| Containerisation | Docker / Docker Compose |
| LLM local (défaut) | Ollama / vLLM |
| Cloud LLM (fallback) | OpenAI-compatible API |
| Jira | Jira Cloud REST API v3 |
| Embeddings | sentence-transformers `all-MiniLM-L6-v2` |
| Observabilité | OpenTelemetry + Langfuse |

---

## Démarrage rapide

### Prérequis
- Python 3.11+
- Docker + Docker Compose
- Git
- (Optionnel) GPU pour inférence locale LLM

### Installation

```bash
# Cloner le repo
git clone https://github.com/<votre-org>/orchestrix.git
cd orchestrix

# Environnement virtuel + dépendances
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Copier la config
cp .env.example .env
# Éditer .env avec vos credentials Jira Cloud

# Démarrer PostgreSQL + MLflow + Redis
docker compose -f docker/docker-compose.yml up -d

# Initialiser DVC
dvc init
dvc pull  # ou peupler data/raw/ manuellement

# Initialiser la base
python scripts/init_db.py

# Lancer l'API
uvicorn orchestrix.api.main:app --reload --port 8000

# Lancer MLflow UI (autre terminal)
mlflow ui --host 0.0.0.0 --port 5000

# Lancer le dashboard Streamlit (autre terminal)
streamlit run src/orchestrix/dashboard/app.py
```

---

## Structure du projet

```
orchestrix/
├── src/orchestrix/
│   ├── agents/             # 3 agents : Scoping, Ops, Risk
│   │   ├── scoping/        # LangGraph + RAG
│   │   ├── ops/            # Tool-calling Jira
│   │   └── risk/           # Surveillance continue
│   ├── services/           # ML services : Effort, Priority
│   ├── reliability/        # ActionGuard (gateway déterministe)
│   ├── rag/                # Base de connaissances hétérogène
│   ├── integrations/jira/  # Adaptateur API Jira
│   ├── observability/      # OpenTelemetry + Langfuse
│   ├── api/                # FastAPI
│   ├── db/                 # Modèles SQLAlchemy / migrations
│   ├── models/             # Wrappers ML (scikit-learn, etc.)
│   ├── schemas/            # Schemas Pydantic (interfaces stables)
│   ├── config/             # Settings
│   └── utils/
├── data/
│   ├── raw/                # Datasets bruts (DVC-tracked)
│   ├── processed/
│   ├── benchmarks/         # Safe/unsafe action benchmark
│   └── policies/           # Knowledge base politique
├── evaluation/             # Suite d'évaluation + dual-rater
├── mlflow/                 # Tracking server config
├── docker/                 # docker-compose + Dockerfiles
├── docs/                   # ARCHITECTURE, RUNBOOK
├── notebooks/              # EDA / exploration
├── scripts/                # init_db, populate, etc.
├── tests/                  # unit, integration, e2e, benchmarks
├── .github/workflows/      # CI avec evaluation gate
├── deploy/
└── pyproject.toml
```

---

## Répartition de l'équipe

| Lot | Personne | Périmètre | Branches Git |
|---|---|---|---|
| **A — Modélisation IA** | Bilel Amri | `agents/scoping/`, `agents/risk/`, `services/effort/`, `services/priority/`, `rag/` | `lot-a/*` |
| **B — Systèmes & Fiabilité** | Mohamed Amine Gotai | `agents/ops/`, `reliability/`, `integrations/jira/`, `observability/`, `api/` | `lot-b/*` |
| **Commun** | Tous les deux | `schemas/`, `db/`, `evaluation/`, `mlflow/`, `docs/` | PR avec 2 reviewers |

**Règle d'or** : on ne touche JAMAIS aux fichiers de l'autre lot sans PR review.

---

## Données

| Source | Rôle | Cardinalité |
|---|---|---|
| **JOSSE** | Effort Estimator (modèle supervisé) | 100% effort réel, 19% expert |
| **Itemlet** | Priority / Complexity Estimator | 727 282 issues · 204 projets · 108 features |
| **Public Jira v7** | Risk Agent (trajectoires + commentaires) | 2,7M issues · 32M changes · 9M comments |
| **Jira Cloud Free** | Environnement d'exécution réel (démo) | ≤10 users · 2 Go |

⚠️ **JOSSE est utilisé uniquement pour l'effort.** Itemlet est utilisé pour priorisation/complexité uniquement — son article 2026 précise que ses champs d'effort sont des *proxys déclaratifs*, pas des mesures de taille livrable validées.

---

## Questions de recherche

1. **RQ1 (Génération)** — La RAG améliore-t-elle la complétude et l'ancrage aux preuves ?
2. **RQ2 (Prédiction)** — Le comportement historique prédit-il un risque de résolution prolongée ?
3. **RQ3 (Sécurité)** — ActionGuard réduit-il le taux d'unsafe actions sans dégrader la complétion ?
4. **RQ4 (MLOps)** — Le CI evaluation gate détecte-t-il les régressions ?

---

## Plan (8 semaines Must-have + 2 Avancé)

Voir [`docs/PLAN.md`](docs/PLAN.md) pour le détail.

---

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — architecture détaillée
- [`docs/RUNBOOK.md`](docs/RUNBOOK.md) — opérations quotidiennes
- [`docs/PLAN.md`](docs/PLAN.md) — roadmap 8 semaines
- [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md) — conventions de contribution

---

## Licence

MIT — voir [`LICENSE`](LICENSE).
