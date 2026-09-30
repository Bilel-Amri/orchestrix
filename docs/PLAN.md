# Plan de travail — 8 semaines Must-have + 2 Avancé

> Voir la proposition complète (`AgentOps_Project_Copilot_v4_frozen.pdf`) pour la justification scientifique.

## Vue d'ensemble

| Lot | Semaines | Livrables principaux |
|---|---|---|
| **Lot A — Bilel** | 1–8 | Scoping Agent, Effort + Priority Estimators, Risk Agent, RAG pipeline |
| **Lot B — Mohamed Amine** | 1–8 | Ops Agent, ActionGuard, Jira integration, FastAPI, observability |
| **Commun** | 1–8 | DB schemas, evaluation harness, MLflow tracking, dashboard |

## Semaine par semaine

### Semaine 1 — Setup (commun)
- [x] Repo Git, .gitignore, LICENSE
- [x] pyproject.toml + requirements.txt
- [x] docker-compose.yml (postgres + pgvector + redis + mlflow + langfuse)
- [x] DB models (SQLAlchemy + pgvector)
- [x] Configuration (.env.example, settings)
- [x] Schemas Pydantic (interfaces stables)
- [ ] Datasets : pull JOSSE / Itemlet / Public Jira (Lot A)
- [ ] Jira Cloud Free : créer le projet démo (Lot B)

### Semaine 2 — Scoping v1 (Lot A) + Ops skeleton (Lot B)
- [ ] Scoping Agent v1 : SLM de base + prompt structuré (sans RAG) (Lot A)
- [ ] JSON parsing + Pydantic validation + retry (Lot A)
- [ ] FastAPI endpoint `/agent/invoke` (Lot B)
- [ ] JiraMockExecutor + tests (Lot B)

### Semaine 3 — RAG + Ops Agent
- [ ] Hybrid retrieval (pgvector + BM25 + filtres source/type) (Lot A)
- [ ] Embeddings : indexation des preuves (Lot A)
- [ ] Ops Agent : plan → ActionProposal (Lot B)
- [ ] Intégration Jira API réelle (Lot B)

### Semaine 4 — ActionGuard
- [ ] Rules déterministes : schema, RBAC, idempotence, charge, état (Lot B)
- [ ] UI de revue humaine (Lot B)
- [ ] Audit log PostgreSQL append-only (Lot B)

### Semaine 5 — Modèles ML + Risk Agent
- [ ] Effort Estimator : entraînement sur JOSSE (Lot A)
- [ ] Priority Estimator : entraînement sur Itemlet (Lot A)
- [ ] Intégration dans le pipeline Scoping (Lot A)
- [ ] Risk Agent : features à t + premier modèle (LogReg) (Lot A)

### Semaine 6 — Evaluation + benchmark
- [ ] Benchmark safe/unsafe (8+4+1 scénarios) (Lot B)
- [ ] Dual-rater protocol + 30-50 cas finaux (commun)
- [ ] MLflow tracking de toutes les expériences (commun)

### Semaine 7 — Comparaisons + ablations
- [ ] Effort : Ridge / RF / XGBoost comparés (Lot A)
- [ ] Priority : LogReg / RF / XGBoost / TabTransformer comparés (Lot A)
- [ ] Risk : LogReg / RF / XGBoost comparés (Lot A)
- [ ] Ablation Scoping A→B→C (Lot A)
- [ ] ActionGuard : unsafe-action rate / false-block rate mesurés (Lot B)

### Semaine 8 — MLOps + intégration
- [ ] DVC : data/raw/, data/processed/, data/benchmarks/, data/policies/ (Lot A)
- [ ] MLflow registry : modèles promus (Lot A)
- [ ] CI GitHub Actions avec evaluation gate (commun)
- [ ] Dashboard Streamlit (commun)
- [ ] Docker Compose final (commun)
- [ ] README + ARCHITECTURE.md + RUNBOOK.md à jour (commun)

### Semaines 9–10 (Avancé)
- [ ] QLoRA fine-tuning du Scoping Agent (Lot A)
- [ ] Ablation D/E complète (Lot A)
- [ ] Classification NLP des commentaires Risk (Lot A)
- [ ] Isolation Forest pour Risk (Lot A)
- [ ] Score ML résiduel dans ActionGuard (Lot B)
- [ ] Optimisations performance (Lot B)
- [ ] Polish démo + slides défense (commun)

## Definition of Done (chaque semaine)

Une semaine est "done" quand :
- [ ] Tous les items cochés sont mergés sur `develop`
- [ ] Tests passent en CI
- [ ] Au moins 1 expérience logguée dans MLflow (si applicable)
- [ ] Au moins 1 PR review croisée

## Points de synchronisation

Tous les **lundis soirs**, sync de 30 min :
- Ce que chacun a fait la semaine passée
- Ce que chacun va faire cette semaine
- Blockers
- Décisions schema à prendre

## Livrables de la défense (fin semaine 10)

- [ ] Repo Git propre, branches mergées
- [ ] `pytest tests/` passe
- [ ] `ruff check` clean
- [ ] MLflow UI avec ≥15 runs documentés
- [ ] Dashboard Streamlit fonctionnel avec 4 panels minimum
- [ ] Demo end-to-end (brief → plan → exécution Jira réelle → Risk alert)
- [ ] README + ARCHITECTURE.md + RUNBOOK.md finalisés
- [ ] Slides de défense
- [ ] Annexe : résultats des 4 RQs avec ablations A→E
