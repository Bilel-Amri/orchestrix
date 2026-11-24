# Image du service de prédiction de complexité.
# Séparée de la plateforme : elle pèse plusieurs centaines de Mo, la
# plateforme n'a besoin de rien.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PORT=8500 \
    HOTE=0.0.0.0 \
    DOSSIER_MODELE=/modele

WORKDIR /app

# Les dépendances d'abord : cette couche est réutilisée tant que le fichier

# ne change pas, même si le code du service change.
COPY requirements.txt .
COPY wheelhouse /wheels

RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt
COPY serveur.py .

# L'artefact est monté au démarrage (voir docker-compose) pour pouvoir le
# remplacer sans reconstruire l'image.
VOLUME ["/modele"]
EXPOSE 8500

HEALTHCHECK --interval=30s --timeout=3s --start-period=20s \
    CMD python -c "import urllib.request,os; \
urllib.request.urlopen(f\"http://127.0.0.1:{os.environ['PORT']}/sante\", timeout=2)"

CMD ["python", "serveur.py"]
