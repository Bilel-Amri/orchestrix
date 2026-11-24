# Intégrer le modèle de complexité à Orchestrix

Votre modèle prend **`title` et `body`** d'une tâche et rend une **complexité**.
Voici comment il se branche, et pourquoi c'est découpé en trois conteneurs.

```
┌─────────────────────┐   HTTP    ┌──────────────────────┐
│  plateforme         │──────────▶│  service du modèle   │
│  Orchestrix  :8402  │  /predire │  sklearn    :8500    │
│  (aucune dépendance)│◀──────────│  model_bundle.joblib │
└─────────┬───────────┘           └──────────────────────┘
          │ écrit out/*.json                  ▲
          ▼                                   │ HTTP
┌─────────────────────┐                       │
│  serveur MCP        │───────────────────────┘
│  (stdio, à la demande)│
└─────────────────────┘
```

---

## 1. Déposer le modèle

Copiez `model_bundle.joblib` dans `service_modele/modele/`. C'est tout : le
service le charge au démarrage et annonce sa version sur `/sante`.

Trois formes d'artefact sont acceptées :

| Forme | Exemple |
|---|---|
| pipeline complet | `Pipeline([("tfidf", TfidfVectorizer()), ("clf", LogisticRegression())])` |
| dictionnaire | `{"vectorizer": ..., "model": ...}` (clés `vectoriseur`, `tfidf`, `features`, `modele`, `classifier`, `estimator` reconnues) |
| objet quelconque | n'importe quoi qui expose `.predict(liste_de_textes)` |

Le texte envoyé est **`title + " " + body`**, dans cet ordre — c'est la
concaténation utilisée à l'entraînement.

> ⚠️ **La version de scikit-learn doit être celle de l'entraînement.** Un
> décalage produit des prédictions fausses ou un plantage au chargement.
> `/sante` affiche la version chargée : comparez-la avec celle qui a produit
> l'artefact. Si la vôtre diffère, épinglez-la dans
> `service_modele/requirements.txt`.

## 2. Lancer

```bash
# tout, en trois conteneurs
export GROQ_API_KEY=gsk_...
docker compose up --build

# ou seulement le modèle, à côté d'une plateforme lancée à la main
cd service_modele && docker build -t orchestrix-modele . && \
  docker run -p 8500:8500 -v "$PWD/modele:/modele:ro" orchestrix-modele

cd .. && URL_MODELE=http://localhost:8500 python -m orchestrix --ui
```

Vérification en deux commandes :

```bash
curl -s localhost:8500/sante
curl -s -X POST localhost:8500/predire \
     -H 'Content-Type: application/json' \
     -d '{"title":"Créer la page de connexion","body":"formulaire email mot de passe"}'
# → {"complexite": 2, "echelle": "1-5", "indice": 0.25}
```

## 3. Ce que ça change dans le plan

Chaque tâche reçoit trois champs au lieu d'un :

| Champ | Sens |
|---|---|
| `charge` | la complexité retenue, de 1 à 5 |
| `charge_origine` | `modele` ou `regles` — jamais de confusion possible |
| `charge_regles` | l'ancienne estimation, conservée pour comparaison |

Les totaux de story (`points`) sont recalculés en conséquence. Le champ
`metadonnees.complexite` du plan indique l'origine, la moyenne et la latence.

**Si le service ne répond pas**, la génération ne s'arrête pas et ne ralentit
pas : chaque tâche garde son estimation par règles (`charge_origine:
"regles"`), et la raison est écrite dans les métadonnées. Un seul appel de
lot, délai de 2 s (`DELAI_MODELE`).

## 4. Le serveur MCP

Il expose le modèle à un agent conversationnel, en JSON-RPC sur
l'entrée/sortie standard — le transport « stdio » du protocole MCP.

```bash
# à la main
URL_MODELE=http://localhost:8500 python mcp_complexite/serveur.py
```

Déclaration dans un client MCP (Claude Desktop, Cursor…) :

```json
{
  "mcpServers": {
    "orchestrix-complexite": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "--network", "orchestrix_default",
               "-e", "URL_MODELE=http://modele:8500",
               "-v", "/chemin/vers/orchestrix/out:/app/out:ro",
               "orchestrix-mcp"],
      "env": {}
    }
  }
}
```

Sans Docker :

```json
{
  "mcpServers": {
    "orchestrix-complexite": {
      "command": "python",
      "args": ["/chemin/vers/orchestrix/mcp_complexite/serveur.py"],
      "env": { "URL_MODELE": "http://localhost:8500",
               "ORCHESTRIX_OUT": "/chemin/vers/orchestrix/out" }
    }
  }
}
```

Cinq outils exposés :

| Outil | Réponse |
|---|---|
| `etat_service` | le modèle répond-il, quelle version, quel artefact |
| `lister_plans` | les plans générés, du plus récent au plus ancien |
| `lire_plan` | clé, titre, épic, story, type, charge et origine |
| `predire_complexite` | complexité d'une ou plusieurs tâches (titre + corps) |
| `complexite_plan` | complexité de **toutes** les tâches d'un plan + moyenne |

Une question comme « quelle est la complexité moyenne du dernier plan, et
quelles tâches dépassent 3 ? » se répond avec `complexite_plan`, sans que
l'agent ait à connaître ni URL ni format JSON.

## 5. Réglages

| Variable | Où | Défaut | Rôle |
|---|---|---|---|
| `URL_MODELE` | plateforme, MCP | *(vide)* | sans elle, aucune requête : les règles internes servent |
| `DELAI_MODELE` | plateforme | `2.0` | délai maximal ; au-delà, repli silencieux |
| `JETON_MODELE` | plateforme | *(vide)* | jeton partagé, si le service est exposé |
| `DOSSIER_MODELE` | service | `/modele` | dossier de l'artefact |
| `FICHIER_MODELE` | service | `model_bundle.joblib` | nom du fichier |
| `JETON_SERVICE` | service | *(vide)* | exige `Authorization: Bearer …` |
| `VERSION_MODELE` | service | `1.0.0` | affichée par `/sante` |
| `ORCHESTRIX_OUT` | MCP | `./out` | où lire les plans |

## 6. Ce qui n'est pas fait

- **Le modèle n'est pas réentraîné ici.** Le service sert l'artefact tel quel.
- **Aucune base de données.** Les plans restent des fichiers JSON dans `out/`.
- **Pas de GPU, pas de file d'attente.** Une prédiction prend quelques
  millisecondes ; le service répond en direct.
- **Le conteneur MCP n'écoute pas sur un port** : c'est le propre du transport
  stdio. Si vous préférez un serveur MCP en HTTP, dites-le — le code a une
  fonction `traiter()` qui se branche sur n'importe quel transport.
