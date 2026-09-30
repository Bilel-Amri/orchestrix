# Ops Agent — Lot B

## Rôle

Traduit un `Plan` approuvé en appels Jira réels (create_epic, create_issue, create_sprint, assign_issue), chacun passant par ActionGuard avant exécution.

## Pipeline

```
[Plan approved]
      │
      ▼
[plan_to_proposals]  ← ops/agent.py
      │   pour chaque epic : create_epic
      │   pour chaque task (ordre topologique) :
      │     - create_issue
      │     - assign_issue (matching compétences + charge)
      │     - create_sprint (une fois par epic)
      ▼
[ActionGuard.evaluate]  ← reliability/gateway.py
      │
      ├─ ALLOW → execute via JiraClient
      ├─ REVIEW → queue human review → wait → execute or block
      └─ BLOCK → log + skip
      │
      ▼
[ExecutionResult]
```

## Ce qui doit être implémenté

1. **Plan → Actions** (`agent.py:plan_to_proposals`)
   - Ordre topologique sur les dépendances
   - Mapping Task → Issue Jira avec champs requis
   - Matching compétences : charger TeamProfile et calculer le score

2. **ActionGuard integration** (`agent.py:execute_plan`)
   - Boucle : propose → guard.evaluate → execute
   - Si verdict=review : notifier UI, attendre, re-évaluer
   - Logging de chaque (proposal, decision, result) dans audit log

3. **Dry-run mode** pour benchmark safe/unsafe
   - `execute_plan(plan, dry_run=True)` ne doit JAMAIS appeler la vraie API
   - Utiliser un JiraMockExecutor qui partage l'interface de JiraClient

4. **Tests** (`tests/unit/agents/test_ops.py`)
   - Test de l'ordre topologique
   - Test de la coordination avec ActionGuard (mock)
   - Test du dry-run mode (aucun appel réel)

## Interfaces stables

- `Plan` (schemas/plan.py) — input
- `ActionProposal` / `ActionDecision` / `ExecutionResult` — output
- `ActionGuard` (reliability/gateway.py) — service à instancier

## ⚠️ Règle d'or

**Aucune action Jira ne doit être exécutée sans être passée par ActionGuard.evaluate() en premier.**
Même en mode "demo", cette règle ne s'assouplit pas : l'API Jira réelle passe par ActionGuard, seul l'environnement dry-run est séparé.
