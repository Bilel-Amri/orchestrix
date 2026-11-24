Déposez ici l'artefact :

    service_modele/modele/model_bundle.joblib

Le serveur charge ce fichier au démarrage. Formes acceptées :

1. un pipeline complet (`TfidfVectorizer` + `LogisticRegression`, `Pipeline`) ;
2. un dictionnaire `{"vectorizer": ..., "model": ...}` — les clés `vectoriseur`,
   `tfidf`, `features`, `modele`, `classifier`, `estimator` sont aussi reconnues ;
3. tout objet exposant `.predict(liste_de_textes)`.

Le texte envoyé au modèle est `title + " " + body`, exactement comme à
l'entraînement (features : titre et description).
