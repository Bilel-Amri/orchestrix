
"""Service du modèle de complexité Orchestrix."""

from __future__ import annotations

import gzip
import json
import os
import pickle
import sys
import time
import traceback
import zlib

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


# ============================================================
# CONFIGURATION
# ============================================================

DOSSIER = Path(
    os.environ.get(
        "DOSSIER_MODELE",
        Path(__file__).parent / "modele"
    )
)

FICHIER = DOSSIER / os.environ.get(
    "FICHIER_MODELE",
    "model_bundle.joblib"
)

PORT = int(os.environ.get("PORT", "8500"))
HOTE = os.environ.get("HOTE", "0.0.0.0")
JETON = os.environ.get("JETON_SERVICE", "")
VERSION = os.environ.get("VERSION_MODELE", "1.0.0")


# ============================================================
# ETAT DU MODELE
# ============================================================

_ETAT = {
    "modele": None,
    "erreur": None,
    "charge_le": None
}


# ============================================================
# VERSION SCIKIT-LEARN
# ============================================================

def _version_sklearn():

    try:
        import sklearn
        return sklearn.__version__

    except ImportError:
        return None


# ============================================================
# CHARGEMENT DU MODELE
# ============================================================

def _charger_artefact(fichier: Path):
    """
    Charge le modèle.

    Formats pris en charge :
    - Joblib standard
    - Pickle standard
    - Pickle compressé avec zlib
    - Pickle compressé avec gzip
    """

    if not fichier.exists():
        raise FileNotFoundError(
            f"Modèle introuvable : {fichier}"
        )

    print("Lecture du fichier modèle...", flush=True)

    donnees = fichier.read_bytes()

    print(
        f"Taille du fichier : {len(donnees) / (1024 * 1024):.2f} MB",
        flush=True
    )

    # --------------------------------------------------------
    # 1. Détection et décompression ZLIB
    # --------------------------------------------------------

    try:

        donnees_decompressees = zlib.decompress(donnees)

        print(
            "Compression ZLIB détectée et décompressée.",
            flush=True
        )

        print(
            f"Taille décompressée : "
            f"{len(donnees_decompressees) / (1024 * 1024):.2f} MB",
            flush=True
        )

        donnees = donnees_decompressees

    except zlib.error:

        # Le fichier n'est pas directement compressé en zlib.
        pass

    # --------------------------------------------------------
    # 2. Détection et décompression GZIP
    # --------------------------------------------------------

    if donnees.startswith(b"\x1f\x8b"):

        donnees = gzip.decompress(donnees)

        print(
            "Compression GZIP détectée et décompressée.",
            flush=True
        )

    # --------------------------------------------------------
    # 3. Chargement du contenu PICKLE
    # --------------------------------------------------------

    try:

        modele = pickle.loads(donnees)

        print(
            "Modèle chargé avec pickle.loads().",
            flush=True
        )

        return modele

    except Exception as erreur_pickle:

        print(
            f"Chargement Pickle impossible : {erreur_pickle}",
            flush=True
        )

    # --------------------------------------------------------
    # 4. Dernier essai : JOBLIB
    # --------------------------------------------------------

    try:

        import joblib

        modele = joblib.load(fichier)

        print(
            "Modèle chargé avec joblib.load().",
            flush=True
        )

        return modele

    except Exception as erreur_joblib:

        raise RuntimeError(
            "Impossible de charger le modèle. "
            f"Erreur Joblib : {erreur_joblib}"
        )


def charger_modele():

    if _ETAT["modele"] is not None:
        return _ETAT["modele"]

    if _ETAT["erreur"] is not None:
        return None

    try:

        print("=" * 60, flush=True)
        print("CHARGEMENT DU MODELE ORCHESTRIX", flush=True)
        print("=" * 60, flush=True)

        _ETAT["modele"] = _charger_artefact(FICHIER)

        _ETAT["charge_le"] = time.strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        print(
            "MODELE CHARGE AVEC SUCCES",
            flush=True
        )

        print(
            "Type :",
            type(_ETAT["modele"]),
            flush=True
        )

        if isinstance(_ETAT["modele"], dict):

            print(
                "Clés du bundle :",
                list(_ETAT["modele"].keys()),
                flush=True
            )

        print(
            "Scikit-learn :",
            _version_sklearn(),
            flush=True
        )

        print("=" * 60, flush=True)

    except Exception as exc:

        _ETAT["erreur"] = (
            f"{type(exc).__name__} : {exc}"
        )

        print(
            "ERREUR DE CHARGEMENT :",
            _ETAT["erreur"],
            flush=True
        )

        traceback.print_exc()

    return _ETAT["modele"]


# ============================================================
# PREPARATION DU TEXTE
# ============================================================

def _texte(title: str, body: str) -> str:

    return f"{title or ''} {body or ''}".strip()


# ============================================================
# OUTILS DE PREDICTION
# ============================================================

def _premier_element(bundle, noms):

    for nom in noms:

        valeur = bundle.get(nom)

        if valeur is not None:
            return valeur

    return None


def predire(modele, taches: list[dict]) -> list[dict]:

    textes = [
        _texte(
            str(t.get("title", "")),
            str(t.get("body", ""))
        )
        for t in taches
    ]

    if not textes:
        return []

    # --------------------------------------------------------
    # CAS 1 : BUNDLE DICTIONNAIRE
    # --------------------------------------------------------

    if isinstance(modele, dict):

        vecteur = _premier_element(
            modele,
            [
                "vectorizer",
                "vectoriseur",
                "tfidf",
                "features",
                "word_vectorizer"
            ]
        )

        estimateur = _premier_element(
            modele,
            [
                "model",
                "modele",
                "classifier",
                "estimator",
                "clf"
            ]
        )

        if vecteur is not None and estimateur is not None:

            X = vecteur.transform(textes)

            brut = estimateur.predict(X)

        elif vecteur is None and estimateur is not None:

            brut = estimateur.predict(textes)

        elif hasattr(modele, "predict"):

            brut = modele.predict(textes)

        else:

            raise ValueError(
                "Structure du bundle non reconnue. "
                f"Clés disponibles : {list(modele.keys())}. "
                "Il faut identifier le vectoriseur et le classifieur."
            )

    # --------------------------------------------------------
    # CAS 2 : PIPELINE SKLEARN
    # --------------------------------------------------------

    elif hasattr(modele, "predict"):

        brut = modele.predict(textes)

    else:

        raise TypeError(
            f"Type de modèle non pris en charge : {type(modele)}"
        )

    # --------------------------------------------------------
    # CONVERSION DES RESULTATS
    # --------------------------------------------------------

    sortie = []

    for valeur, tache in zip(list(brut), taches):

        if hasattr(valeur, "item"):
            valeur = valeur.item()

        if isinstance(valeur, (int, float)):

            n = int(valeur)

            sortie.append({
                "complexite": n,
                **_libelle(n)
            })

        else:

            classe = str(valeur)

            sortie.append({
                "classe": classe,
                "complexite": _depuis_libelle(classe)
            })

    return sortie


# ============================================================
# ECHELLE DE COMPLEXITE
# ============================================================

def _libelle(n: int) -> dict:

    return {
        "echelle": "1-5",
        "indice": (n - 1) / 4 if 1 <= n <= 5 else None
    }


def _depuis_libelle(classe: str) -> int:

    table = {
        "trivial": 1,
        "facile": 2,
        "simple": 2,
        "moyen": 3,
        "medium": 3,
        "difficile": 4,
        "hard": 4,
        "critique": 5,
        "complexe": 5
    }

    return table.get(classe.strip().lower(), 3)


# ============================================================
# SERVEUR HTTP
# ============================================================

class _Handler(BaseHTTPRequestHandler):

    def log_message(self, *args):

        if os.environ.get("VERBEUX"):
            super().log_message(*args)

    def _json(self, code: int, donnees: dict):

        corps = json.dumps(
            donnees,
            ensure_ascii=False
        ).encode("utf-8")

        self.send_response(code)

        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8"
        )

        self.send_header(
            "Content-Length",
            str(len(corps))
        )

        self.end_headers()

        self.wfile.write(corps)

    def _entree(self):

        n = int(
            self.headers.get("Content-Length") or 0
        )

        return json.loads(
            self.rfile.read(n) or b"{}"
        )

    def _autorise(self):

        if not JETON:
            return True

        return (
            self.headers.get("Authorization", "")
            == f"Bearer {JETON}"
        )

    # --------------------------------------------------------
    # GET : SANTE DU SERVICE
    # --------------------------------------------------------

    def do_GET(self):

        route = self.path.split("?")[0]

        if route in ("/", "/sante", "/health"):

            modele = charger_modele()

            self._json(
                200 if modele is not None else 503,
                {
                    "statut": (
                        "pret"
                        if modele is not None
                        else "indisponible"
                    ),
                    "version": VERSION,
                    "artefact": str(FICHIER),
                    "erreur": _ETAT["erreur"],
                    "charge_le": _ETAT["charge_le"],
                    "scikit_learn": _version_sklearn(),
                    "entree": {
                        "title": "str",
                        "body": "str"
                    },
                    "sortie": {
                        "complexite": "entier 1-5"
                    }
                }
            )

            return

        self._json(
            404,
            {"erreur": "route inconnue"}
        )

    # --------------------------------------------------------
    # POST : PREDICTIONS
    # --------------------------------------------------------

    def do_POST(self):

        route = self.path.split("?")[0]

        if not self._autorise():

            self._json(
                401,
                {"erreur": "jeton refusé"}
            )

            return

        try:

            corps = self._entree()

        except (ValueError, UnicodeDecodeError):

            self._json(
                400,
                {"erreur": "corps JSON illisible"}
            )

            return

        modele = charger_modele()

        if modele is None:

            self._json(
                503,
                {
                    "erreur": (
                        _ETAT["erreur"]
                        or "modèle indisponible"
                    )
                }
            )

            return

        try:

            # PREDICTION INDIVIDUELLE

            if route in ("/predire", "/predict"):

                tache = {
                    "title": str(corps.get("title", "")),
                    "body": str(corps.get("body", ""))
                }

                if not (
                    tache["title"] or tache["body"]
                ):

                    self._json(
                        400,
                        {
                            "erreur": "title et body sont vides"
                        }
                    )

                    return

                resultat = predire(
                    modele,
                    [tache]
                )[0]

                self._json(200, resultat)

            # PREDICTION PAR LOT

            elif route in (
                "/predire_lot",
                "/predict_batch"
            ):

                taches = (
                    corps.get("taches")
                    or corps.get("tasks")
                    or []
                )

                if not isinstance(taches, list) or not taches:

                    self._json(
                        400,
                        {
                            "erreur": (
                                "« taches » doit être "
                                "une liste non vide"
                            )
                        }
                    )

                    return

                if len(taches) > 500:

                    self._json(
                        413,
                        {
                            "erreur": "500 tâches maximum par lot"
                        }
                    )

                    return

                resultats = predire(
                    modele,
                    taches
                )

                self._json(
                    200,
                    {
                        "predictions": resultats,
                        "modele": {
                            "version": VERSION
                        }
                    }
                )

            else:

                self._json(
                    404,
                    {"erreur": "route inconnue"}
                )

        except Exception as exc:

            traceback.print_exc()

            self._json(
                500,
                {
                    "erreur": (
                        f"{type(exc).__name__} : {exc}"
                    )
                }
            )


# ============================================================
# DEMARRAGE
# ============================================================

def main():

    print(
        f"Service du modèle : {HOTE}:{PORT}",
        flush=True
    )

    print(
        f"Artefact : {FICHIER}",
        flush=True
    )

    charger_modele()

    serveur = ThreadingHTTPServer(
        (HOTE, PORT),
        _Handler
    )

    print(
        f"Serveur prêt sur le port {PORT}",
        flush=True
    )

    try:

        serveur.serve_forever()

    except KeyboardInterrupt:

        print(
            "Arrêt du serveur.",
            flush=True
        )

    finally:

        serveur.server_close()


if __name__ == "__main__":

    sys.exit(main())
