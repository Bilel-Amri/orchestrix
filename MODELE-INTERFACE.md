# Le contrat exact entre votre modèle et Orchestrix

Tout ce qui suit est le **minimum à respecter**. Si votre modèle rend autre
chose que ce qui est décrit ici, il faut soit l'adapter, soit me le dire.

---

## Ce que Orchestrix envoie à votre modèle

Une liste de tâches, chacune avec **deux chaînes** :

```json
POST http://modele:8500/predire_lot
{"taches": [
  {"title": "Créer la page de connexion",
   "body":  "Formulaire email et mot de passe, validation côté client, message d'erreur explicite."},
  {"title": "Migrer la base de données",
   "body":  "Reprise des schémas existants, script réversible, sauvegarde préalable."}
]}
```

- `title` = le titre de la tâche (`title` en interne) ;
- `body` = sa **description** (le champ `description` du plan).

Côté service, les deux sont concaténés en `title + " " + body` avant d'être
donnés à votre modèle. C'est ce que vous avez décrit comme features.

## Ce que votre modèle doit rendre

Un entier **de 1 à 5** par tâche, dans le même ordre.

| Valeur | Sens conventionnel |
|---|---|
| 1 | trivial — quelques lignes, sans dépendance |
| 2 | facile |
| 3 | moyen — un module, des tests |
| 4 | difficile — plusieurs composants |
| 5 | critique — architecture, migration, sécurité transverse |

```json
{"predictions": [{"complexite": 2}, {"complexite": 4}]}
```

Si votre modèle rend autre chose, deux adaptations sont déjà prévues :

| Votre sortie | Ce que le service en fait |
|---|---|
| classes nommées (`"facile"`, `"critique"`, `"moyen"`) | converties en 1-5 par une table |
| probabilités ou score continu | **non géré** — à convertir avant, ou dites-le-moi |

> ⚠️ **Le point à décider ensemble : la valeur prédite signifie-t-elle des
> POINTS (1 à 5, comme le story points d'une tâche) ou une CLASSE de
> complexité ?** Les deux marchent pour l'affichage, mais le total d'une story
> additionne les valeurs. Si votre modèle prédit une classe, il faut décider
> si la classe 4 vaut 4 points ou, par exemple, 8 points (Fibonacci).

## Où va le fichier

```
orchestrix/
└── service_modele/
    └── modele/
        └── model_bundle.joblib      ← VOTRE fichier, ici
```

Le service accepte trois formes d'artefact :

1. un `Pipeline` complet (vectoriseur + classifieur) ;
2. un dictionnaire `{"vectorizer": ..., "model": ...}` (les clés
   `vectoriseur`, `tfidf`, `features`, `modele`, `classifier`, `estimator`
   sont aussi reconnues) ;
3. n'importe quel objet exposant `.predict(liste_de_textes)`.

## Le seul piège réel : la version de scikit-learn

Un artefact `.joblib` n'est pas portable entre versions de scikit-learn. Si le
service utilise 1.6 et que l'entraînement a utilisé 1.3, vous obtiendrez au
mieux des prédictions fausses, au pire un plantage au chargement.

Vérification en une commande, une fois le service lancé :

```bash
curl -s localhost:8500/sante
```

```json
{"statut": "pret", "version": "1.0.0", "scikit_learn": "1.6.1", ...}
```

Comparez `scikit_learn` avec la version qui a produit votre fichier. Si elles
diffèrent, épinglez la bonne version dans `service_modele/requirements.txt` :

```
scikit-learn==1.3.2
```

La version d'entraînement se lit dans votre `config.json` ou, à défaut, en
regardant la version utilisée par votre script d'entraînement.

## Si vous n'avez pas de variable `body`

Le plan d'Orchestrix fournit toujours une description, même courte. Si votre
modèle a été entraîné sans `body`, deux options :

- envoyer `body: ""` (le service accepte, la prédiction reposera sur le
  titre seul) ;
- ou réentraîner avec le titre et la description des tâches déjà générées
  par Orchestrix, qui sont dans `out/*.json` — c'est la meilleure source,
  puisque ce sont exactement les tâches à prédire.
