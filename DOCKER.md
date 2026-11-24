# Lancer Orchestrix avec Docker — les commandes, dans l'ordre

## Avant tout : Docker doit être installé

```bash
docker --version          # doit afficher une version
docker compose version    # doit afficher une version (v2)
```

Si l'une des deux commandes échoue, installez Docker Desktop
(https://www.docker.com/products/docker-desktop). Rien d'autre n'est
nécessaire : ni Python, ni scikit-learn, ni pip — tout est dans les images.

---

## Étape 1 — dézipper et se placer dans le dossier

```bash
unzip orchestrix.zip
cd orchestrix
```

## Étape 2 — mettre votre modèle au bon endroit

```bash
cp ~/Téléchargements/planagent_model/model_bundle.joblib service_modele/modele/
```

Vérifiez :

```bash
ls -lh service_modele/modele/
# → model_bundle.joblib
```

C'est le **seul fichier à copier**. Sans lui, Tout démarre quand même, mais la
complexité est estimée par les règles internes (et `/sante` répond `503`).

## Étape 3 — mettre votre clé Groq

```bash
cp .env.exemple .env
nano .env          # remplacez gsk_... par votre vraie clé
```

Sans clé Groq, l'interface s'ouvre mais aucune génération de plan ne fonctionne.

## Étape 4 — construire et démarrer

```bash
docker compose up --build
```

La première fois, le téléchargement des dépendances prend quelques minutes.
Les fois suivantes, quelques secondes.

Attendu :

```
orchestrix-modele  | ✓ modèle chargé depuis /modele/model_bundle.joblib
orchestrix-modele  |    scikit-learn 1.6.1
orchestrix-modele  | 🧠 service du modèle — 0.0.0.0:8500
orchestrix-platefo | 🖥  Interface Orchestrix — http://localhost:8402
```

## Étape 5 — ouvrir et vérifier

Navigateur : **http://localhost:8402**

En ligne de commande :

```bash
curl -s localhost:8500/sante
# {"statut":"pret","version":"1.0.0","scikit_learn":"1.6.1",...}

curl -s -X POST localhost:8500/predire \
  -H 'Content-Type: application/json' \
  -d '{"title":"Créer la page de connexion","body":"formulaire email mot de passe"}'
# {"complexite":2,"echelle":"1-5","indice":0.25}
```

Si le premier `curl` affiche `"statut":"indisponible"`, l'artefact n'a pas été
trouvé ou scikit-learn n'est pas de la bonne version — voir `MODELE-INTERFACE.md`.

---

## Toutes les commandes utiles

| Commande | Effet |
|---|---|
| `docker compose up --build` | construire et démarrer (premier lancement) |
| `docker compose up -d` | démarrer en arrière-plan |
| `docker compose logs -f plateforme` | suivre les journaux de l'interface |
| `docker compose logs -f modele` | suivre les journaux du modèle |
| `docker compose ps` | état des conteneurs |
| `docker compose down` | arrêter (les plans restent dans `./out`) |
| `docker compose down -v` | arrêter et **supprimer** les volumes |
| `docker compose restart plateforme` | redémarrer l'interface seule |
| `docker compose build --no-cache plateforme` | reconstruire après un changement de code |

## Changer le modèle sans reconstruire

Le dossier `service_modele/modele/` est monté dans le conteneur : remplacez le
fichier, puis

```bash
docker compose restart modele
```

## Le serveur MCP (facultatif)

Il n'est **pas** démarré par `docker compose up`. Pour l'utiliser depuis un
client MCP (Claude Desktop, Cursor…), ajoutez ceci dans la configuration du
client :

```json
{
  "mcpServers": {
    "orchestrix": {
      "command": "docker",
      "args": ["compose", "-f", "/chemin/vers/orchestrix/docker-compose.yml",
               "--profile", "mcp", "run", "--rm", "-T", "mcp"]
    }
  }
}
```

Test manuel, sans client :

```bash
docker compose --profile mcp run --rm -T mcp <<'EOF'
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}
{"jsonrpc":"2.0","id":2,"method":"tools/list"}
EOF
```

`-T` coupe l'allocation d'un terminal : sans lui, les messages JSON seraient
mélangés à l'affichage du terminal et le client MCP ne comprendrait rien.

## Changer les ports

Si 8402 ou 8500 sont déjà pris, éditez `docker-compose.yml` :

```yaml
ports:
  - "9402:8402"        # 9402 sur votre machine → 8402 dans le conteneur
```

Puis `docker compose up -d` et ouvrez `http://localhost:9402`.

## Ce que les conteneurs écrivent sur votre machine

| Dossier local | Contenu |
|---|---|
| `./out/` | les plans générés (JSON) — **conservez-les** |
| `./donnees/` | l'état de la plateforme (projet, équipe, statuts) |
| `./service_modele/modele/` | votre artefact, monté en lecture seule |

Rien d'autre ne sort des conteneurs. `docker compose down` ne touche pas à ces
dossiers.

## En cas de problème

| Symptôme | Cause probable | Solution |
|---|---|---|
| `port is already allocated` | 8402 ou 8500 déjà utilisés | changer le port (ci-dessus) |
| `/sante` répond `503` | artefact absent ou version sklearn | voir `MODELE-INTERFACE.md` |
| `ModuleNotFoundError: sklearn` dans les logs du modèle | image construite avant que `requirements.txt` ne soit complet | `docker compose build --no-cache modele` |
| L'interface affiche « clé Groq absente » | `.env` non créé ou vide | étape 3 |
| Les plans sont vides après `down` | volume monté ailleurs | vérifier `./out` |

## Sans Docker

Si Docker n'est pas disponible, la même chose tient en une commande :

```bash
./demarrer.sh
```
