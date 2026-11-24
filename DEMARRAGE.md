# Démarrage — 4 étapes

## 1. Décompresser et entrer dans le dossier

```bash
unzip -o orchestrix.zip
cd orchestrix
```

Toutes les commandes qui suivent se lancent **depuis ce dossier `orchestrix/`**
(celui qui contient `pyproject.toml` et le sous-dossier `orchestrix/`).
Si vous lancez `python -m orchestrix` depuis un autre dossier, vous obtiendrez
`No module named orchestrix`.

## 2. Aucune installation nécessaire

Orchestrix n'utilise **que la bibliothèque standard** de Python.
Il n'y a rien à installer.

```bash
pip install -r requirements.txt   # facultatif, ne fait rien
```

Si vous préférez un environnement isolé :

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows : .venv\Scripts\activate
```


## 3. Mettre la clé Groq

```bash
export GROQ_API_KEY=gsk_votre_cle      # Windows PowerShell : $env:GROQ_API_KEY="gsk_..."
```

Clé gratuite sur https://console.groq.com/keys

Facultatif mais recommandé, sinon GitHub plafonne à 60 lectures/heure :

```bash
export GITHUB_TOKEN=ghp_votre_jeton
```

Pour vérifier que la clé est bien vue, et voir les modèles disponibles :

```bash
python -m orchestrix --models
```

## 4. Lancer

### L'interface graphique

```bash
python -m orchestrix --ui
```

Le navigateur s'ouvre sur `http://127.0.0.1:8402`. Écrivez le brief, cliquez
sur **Générer**. Le journal des 9 étapes défile, puis le backlog s'affiche.
Tout est en français, même si vous écrivez le brief en anglais.

- `python -m orchestrix --ui --no-open` : ne pas ouvrir le navigateur
- `python -m orchestrix --ui --port 8500` : autre port
- `Ctrl+C` dans le terminal arrête le serveur
- pendant la génération, l'écran affiche seulement « Génération en cours » ;
  le plan apparaît une fois complet

### L'agent en ligne de commande

```bash
python -m orchestrix --brief "Application de gestion de bibliothèque scolaire avec prêt de livres."
```

Résultat à l'écran + deux fichiers dans `out/` : `plan-<date>.json` et
`plan-<date>.md`.

Options utiles :

```bash
python -m orchestrix --brief "..." --model openai/gpt-oss-120b
python -m orchestrix --brief-file mon-brief.txt
python -m orchestrix --brief "..." --out resultats
python -m orchestrix --brief "..." --quiet           # sans le détail des étapes
```

---

## Ce qui doit s'afficher si tout va bien

```
✅ Groq · modèle openai/gpt-oss-120b

① analyse du besoin …
② requêtes : …
③ collecte des 9 sources …
④ pertinence : 20 documents retenus sur 27
⑤ recherche : 81 passages → 12 retenus
⑥ extraction …
⑦ validation : 52 fonctionnalités
⑧ plan agile …
✅ 7 épics · 22 user stories · 108 tâches
```

Durée normale : **1 à 4 minutes**. C'est long parce que neuf sources web sont
interrogées en parallèle, pas parce que c'est bloqué.

## Les erreurs courantes

| Message | Cause | Solution |
|---|---|---|
| `❌ Clé Groq absente.` | `GROQ_API_KEY` non définie | refaire l'étape 3, dans le **même** terminal |
| `❌ Clé Groq refusée (401)` | clé fausse ou révoquée | créer une nouvelle clé |
| `No module named orchestrix` | mauvais dossier | `cd orchestrix` avant de lancer |
| `Address already in use` | port 8402 déjà pris | `--port 8500` |
| `413` | brief trop long | raccourcir le brief |
| collecte vide sur GitHub | quota épuisé | définir `GITHUB_TOKEN` |

## Langue

Tout sort en **français**, même si vous écrivez le brief en anglais. Pour
changer ce comportement :

```bash
ORCHESTRIX_FRANCAIS=0          python -m orchestrix --brief "..."   # plan dans la langue du brief
ORCHESTRIX_TRADUIRE_PREUVES=0  python -m orchestrix --brief "..."   # preuves citées telles quelles
```

Pour la trace complète d'une erreur inattendue :

```bash
ORCHESTRIX_DEBUG=1 python -m orchestrix --brief "..."
```
