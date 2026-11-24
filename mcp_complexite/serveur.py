"""Serveur MCP — Orchestrix expose ses tâches et leur complexité aux agents.

    transport : JSON-RPC 2.0 sur entrée/sortie standard (MCP « stdio »)
    aucune dépendance : bibliothèque standard seulement

Ce que ce serveur apporte
-------------------------
Un agent conversationnel (Claude Desktop, Cursor, un orchestre maison) peut
demander, en langage naturel, « quelle est la complexité des tâches du
dernier plan ? ». Le serveur MCP répond en appelant le service de modèle, ou
en lisant directement le dernier plan produit par Orchestrix.

Outils exposés
--------------
    lister_plans        les plans disponibles dans out/
    lire_plan           le contenu d'un plan (épics, stories, tâches)
    predire_complexite  complexité d'une ou plusieurs tâches (titre + corps)
    complexite_plan     complexité de TOUTES les tâches d'un plan
    etat_service        le service de modèle répond-il ?

Pourquoi MCP et pas une simple API REST
---------------------------------------
Une API REST demande à l'agent de connaître l'URL, de composer un corps JSON,
de gérer les erreurs. MCP expose des *outils nommés avec un schéma* : l'agent
sait quoi appeler et avec quoi. C'est la même logique que lire un plan :
l'outil décrit ce qu'il attend, l'agent n'a plus qu'à le remplir.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Le dossier de la plateforme est ajouté au chemin : le serveur MCP peut être
# lancé depuis n'importe où (Claude Desktop le lance avec son propre cwd).
RACINE = Path(os.environ.get("ORCHESTRIX_RACINE", Path(__file__).resolve().parent.parent))
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

VERSION = "1.0.0"
PROTOCOLE = "2024-11-05"


# ── chargement de la plateforme, tolérant ────────────────────────────
def _complexite():
    try:
        from orchestrix import complexite          # noqa: PLC0415
        return complexite
    except Exception:                              # noqa: BLE001
        return None


def _dossier_sorties() -> Path:
    return Path(os.environ.get("ORCHESTRIX_OUT", RACINE / "out"))


# ── outils ───────────────────────────────────────────────────────────
def outil_lister_plans(_args: dict) -> dict:
    dossier = _dossier_sorties()
    plans = []
    if dossier.exists():
        for f in sorted(dossier.glob("*.json"), key=lambda p: -p.stat().st_mtime):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            plan = d.get("plan") or d
            taches = sum(len(s.get("tasks", []))
                         for e in plan.get("epics", [])
                         for s in e.get("stories", []))
            plans.append({"fichier": f.name,
                          "date": (d.get("metadonnees") or d.get("meta") or {}).get("date"),
                          "taches": taches,
                          "octets": f.stat().st_size})
    return {"plans": plans, "dossier": str(dossier)}


def _charge_plan(nom: str | None) -> tuple[dict, str]:
    dossier = _dossier_sorties()
    fichiers = sorted(dossier.glob("*.json"), key=lambda p: -p.stat().st_mtime) \
        if dossier.exists() else []
    if not fichiers:
        raise FileNotFoundError(f"aucun plan dans {dossier}")
    if nom:
        choisi = next((f for f in fichiers if f.name == nom), None)
        if choisi is None:
            raise FileNotFoundError(f"plan « {nom} » introuvable")
    else:
        choisi = fichiers[0]
    d = json.loads(choisi.read_text(encoding="utf-8"))
    return (d.get("plan") or d), choisi.name


def outil_lire_plan(args: dict) -> dict:
    plan, nom = _charge_plan(args.get("fichier"))
    resume = []
    for e in plan.get("epics", []):
        for s in e.get("stories", []):
            for t in s.get("tasks", []):
                resume.append({"cle": t.get("cle"), "titre": t.get("title"),
                               "epic": e.get("title"), "story": s.get("title"),
                               "type": t.get("type"), "charge": t.get("charge"),
                               "origine": t.get("charge_origine", "regles")})
    return {"fichier": nom, "epics": len(plan.get("epics", [])),
            "taches": len(resume), "detail": resume}


def outil_predire_complexite(args: dict) -> dict:
    module = _complexite()
    if module is None:
        return {"erreur": "plateforme Orchestrix introuvable"}
    entrees = args.get("taches")
    if not entrees:
        un = {"title": args.get("title", ""), "body": args.get("body", "")}
        if not (un["title"] or un["body"]):
            return {"erreur": "fournir « taches », ou « title » et « body »"}
        entrees = [un]
    entrees = [t if isinstance(t, dict) else {"title": str(t)} for t in entrees]
    predictions = module.predire_lot(entrees)
    if not predictions:
        return {"erreur": "service de modèle muet ou non configuré",
                "conseil": "démarrer service_modele et définir URL_MODELE"}
    sortie = []
    for t, p in zip(entrees, predictions):
        sortie.append({"title": t.get("title", ""),
                       "complexite": p["complexite"],
                       "echelle": "1 (trivial) à 5 (difficile)",
                       "origine": p["origine"]})
    return {"predictions": sortie}


def outil_complexite_plan(args: dict) -> dict:
    plan, nom = _charge_plan(args.get("fichier"))
    module = _complexite()
    taches = [t for e in plan.get("epics", [])
              for s in e.get("stories", [])
              for t in s.get("tasks", [])]
    if not taches:
        return {"fichier": nom, "taches": 0, "predictions": []}

    predictions = None
    if module is not None:
        predictions = module.predire_lot(
            [{"title": t.get("title", ""), "body": t.get("description", "")}
             for t in taches])

    detail = []
    for i, t in enumerate(taches):
        if predictions and i < len(predictions):
            detail.append({"cle": t.get("cle"), "titre": t.get("title"),
                           "complexite": predictions[i]["complexite"],
                           "origine": "modele"})
        else:
            detail.append({"cle": t.get("cle"), "titre": t.get("title"),
                           "complexite": t.get("charge"),
                           "origine": t.get("charge_origine", "regles")})
    valeurs = [d["complexite"] for d in detail if isinstance(d["complexite"], int)]
    return {"fichier": nom, "taches": len(detail),
            "moyenne": round(sum(valeurs) / len(valeurs), 2) if valeurs else None,
            "detail": detail}


def outil_etat_service(_args: dict) -> dict:
    module = _complexite()
    if module is None:
        return {"erreur": "plateforme Orchestrix introuvable"}
    return module.sante()


# ── catalogue ────────────────────────────────────────────────────────
OUTILS = [
    {
        "name": "etat_service",
        "description": "Dit si le service de prédiction de complexité répond, "
                       "et quelle version de modèle il sert.",
        "inputSchema": {"type": "object", "properties": {}},
        "_fn": outil_etat_service,
    },
    {
        "name": "lister_plans",
        "description": "Liste les plans générés par Orchestrix (fichiers JSON du "
                       "dossier out/), du plus récent au plus ancien.",
        "inputSchema": {"type": "object", "properties": {}},
        "_fn": outil_lister_plans,
    },
    {
        "name": "lire_plan",
        "description": "Renvoie les tâches d'un plan : clé, titre, épic, story, "
                       "type, charge estimée et origine de l'estimation.",
        "inputSchema": {"type": "object", "properties": {
            "fichier": {"type": "string",
                        "description": "nom du fichier ; le plus récent par défaut"}}},
        "_fn": outil_lire_plan,
    },
    {
        "name": "predire_complexite",
        "description": "Prédit la complexité (1 = trivial, 5 = difficile) d'une ou "
                       "plusieurs tâches à partir de leur titre et de leur "
                       "description. C'est le modèle entraîné qui répond.",
        "inputSchema": {"type": "object", "properties": {
            "taches": {"type": "array", "items": {"type": "object", "properties": {
                "title": {"type": "string"}, "body": {"type": "string"}}}},
            "title": {"type": "string", "description": "raccourci pour une tâche"},
            "body": {"type": "string", "description": "raccourci pour une tâche"}}},
        "_fn": outil_predire_complexite,
    },
    {
        "name": "complexite_plan",
        "description": "Prédit la complexité de TOUTES les tâches d'un plan et "
                       "renvoie la moyenne. Utilise le modèle si le service "
                       "répond, sinon les estimations enregistrées.",
        "inputSchema": {"type": "object", "properties": {
            "fichier": {"type": "string",
                        "description": "nom du plan ; le plus récent par défaut"}}},
        "_fn": outil_complexite_plan,
    },
]


def _catalogue() -> list[dict]:
    return [{k: v for k, v in o.items() if k != "_fn"} for o in OUTILS]


# ── JSON-RPC ─────────────────────────────────────────────────────────
def traiter(requete: dict) -> dict | None:
    methode = requete.get("method")
    rid = requete.get("id")
    params = requete.get("params") or {}

    def ok(resultat):
        return {"jsonrpc": "2.0", "id": rid, "result": resultat}

    def err(code, message):
        return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}

    if methode == "initialize":
        return ok({"protocolVersion": PROTOCOLE,
                   "capabilities": {"tools": {"listChanged": False}},
                   "serverInfo": {"name": "orchestrix-complexite",
                                  "version": VERSION}})
    if methode in ("notifications/initialized", "initialized", "notifications/cancelled"):
        return None                                  # notifications : pas de réponse
    if methode == "ping":
        return ok({})
    if methode == "tools/list":
        return ok({"tools": _catalogue()})
    if methode == "tools/call":
        nom = params.get("name")
        args = params.get("arguments") or {}
        outil = next((o for o in OUTILS if o["name"] == nom), None)
        if outil is None:
            return err(-32602, f"outil inconnu : {nom}")
        try:
            resultat = outil["_fn"](args)
        except FileNotFoundError as exc:
            return ok({"content": [{"type": "text", "text": str(exc)}],
                       "isError": True})
        except Exception as exc:                     # noqa: BLE001
            return ok({"content": [{"type": "text",
                                    "text": f"{type(exc).__name__} : {exc}"}],
                       "isError": True})
        return ok({"content": [{"type": "text",
                                "text": json.dumps(resultat, ensure_ascii=False,
                                                   indent=1)}],
                   "isError": False})
    if methode in ("resources/list", "prompts/list"):
        return ok({methode.split("/")[0]: []})
    return err(-32601, f"méthode inconnue : {methode}")


def boucle(entree=None, sortie=None) -> None:
    entree = entree or sys.stdin
    sortie = sortie or sys.stdout
    for ligne in entree:
        ligne = ligne.strip()
        if not ligne:
            continue
        try:
            requete = json.loads(ligne)
        except ValueError:
            sortie.write(json.dumps({"jsonrpc": "2.0", "id": None,
                                     "error": {"code": -32700,
                                               "message": "JSON illisible"}}) + "\n")
            sortie.flush()
            continue
        reponse = traiter(requete)
        if reponse is not None:
            sortie.write(json.dumps(reponse, ensure_ascii=False) + "\n")
            sortie.flush()


if __name__ == "__main__":
    boucle()
