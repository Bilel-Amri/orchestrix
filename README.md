# Orchestrix

**AI-Powered Agile Project Planning and Backlog Generation**

Orchestrix est une plateforme intelligente de gestion et de planification de projets logiciels. Elle utilise l'intelligence artificielle et la recherche de connaissances pour transformer un besoin exprimé en langage naturel en un backlog Agile structuré, composé d'Epics, de User Stories et de tâches techniques.

Le système automatise une partie du travail de planification tout en s'appuyant sur des éléments de preuve et un modèle spécialisé pour classifier la complexité des tâches.

---

## 1. Objectifs du projet

Orchestrix vise à faciliter la préparation et l'organisation des projets logiciels en permettant de :

- Transformer une description fonctionnelle en plan de projet structuré.
- Analyser les besoins exprimés en langage naturel.
- Exploiter des sources documentaires pour enrichir la génération.
- Générer automatiquement des Epics, User Stories et tâches.
- Organiser les tâches selon une structure Agile.
- Classifier individuellement la complexité de chaque tâche avec un modèle de Machine Learning.
- Présenter les résultats dans une interface web.

## 2. Fonctionnalités principales

### 2.1 Génération intelligente du backlog

À partir d'une description de projet, Orchestrix produit une structure organisée :

```text
Project
 ├── Epic 1
 │    ├── User Story 1
 │    │    ├── Task 1
 │    │    ├── Task 2
 │    │    └── Task 3
 │    └── User Story 2
 │         ├── Task 1
 │         └── Task 2
 │
 └── Epic 2
      └── User Story 1
           ├── Task 1
           └── Task 2
```

Chaque tâche possède notamment :
- Un titre.
- Une description.
- Un type de tâche.
- Des critères d'acceptation associés au contexte de la User Story.
- Des informations de classification.

### 2.2 Recherche et exploitation des preuves

Orchestrix exploite une approche de recherche augmentée par récupération de connaissances (RAG).

Le processus comprend :
1. La collecte des sources documentaires.
2. Le nettoyage et la préparation des données.
3. La segmentation des documents.
4. La recherche de passages pertinents.
5. L'intégration des éléments récupérés dans le contexte de génération.

Les preuves permettent d'enrichir le contexte fourni au modèle de langage.

### 2.3 Agent IA

L'agent orchestre les différentes étapes de traitement :

- Analyse du besoin utilisateur.
- Préparation du contexte.
- Exploitation des preuves.
- Génération du backlog.
- Nettoyage et validation de la structure.
- Classification de la complexité.
- Production du résultat final.

### 2.4 Classification intelligente de la complexité

Orchestrix intègre **PlanAgent**, un service de Machine Learning indépendant hébergé sur Kaggle.

PlanAgent utilise des représentations textuelles MPNet et plusieurs classifieurs pour déterminer la classe de complexité d'une tâche.

Chaque tâche est évaluée indépendamment à partir de son titre et de sa description.

Les quatre classes disponibles sont :

| Classe | Signification |
|---|---|
| Faible | Travail simple et limité |
| Moyenne | Travail nécessitant plusieurs étapes |
| Elevee | Travail complexe nécessitant une analyse approfondie |
| Tres_elevee | Travail très complexe impliquant plusieurs composants ou difficultés techniques |

La classification est textuelle : Orchestrix n'utilise pas de points numériques de complexité pour cette fonctionnalité.

Le service expose notamment les endpoints :

- `GET /health` : vérification de l'état du modèle.
- `POST /predire` : classification d'une tâche.
- `POST /predire_lot` : classification de plusieurs tâches.

L'intégration s'effectue via le module `orchestrix/complexite.py`.

---

## 3. Architecture du projet

```text
                    UTILISATEUR
                         |
                         v
                 INTERFACE WEB
                         |
                         v
                   ORCHESTRIX
                         |
              +----------+----------+
              |          |           |
              v          v           v
           Analyse    Recherche    Agent IA
           du besoin  de preuves   / LLM
              |          |           |
              +----------+-----------+
                         |
                         v
                 Génération du plan
                         |
                         v
                 Nettoyage / Validation
                         |
                         v
                  Classification
                         |
                         v
                     PLANAGENT
                         |
                  API REST / HTTPS
                         |
                         v
                  Modèle ML MPNet
                         |
                         v
               Classes de complexité
                         |
                         v
                 Backlog final JSON
                         |
                         v
                  Interface Orchestrix
```

### Modules principaux

| Module | Responsabilité |
|---|---|
| `orchestrix/agent.py` | Orchestration de l'agent IA et génération du backlog |
| `orchestrix/complexite.py` | Communication avec l'API PlanAgent et récupération des classifications |
| `orchestrix/server.py` | Serveur HTTP et interface web |
| `orchestrix/gestion.py` | Gestion et exploitation des tâches |
| `orchestrix/config.py` | Configuration de l'application |

---

## 4. Technologies utilisées

| Technologie | Utilisation |
|---|---|
| Python | Développement backend |
| FastAPI | API du service PlanAgent |
| MPNet | Représentation sémantique des tâches |
| Scikit-learn | Classification Machine Learning |
| Groq / LLM | Génération et analyse du backlog |
| RAG | Recherche augmentée par récupération |
| Docker | Conteneurisation des services |
| Cloudflare Tunnel | Exposition de l'API PlanAgent |
| Kaggle | Hébergement et exécution du modèle ML |

---

## 5. Installation et lancement

### Prérequis

- Python 3.
- Docker et Docker Compose (pour le déploiement conteneurisé).
- Une connexion Internet pour accéder aux services externes.
- Un accès à l'API LLM configurée dans le projet.

### Cloner le projet

```bash
git clone <URL_DU_DEPOT>
cd orchestrix
```

### Installer les dépendances

Utiliser le fichier de dépendances fourni avec le projet :

```bash
pip install -r requirements.txt
```

### Lancer Orchestrix localement

```bash
python3 -m orchestrix --ui --port 8403
```

Puis ouvrir :

```text
http://localhost:8403
```

### Lancer avec Docker

Les services Docker actuellement utilisés dans l'environnement comprennent :

- Orchestrix Platform : port `8402`.
- Service de modèle local historique : port `8500`.

Pour lancer les services, utiliser le fichier Compose fourni dans le dépôt.

---

## 6. Configuration de PlanAgent

Pour connecter Orchestrix au service PlanAgent hébergé sur Kaggle, configurer les variables d'environnement :

```bash
export URL_MODELE="https://VOTRE_TUNNEL.trycloudflare.com"
export DELAI_MODELE="300"
```

Lancer ensuite Orchestrix :

```bash
python3 -u -m orchestrix --ui --port 8403
```

Vérifier la disponibilité du modèle :

```bash
curl "$URL_MODELE/health"
```

Le service doit retourner un état `ok` et indiquer que le modèle est chargé.

**Important :** le tunnel Cloudflare dépend de la session Kaggle active. Son adresse peut changer lors de la création d'un nouveau tunnel. L'API de test actuelle ne doit pas être considérée comme un service public sécurisé.

---

## 7. Format de sortie

Orchestrix produit un backlog structuré au format JSON.

Exemple simplifié :

```json
{
  "epics": [
    {
      "title": "Gestion des utilisateurs",
      "stories": [
        {
          "title": "Authentification",
          "tasks": [
            {
              "title": "Créer le formulaire de connexion",
              "description": "Développer le formulaire utilisateur.",
              "complexite_classe": "Faible"
            },
            {
              "title": "Développer le mécanisme de sécurité",
              "description": "Implémenter les contrôles de sécurité.",
              "complexite_classe": "Elevee"
            }
          ]
        }
      ]
    }
  ]
}
```

Chaque tâche possède sa propre classification.

---

## 8. Structure du dépôt

```text
orchestrix/
│
├── orchestrix/
│   ├── __init__.py
│   ├── __main__.py
│   ├── agent.py
│   ├── complexite.py
│   ├── config.py
│   ├── gestion.py
│   ├── server.py
│   └── ...
│
├── out/
│   └── plan-*.json
│
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

La structure exacte peut varier selon la version du projet.

---

## 9. Perspectives d'évolution

Les évolutions possibles comprennent :

- Amélioration de la qualité des classifications.
- Évaluation du modèle sur des backlogs réels.
- Amélioration de la recherche documentaire.
- Ajout de mécanismes de suivi de la qualité des preuves.
- Amélioration de l'expérience utilisateur.
- Déploiement sécurisé et permanent de PlanAgent.
- Tests automatisés de l'intégration entre Orchestrix et PlanAgent.

---

## 10. Auteur et projet

**Projet :** Orchestrix  
**Domaine :** Intelligence artificielle, Machine Learning, Agile Project Management et RAG  
**Objectif :** Automatiser la transformation des besoins logiciels en backlogs structurés et enrichis par l'intelligence artificielle.

---


