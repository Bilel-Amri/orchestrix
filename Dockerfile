# Image de la plateforme Orchestrix.
# Elle n'installe AUCUNE dépendance : la bibliothèque standard suffit.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PORT=8402 \
    URL_MODELE=http://modele:8500

WORKDIR /app

COPY pyproject.toml requirements.txt README.md ./
COPY orchestrix /app/orchestrix
COPY _page_pro.html /app/_page_pro.html

# utilisateur non privilégié : le serveur n'écrit que dans out/ et donnees/
RUN useradd -m orchestrix && mkdir -p /app/out /app/donnees \
    && chown -R orchestrix:orchestrix /app
USER orchestrix

EXPOSE 8402

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
    CMD python -c "import urllib.request; \
urllib.request.urlopen('http://127.0.0.1:8402/api/etat', timeout=2)"

CMD ["python", "-m", "orchestrix", "--ui", "--no-open"]
