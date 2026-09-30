# Guide de configuration — Jira Cloud Free (projet démo)

> Lot B — Semaine 1. Durée : ~20 minutes. Coût : 0 €.

## Étapes

1. **Créer le site Atlassian** — https://www.atlassian.com/software/free
   → « Get Jira Free » → choisir une URL de site, ex `https://orchestrix.atlassian.net`.
2. **Créer le projet démo** — Dans Jira : *Projects → Create project → Scrum*.
   - Nom : `ORCHESTRIX Demo`
   - Key : `DEMO`
   - Type : **team-managed** (défaut sur Free).
3. **Créer l'API token** — https://id.atlassian.com/manage-profile/security/api-tokens → *Create API token*.
4. **Remplir `.env`** :
   ```bash
   JIRA_BASE_URL=https://orchestrix.atlassian.net
   JIRA_EMAIL=you@example.com
   JIRA_API_TOKEN=<le-token>
   JIRA_DEMO_PROJECT_KEY=DEMO
   ```
5. **Vérifier** :
   ```bash
   python scripts/seed_jira_demo.py --dry-run
   ```
   Attendu : `Projet DEMO : trouvé`.
6. **Seeder le plan démo** :
   ```bash
   python scripts/seed_jira_demo.py
   ```
   Crée 3 epics + 9 tasks (label `orchestrix-demo-plan-v1`). Idempotent.
7. **Nettoyer / rejouer** :
   ```bash
   python scripts/seed_jira_demo.py --reset   # supprime les issues démo
   python scripts/seed_jira_demo.py --force   # re-seed par-dessus
   ```

## Troubleshooting

| Symptôme | Cause probable | Fix |
|---|---|---|
| `401 Unauthorized` | token expiré ou email/token incohérents | recréer le token, vérifier `JIRA_EMAIL` |
| `403` | token sans accès au site | vérifier l'accès au produit Jira sur le site |
| `Projet DEMO : ABSENT` | clé de projet différente | aligner `JIRA_DEMO_PROJECT_KEY` dans `.env` |
| story points rejetés | champ custom différent | sans conséquence — le client retry sans ce champ |
| lien Epic refusé | projet **company-managed** | le client retente sans `parent` (warning OK) |

## Limites Jira Free (pourquoi RBAC + audit côté app)

- ≤ 10 utilisateurs, 2 Go stockage
- Pas de permissions/roles personnalisables
- **Pas de journal d'audit natif** → le journal d'audit ActionGuard
  (table `jira_action_audit`, append-only) comble ce manque
- Site désactivable après inactivité — relancer un `--dry-run` avant la démo

> ⚠️ Benchmark : utiliser `JiraMockExecutor` (jamais le vrai Jira), cf. RUNBOOK.
