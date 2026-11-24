# Image du serveur MCP. Volontairement minimale : bibliothèque standard
# seulement, plus le code de la plateforme pour lire les plans et joindre le
# service de modèle.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    ORCHESTRIX_RACINE=/app \
    ORCHESTRIX_OUT=/app/out \
    URL_MODELE=http://modele:8500

WORKDIR /app

COPY orchestrix /app/orchestrix
COPY mcp_complexite /app/mcp_complexite
COPY pyproject.toml /app/pyproject.toml

# Transport stdio : le conteneur est lancé par le client MCP avec -i.
ENTRYPOINT ["python", "/app/mcp_complexite/serveur.py"]
