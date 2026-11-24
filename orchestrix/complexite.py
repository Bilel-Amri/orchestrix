"""Client HTTP du modèle PlanAgent hébergé sur Kaggle.

Chaque tâche reçoit une classe textuelle indépendante.
Aucun point, score ou moyenne de complexité n'est utilisé.
"""

from __future__ import annotations

import json
import os
import time

from . import httpclient as requests


# Configuration
URL = os.environ.get("URL_MODELE", "").rstrip("/")
DELAI = float(os.environ.get("DELAI_MODELE", "15.0"))
JETON = ''

CLASSES_AUTORISEES = {
    "Faible",
    "Moyenne",
    "Elevee",
    "Tres_elevee",
}


def disponible() -> bool:
    """Vérifie si l'URL du modèle est configurée."""
    return bool(URL)


def _entetes() -> dict:
    """Construit les en-têtes HTTP."""
    entetes = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    if JETON:
        entetes["Authorization"] = f"Bearer {JETON}"

    return entetes


def sante(delai: float | None = None) -> dict:
    """Vérifie la disponibilité de l'API PlanAgent."""

    if not URL:
        return {
            "actif": False,
            "raison": "URL_MODELE non définie",
        }

    try:
        reponse = requests.get(
            f"{URL}/health",
            headers=_entetes(),
            timeout=delai or DELAI,
        )

        try:
            donnees = reponse.json() or {}
        except ValueError:
            donnees = {}

        return {
            **donnees,
            "actif": reponse.status_code == 200,
        }

    except requests.RequestException as exc:
        return {
            "actif": False,
            "raison": str(exc)[:160],
        }


def predire_lot(taches: list[dict]) -> list[dict]:
    """Prédit une classe textuelle pour chaque tâche."""

    if not URL or not taches:
        return []

    entrees = []

    for tache in taches:
        if not isinstance(tache, dict):
            print("Tâche invalide : dictionnaire attendu.", flush=True)
            return []

        entrees.append({
            "title": str(tache.get("title", "")),
            "body": str(tache.get("body", "")),
        })

    debut = time.perf_counter()

    try:
        reponse = requests.post(
            f"{URL}/predire_lot",
            headers=_entetes(),
            timeout=DELAI,
            json={"taches": entrees},
        )

        if reponse.status_code != 200:
            print(
                f"PlanAgent : HTTP {reponse.status_code}",
                flush=True,
            )
            return []

        donnees = reponse.json()

    except requests.RequestException as exc:
        print(
            f"PlanAgent inaccessible : {str(exc)[:160]}",
            flush=True,
        )
        return []

    except (ValueError, TypeError) as exc:
        print(
            f"Réponse PlanAgent invalide : {str(exc)[:160]}",
            flush=True,
        )
        return []

    duree = round((time.perf_counter() - debut) * 1000)

    if not isinstance(donnees, dict):
        print("Réponse JSON incorrecte.", flush=True)
        return []

    predictions = donnees.get("predictions")

    if not isinstance(predictions, list):
        print("Champ predictions absent ou invalide.", flush=True)
        return []

    if len(predictions) != len(entrees):
        print(
            f"Nombre de prédictions incorrect : "
            f"{len(predictions)} pour {len(entrees)} tâches.",
            flush=True,
        )
        return []

    sortie = []

    for index, prediction in enumerate(predictions):
        if not isinstance(prediction, dict):
            print(f"Prédiction invalide à la position {index}.", flush=True)
            return []

        classe = prediction.get("complexite_classe")

        if classe not in CLASSES_AUTORISEES:
            print(
                f"Classe inconnue à la position {index} : {classe!r}",
                flush=True,
            )
            return []

        sortie.append({
            "complexite_classe": classe,
            "origine": "modele",
            "latence_ms": duree,
        })

    return sortie


def diagnostiquer() -> str:
    """Retourne un résumé de l'état du service PlanAgent."""

    if not URL:
        return "PlanAgent : URL_MODELE non définie"

    etat = sante()

    if etat.get("actif"):
        version = etat.get("version", "?")
        return f"PlanAgent : modèle disponible (version {version})"

    raison = (
        etat.get("raison")
        or etat.get("erreur")
        or "service indisponible"
    )

    return f"PlanAgent : indisponible ({raison})"


def _json_dumps(d: dict) -> str:
    """Utilitaire JSON utilisé par les tests."""
    return json.dumps(d, ensure_ascii=False)
