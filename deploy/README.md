# Deploy

> Stratégie de déploiement pour la démo PFE et au-delà.

## Cibles

| Env | Stack | Usage |
|---|---|---|
| **Local dev** | Docker Compose | Développement quotidien |
| **Demo PFE** | VM locale + Jira Cloud Free | Présentation défense |
| **(futur)** Cloud | Kubernetes + Helm | Production (hors périmètre PFE) |

## Demo PFE — checklist

Avant la défense :

- [ ] VM avec 16 Go RAM, GPU optionnel
- [ ] Docker + Docker Compose installés
- [ ] Python 3.11+ installé
- [ ] Repo cloné
- [ ] `.env` configuré avec Jira Cloud Free credentials
- [ ] `docker compose -f docker/docker-compose.yml up -d`
- [ ] `python scripts/init_db.py`
- [ ] `python scripts/populate_team_profiles.py`
- [ ] Modèles entraînés et promus dans MLflow registry
- [ ] `uvicorn orchestrix.api.main:app --host 0.0.0.0 --port 8000`
- [ ] `streamlit run src/orchestrix/dashboard/app.py`
- [ ] `mlflow ui --host 0.0.0.0 --port 5000`

## Sécurité

- ⚠️ Ne JAMAIS commit `.env`
- ⚠️ Jira API token à rotation régulière
- ⚠️ MLflow artifact store doit être backupé (ou volume Docker persistent)

## Backup

```bash
# Backup PostgreSQL
docker compose -f docker/docker-compose.yml exec postgres pg_dump -U orchestrix orchestrix > backup_$(date +%F).sql

# Backup MLflow
docker compose -f docker/docker-compose.yml exec mlflow mlflow artifacts list
# → copier le volume mlflow_artifacts
```
