# Lancer Orchestrix

Guide de démarrage, de A à Z. Comptez **5 minutes**.

---

## Ce qu'il faut

| Élément | Détail |
|---|---|
| Python | version 3.9 ou plus récente (testé sur 3.13) |
| Une clé Groq | gratuite, sur https://console.groq.com/keys |
| Une connexion | pour interroger les 9 sources publiques |
| Paquets à installer | **aucun** |

---

## Étape 1 — Récupérer le dossier

Téléchargez **`orchestrix.zip`** puis, dans un terminal :

```bash
unzip -o orchestrix.zip
cd orchestrix
```

⚠️ Toutes les commandes suivantes se lancent **depuis ce dossier**, celui qui
contient `pyproject.toml`. Sinon Python répond `No module named orchestrix`.

---

## Étape 2 — Rien à installer

Orchestrix n'utilise **que la bibliothèque standard** de Python.
Pas de `pip install`, pas de conflit de versions, rien à télécharger.

Si vous préférez tout de même un environnement isolé :

```bash
python3 -m venv .venv
source .venv/bin/activate      # Windows : .venv\Scripts\activate
```

---

## Étape 3 — Mettre la clé Groq

**Linux / macOS :**

```bash
export GROQ_API_KEY=gsk_votre_cle
```

**Windows (PowerShell) :**

```powershell
$env:GROQ_API_KEY="gsk_votre_cle"
```

Facultatif mais recommandé, sinon GitHub limite à 60 lectures par heure :

```bash
export GITHUB_TOKEN=ghp_votre_jeton
```

Vérifier que la clé est reconnue :

```bash
python -m orchestrix --models
```

---

## Étape 4 — Lancer

### L'interface graphique (recommandé)

```bash
python -m orchestrix --ui
```

Le navigateur s'ouvre sur **http://127.0.0.1:8402**.

Variantes utiles :

| Commande | Effet |
|---|---|
| `python -m orchestrix --ui --no-open` | ne pas ouvrir le navigateur |
| `python -m orchestrix --ui --port 8500` | changer de port |
| `Ctrl+C` dans le terminal | arrêter le serveur |

### En ligne de commande (sans interface)

```bash
python -m orchestrix --brief "Application web de gestion de stock pour une PME agroalimentaire, avec alertes de rupture, inventaires et tableau de bord."
```

Le plan est écrit dans le dossier `out/` et affiché dans le terminal.

---

## Le parcours dans l'interface

1. **Brief** — écrire la demande, puis « Générer le plan » (compter 30 à 90 secondes).
2. **Synthèse** — relire le plan.
3. **Validation** — approuver, ou rejeter avec un motif : un autre plan est alors généré.
4. **Espace de travail** — créer le projet et composer l'équipe.
5. **Exécution** — affecter les tâches, changer les statuts, commenter.
6. **Jira** — publier les tickets, puis relire l'état.

---

## Problèmes fréquents

| Message | Cause | Solution |
|---|---|---|
| `No module named orchestrix` | mauvais dossier | `cd orchestrix` puis relancer |
| `Address already in use` | le port 8402 est pris | `--port 8500`, ou fermer l'ancien serveur |
| `Clé Groq absente` | variable non définie | refaire l'étape 3, ou saisir la clé dans **Réglages** |
| `externally-managed-environment` | vous avez lancé un `pip install` | inutile : rien à installer |
| Génération très lente | sources lentes | c'est normal au premier lancement ; ensuite le cache de 30 min accélère |

---

## Vérifier que tout fonctionne

```bash
python test_plateforme.py
```

Résultat attendu : `TOUT PASSE (35 contrôles)`.
