# Commencer ici — trois réponses simples

## 1. Est-ce que MCP est obligatoire ?

**Non. MCP est totalement facultatif.**

| Ce que vous voulez | MCP nécessaire ? |
|---|---|
| Générer des plans dans l'interface Orchestrix | ❌ non |
| Que la complexité des tâches vienne de **votre modèle** | ❌ non — c'est le *service du modèle* qui s'en charge |
| Poser des questions à un agent (Claude, Cursor…) sur vos plans | ✅ oui, c'est là et seulement là que MCP sert |

Autrement dit : **le modèle n'a pas besoin de MCP pour être utilisé**. MCP est
un troisième étage, optionnel, qui sert à parler de vos plans avec un agent
conversationnel. Si vous ne l'utilisez pas, ignorez complètement le dossier
`mcp_complexite/`.

```
[ plateforme Orchestrix ]  ──HTTP──▶  [ service du modèle ]      ← utile
[ agent conversationnel ]  ──MCP───▶  [ plans + complexité ]     ← facultatif
```

## 2. Quel fichier, où ?

Votre fichier s'appelle **`model_bundle.joblib`** (vous l'avez : c'est celui de
`planagent_model`). Il se copie dans le dossier **`service_modele/modele/`**.

```bash
cd chemin/vers/orchestrix
cp ~/Téléchargements/planagent_model/model_bundle.joblib service_modele/modele/
```

C'est le **seul fichier à déplacer**. `config.json` et le dossier
`embedding_model` ne sont pas utilisés par Orchestrix.

## 3. Qu'est-ce que j'installe ?

### Option A — la plus simple, sans Docker (recommandée pour essayer)

```bash
cd chemin/vers/orchestrix
./demarrer.sh
```

Le script fait tout : il vérifie que le fichier est là, installe scikit-learn
si besoin (une fois), démarre le service du modèle, puis l'interface.
Ouvrez **http://localhost:8402**.

À la fin : `Ctrl+C` arrête les deux.

### Option B — Docker (si vous préférez les conteneurs)

```bash
cd chemin/vers/orchestrix
cp ~/Téléchargements/planagent_model/model_bundle.joblib service_modele/modele/
cp .env.exemple .env && nano .env     # mettre votre clé Groq
docker compose up --build
```

Commandes détaillées, ports, journaux, dépannage : **DOCKER.md**.

Deux conteneurs démarrent : `modele` (votre modèle, port 8500) et
`plateforme` (Orchestrix, port 8402). Le troisième, `mcp`, n'est pas lancé
ici — il se lance à la demande, uniquement si vous en voulez.

### Option C — sans le modèle du tout

```bash
python3 -m orchestrix --ui
```

Rien à installer, aucune dépendance. La complexité des tâches est alors
calculée par les règles internes (type de tâche + longueur de la description).
C'est le fonctionnement d'origine, et ça reste valable.

## Récapitulatif de ce qui s'installe où

| Élément | À installer ? | Où |
|---|---|---|
| Orchestrix (la plateforme) | **rien** | — |
| scikit-learn, joblib | oui, **seulement** pour le service du modèle | `service_modele/requirements.txt` |
| `model_bundle.joblib` | oui, votre fichier | `service_modele/modele/` |
| Docker | facultatif | remplace l'installation de scikit-learn |
| serveur MCP | facultatif | `mcp_complexite/serveur.py` |

## Vérifier que ça marche

```bash
curl -s localhost:8500/sante
```

Réponse attendue :

```json
{"statut": "pret", "version": "1.0.0", "scikit_learn": "1.6.1", ...}
```

Puis une prédiction à la main :

```bash
curl -s -X POST localhost:8500/predire \
  -H 'Content-Type: application/json' \
  -d '{"title":"Créer la page de connexion","body":"formulaire email mot de passe"}'
```

```json
{"complexite": 2, "echelle": "1-5", "indice": 0.25}
```

Si `complexite` change selon le texte que vous envoyez, le modèle est branché.
Générez un plan : dans le tableau de bord, les charges prédites portent un **ⓜ**.

## Et si MCP m'intéresse plus tard ?

Il suffit d'ajouter ce bloc dans la configuration de votre client MCP
(Claude Desktop, Cursor…) :

```json
{
  "mcpServers": {
    "orchestrix": {
      "command": "python3",
      "args": ["/chemin/vers/orchestrix/mcp_complexite/serveur.py"],
      "env": {
        "URL_MODELE": "http://localhost:8500",
        "ORCHESTRIX_OUT": "/chemin/vers/orchestrix/out"
      }
    }
  }
}
```

Puis redémarrez le client. L'agent voit cinq outils : `etat_service`,
`lister_plans`, `lire_plan`, `predire_complexite`, `complexite_plan`.

Rien à installer pour ça : le serveur MCP n'utilise que la bibliothèque
standard de Python.
