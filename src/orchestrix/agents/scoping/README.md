# Scoping Agent — Lot A

## Rôle

Génère un `Plan` structuré (epics + tasks + dépendances) depuis un brief en langage naturel.

## Pipeline interne (à implémenter)

```
[PlanGenerationRequest]
        │
        ▼
[retrieve_evidence]  ← src/orchestrix/rag/retrieve.py
        │   - hybrid retrieval : vectoriel (pgvector) + BM25
        │   - filtre source ∈ {josse, itemlet, public_jira, policy}
        │   - filtre type ∈ {task, issue_metadata, dependency/comment, policy}
        │   - top-k=8 par défaut
        ▼
[build_prompt]       ← prompts.py (4 versions A/B/C/D/E)
        │
        ▼
[LLM.invoke]
        │
        ▼
[parse_and_validate]
        │   - parse JSON
        │   - valider via Pydantic (Plan / Epic / Task)
        │   - si échec → retry une fois avec prompt de correction
        ▼
[annotate_with_ML]   ← services/effort + services/priority
        │
        ▼
[mlflow.log]
        │   - params: ablation_condition, prompt_version, llm_model, rag_top_k
        │   - metrics: json_validity, anchored_evidence_count, plan_size
        ▼
[PlanGenerationResponse]
```

## Ce qui doit être implémenté

1. **RAG retrieval** (`src/orchestrix/rag/retrieve.py`)
   - Charger embeddings depuis pgvector
   - Filtrer par source/type
   - Reranking optionnel (cross-encoder)
   - Retourner liste de chunks + métadonnées

2. **JSON parsing & validation**
   - Utiliser `Plan.model_validate_json()`
   - En cas d'erreur : retry avec prompt de correction (max 1 fois)

3. **Intégration Effort + Priority**
   - Appeler `EffortEstimator.predict(task)` pour chaque tâche
   - Idem pour Priority
   - Stocker dans `task.effort_estimate` et `task.priority_complexity`

4. **MLflow tracking**
   - `mlflow.set_experiment("orchestrix-scoping")`
   - Logger params + metrics pour chaque run
   - Logger le plan généré comme artifact

5. **Tests** (`tests/unit/agents/test_scoping.py`)
   - Test du parsing JSON (valide + invalide)
   - Test du retry logic
   - Test de l'annotation ML

## Ablation A→E

Le paramètre `ablation_condition` permet de tester 5 versions :

| Cond | Prompt      | RAG | QLoRA |
|------|-------------|-----|-------|
| A    | minimal     | non | non   |
| B    | structuré   | non | non   |
| C    | structuré   | oui | non   |
| D    | structuré   | non | oui   |
| E    | structuré   | oui | oui   |

Mesurer sur chacun : complétude, ancrage, exactitude des dépendances, erreur d'effort, validité JSON.

## Interfaces stables (à NE PAS modifier sans coordination)

- `PlanGenerationRequest` / `PlanGenerationResponse` / `Plan` (schemas/plan.py)
- `EffortEstimate` / `PriorityComplexity` (schemas/plan.py)
