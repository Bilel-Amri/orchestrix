"""Gestion du projet après génération du plan.

Le plan produit par l'agent décrit *ce qu'il faut faire*. Ce module gère
*qui le fait* et *où en est chaque tâche* :

  - le projet (nom, brief, objectif) et son équipe ;
  - le cycle de vie d'une tâche : à faire → en cours → en revue → terminé,
    avec un état « bloqué » qui ne fait pas avancer l'avancement ;
  - l'affectation aux développeurs, manuelle ou automatique ;
  - la persistance dans un fichier JSON, pour retrouver son projet au
    redémarrage du serveur.

Aucune dépendance externe : la bibliothèque standard suffit.
"""

from __future__ import annotations

import json
import re
import threading
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

# ── Cycle de vie ─────────────────────────────────────────────────────
STATUTS = ["a_faire", "en_cours", "en_revue", "termine", "bloque"]
STATUT_LIB = {
    "a_faire": "À faire",
    "en_cours": "En cours",
    "en_revue": "En revue",
    "termine": "Terminé",
    "bloque": "Bloqué",
}
# Un état bloqué n'est pas une progression : il sort du calcul d'avancement.
STATUTS_AVANCEMENT = ["a_faire", "en_cours", "en_revue", "termine"]

ROLES = [
    "Développeur backend",
    "Développeur frontend",
    "Développeur full-stack",
    "Testeur",
    "Chef de projet",
    "Architecte",
    "Designer",
    "DevOps",
]

# Une nature de travail appelle un rôle : sert à l'affectation automatique.
AFFINITE = {
    "dev":     ["Développeur full-stack", "Développeur backend", "Développeur frontend"],
    "test":    ["Testeur", "Développeur full-stack"],
    "config":  ["DevOps", "Développeur backend"],
    "doc":     ["Chef de projet", "Développeur full-stack", "Architecte"],
    "design":  ["Designer", "Architecte", "Développeur frontend"],
    "securite": ["DevOps", "Architecte", "Développeur backend"],
}

_RACINE = Path(__file__).resolve().parent.parent / "donnees"
_FICHIER = _RACINE / "plateforme.json"
_VERROU = threading.RLock()


# ── Utilitaires ──────────────────────────────────────────────────────
def _maintenant() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")


def _slug(texte: str, maximum: int = 40) -> str:
    t = unicodedata.normalize("NFKD", str(texte)).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-zA-Z0-9]+", "-", t).strip("-").lower()
    return (t or "projet")[:maximum]


def _vide() -> dict:
    return {
        "projet": None,
        "taches": {},
        "validation": {"statut": "aucune", "motif": "", "date": "", "auteur": "",
                       "historique": []},
        "jira": {"url": "", "email": "", "token": "", "cle_projet": "",
                 "derniere_sync": None, "resultats": []},
        "journal": [],
    }


# ── Persistance ──────────────────────────────────────────────────────
def charger() -> dict:
    """Lit l'état sauvegardé, ou renvoie une structure vide."""
    with _VERROU:
        if not _FICHIER.exists():
            return _vide()
        try:
            d = json.loads(_FICHIER.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return _vide()
        base = _vide()
        base.update(d if isinstance(d, dict) else {})
        base.setdefault("jira", {}).setdefault("resultats", [])
        return base


def sauver(etat: dict) -> None:
    with _VERROU:
        _RACINE.mkdir(parents=True, exist_ok=True)
        tmp = _FICHIER.with_suffix(".tmp")
        tmp.write_text(json.dumps(etat, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(_FICHIER)


VALIDATIONS = {
    "aucune": "Non soumis",
    "en_attente": "En attente de validation",
    "approuve": "Approuvé",
    "rejete": "Rejeté",
}
VALIDATIONS_LIB = VALIDATIONS


def _validation(etat: dict) -> dict:
    return etat.setdefault("validation", {"statut": "aucune", "motif": "", "date": "",
                                          "auteur": "", "historique": []})


def soumettre(etat: dict, auteur: str = "") -> dict:
    """Le plan passe en attente de validation humaine."""
    v = _validation(etat)
    v.update({"statut": "en_attente", "date": _maintenant(),
              "auteur": auteur or "chef de projet", "motif": ""})
    v.setdefault("historique", []).append(
        {"date": _maintenant(), "statut": "en_attente",
         "texte": "plan soumis à validation", "auteur": auteur or "chef de projet"})
    journaliser(etat, "plan soumis à validation")
    sauver(etat)
    return etat


def approuver(etat: dict, auteur: str = "") -> dict:
    """Le chef de projet approuve : le plan devient exécutable."""
    v = _validation(etat)
    v.update({"statut": "approuve", "date": _maintenant(),
              "auteur": auteur or "chef de projet"})
    v.setdefault("historique", []).append(
        {"date": _maintenant(), "statut": "approuve",
         "texte": "plan approuvé", "auteur": auteur or "chef de projet"})
    journaliser(etat, "plan APPROUVÉ — la plateforme passe en exécution")
    sauver(etat)
    return etat


def rejeter(etat: dict, motif: str, auteur: str = "") -> dict:
    """Le chef de projet rejette : le motif servira à régénérer un autre plan.

    Rejeter sans motif serait inutile : le modèle produirait un plan presque
    identique. Le motif est donc obligatoire.
    """
    motif = " ".join(str(motif or "").split())
    if len(motif) < 10:
        raise ValueError("indiquez un motif de rejet d'au moins 10 caractères : "
                         "c'est lui qui guidera la régénération du plan")
    v = _validation(etat)
    v.update({"statut": "rejete", "motif": motif, "date": _maintenant(),
              "auteur": auteur or "chef de projet"})
    v.setdefault("historique", []).append(
        {"date": _maintenant(), "statut": "rejete", "texte": motif,
         "auteur": auteur or "chef de projet"})
    journaliser(etat, f"plan REJETÉ — motif : {motif[:120]}")
    sauver(etat)
    return etat


def journaliser(etat: dict, texte: str) -> None:
    etat.setdefault("journal", []).append({"date": _maintenant(), "texte": texte})
    etat["journal"] = etat["journal"][-200:]


# ── Création du projet ───────────────────────────────────────────────
def creer_projet(plan: dict, meta: dict, nom: str = "") -> dict:
    """Installe un plan généré comme projet pilotable.

    Les tâches reçoivent un identifiant stable (leur clé d'origine) : c'est lui
    qui sert ensuite dans l'interface, dans les exports et dans Jira. On ne
    régénère rien, on ne modifie pas le plan : on l'habille d'un état
    d'exécution.
    """
    analyse = (meta or {}).get("analyse") or {}
    sujet = nom.strip() or analyse.get("sujet") or "Projet sans titre"
    etat = charger()
    etat["projet"] = {
        "id": _slug(sujet),
        "nom": sujet,
        "brief": (meta or {}).get("brief", ""),
        "objectif": analyse.get("objectif", ""),
        "domaine": analyse.get("domaine", ""),
        "genere_le": (meta or {}).get("date", ""),
        "modele": (meta or {}).get("modele", ""),
        "cree_le": _maintenant(),
        "equipe": (etat.get("projet") or {}).get("equipe") or [],
    }
    etat["taches"] = _extraire_taches(plan)
    journaliser(etat, f"projet « {sujet} » créé avec {len(etat['taches'])} tâches")
    sauver(etat)
    return etat


def _extraire_taches(plan: dict) -> dict:
    taches: dict = {}

    for i, epic in enumerate(plan.get("epics") or []):
        eid = f"E{i + 1}"

        for j, story in enumerate(epic.get("stories") or []):
            sid = story.get("cle") or f"US-{i + 1}.{j + 1}"

            for t in story.get("tasks") or []:
                cle = str(
                    t.get("cle")
                    or f"T-{i + 1}.{j + 1}.{len(taches) + 1}"
                )

                taches[cle] = {
                    "cle": cle,
                    "titre": t.get("title", ""),
                    "description": t.get("description", ""),
                    "epic": eid,
                    "epic_titre": epic.get("title", ""),
                    "story": sid,
                    "story_titre": story.get("title", ""),
                    "type": t.get("type", "dev"),
                    "priorite": t.get("priorite", "Moyenne"),
                    "complexite_classe": t.get("complexite_classe"),
                    "sources": list(t.get("sources") or []),
                    "statut": "a_faire",
                    "assigne": None,
                    "jira": None,
                    "commentaires": [],
                    "historique": [],
                }

    return taches

def definir_equipe(etat: dict, membres: list[dict]) -> dict:
    propre: list[dict] = []

    for k, m in enumerate(membres):
        nom = str(m.get("nom") or "").strip()
        if not nom:
            continue

        role = str(m.get("role") or ROLES[0])
        if role not in ROLES:
            role = ROLES[0]

        propre.append({
            "id": str(m.get("id") or f"m{k + 1}"),
            "nom": nom,
            "role": role,
            "initiales": "".join(
                p[0] for p in nom.split()[:2]
            ).upper() or "?",
        })

    if etat.get("projet"):
        etat["projet"]["equipe"] = propre

    journaliser(etat, f"équipe définie : {len(propre)} membre(s)")
    sauver(etat)
    return etat

def affecter(etat: dict, cle: str, membre_id: str | None) -> dict:
    t = (etat.get("taches") or {}).get(cle)
    if not t:
        raise KeyError(cle)
    avant = t.get("assigne")
    t["assigne"] = membre_id or None
    if avant != t["assigne"]:
        nom = _nom_membre(etat, t["assigne"]) or "personne"
        t["historique"].append({"date": _maintenant(),
                                "texte": f"affectée à {nom}"})
        journaliser(etat, f"{cle} affectée à {nom}")
        sauver(etat)
    return etat


def _nom_membre(etat: dict, mid: str | None) -> str:
    if not mid:
        return ""
    for m in ((etat.get("projet") or {}).get("equipe") or []):
        if m["id"] == mid:
            return m["nom"]
    return ""


def _score_candidat(
    membre: dict,
    tache: dict,
    repartition: dict
) -> tuple[tuple, str]:
    """Choisit un membre selon ses compétences et son nombre de tâches."""

    role = membre["role"]
    nature = tache.get("type", "dev")

    if role in AFFINITE.get(nature, []):
        metier = (
            0 if AFFINITE.get(nature, [None])[0] == role else 1
        )
        raison = f"profil {role.lower()} adapté à une tâche de type {nature}"
    else:
        metier = 2
        raison = f"aucun profil {nature} dans l'équipe"

    nombre_taches = repartition.get(membre["id"], 0)

    return (
        (metier, nombre_taches, membre["nom"].casefold()),
        raison
    )

def repartir_automatiquement(
    etat: dict,
    forcer: bool = False
) -> dict:
    """Répartit les tâches selon les compétences et le nombre de tâches."""

    equipe = (etat.get("projet") or {}).get("equipe") or []
    if not equipe:
        return etat

    taches = etat.get("taches") or {}

    if forcer:
        for t in taches.values():
            t["assigne"] = None

    repartition = {m["id"]: 0 for m in equipe}

    # Comptabiliser les affectations déjà existantes.
    for t in taches.values():
        mid = t.get("assigne")
        if mid in repartition:
            repartition[mid] += 1

    ordre_priorite = {"Haute": 0, "Moyenne": 1, "Basse": 2}

    a_faire = sorted(
        (t for t in taches.values() if not t.get("assigne")),
        key=lambda t: (
            ordre_priorite.get(t.get("priorite"), 1),
            t.get("epic", ""),
            t.get("cle", ""),
        )
    )

    for t in a_faire:
        notes = [
            (_score_candidat(m, t, repartition) + (m,))
            for m in equipe
        ]

        score, raison, choisi = min(
            notes,
            key=lambda x: x[0]
        )

        t["assigne"] = choisi["id"]
        repartition[choisi["id"]] += 1

        t.setdefault("historique", []).append({
            "date": _maintenant(),
            "texte": (
                f"affectée automatiquement à {choisi['nom']} "
                f"({raison})"
            ),
        })

    journaliser(
        etat,
        f"répartition automatique : {len(a_faire)} tâche(s) affectée(s)"
        + (" (recalcul complet)" if forcer else "")
    )

    sauver(etat)
    return etat

def plan_de_charge(etat: dict) -> dict:
    """Retourne la répartition des tâches entre les membres."""

    st = statistiques(etat)

    return {
        "repartition": st["equipe"],
        "total_taches": st["total"],
        "non_assigne": st["non_assigne"],
    }

def changer_statut(etat: dict, cle: str, statut: str, auteur: str = "") -> dict:
    if statut not in STATUTS:
        raise ValueError(f"statut inconnu : {statut}")
    t = (etat.get("taches") or {}).get(cle)
    if not t:
        raise KeyError(cle)
    avant = t.get("statut")
    if avant == statut:
        return etat
    t["statut"] = statut
    qui = auteur or _nom_membre(etat, t.get("assigne")) or "chef de projet"
    t["historique"].append({
        "date": _maintenant(),
        "texte": f"{STATUT_LIB.get(avant, avant)} → {STATUT_LIB[statut]}",
        "auteur": qui,
    })
    journaliser(etat, f"{cle} : {STATUT_LIB.get(avant, avant)} → {STATUT_LIB[statut]} par {qui}")
    sauver(etat)
    return etat


def commenter(etat: dict, cle: str, texte: str, auteur: str = "") -> dict:
    t = (etat.get("taches") or {}).get(cle)
    if not t:
        raise KeyError(cle)
    texte = str(texte).strip()
    if not texte:
        return etat
    t["commentaires"].append({
        "date": _maintenant(), "texte": texte,
        "auteur": auteur or _nom_membre(etat, t.get("assigne")) or "chef de projet",
    })
    sauver(etat)
    return etat


# ── Indicateurs ──────────────────────────────────────────────────────
def statistiques(etat: dict) -> dict:
    """Calcule les statistiques en nombre de tâches."""

    taches = list((etat.get("taches") or {}).values())
    total = len(taches)

    par_statut = {s: 0 for s in STATUTS}

    for t in taches:
        statut = t.get("statut", "a_faire")
        par_statut[statut] = par_statut.get(statut, 0) + 1

    fait = par_statut.get("termine", 0)
    en_cours = (
        par_statut.get("en_cours", 0)
        + par_statut.get("en_revue", 0)
    )

    avancement = round(fait / total * 100) if total else 0

    equipe = (etat.get("projet") or {}).get("equipe") or []

    repartition = {
        m["id"]: {
            "nom": m["nom"],
            "role": m["role"],
            "taches": 0,
            "assignees": 0,
            "terminees": 0,
            "en_cours": 0,
        }
        for m in equipe
    }

    for t in taches:
        mid = t.get("assigne")

        if mid not in repartition:
            continue

        membre = repartition[mid]
        membre["taches"] += 1
        membre["assignees"] += 1

        if t.get("statut") == "termine":
            membre["terminees"] += 1
        elif t.get("statut") in ("en_cours", "en_revue"):
            membre["en_cours"] += 1

    classes = ("Faible", "Moyenne", "Elevee", "Tres_elevee")
    par_complexite = {
        classe: sum(
            1 for t in taches
            if t.get("complexite_classe") == classe
        )
        for classe in classes
    }

    return {
        "total": total,
        "par_statut": par_statut,
        "avancement": avancement,
        "en_cours": en_cours,
        "bloquees": par_statut.get("bloque", 0),
        "non_assigne": sum(
            1 for t in taches if not t.get("assigne")
        ),
        "par_complexite": par_complexite,
        "equipe": list(repartition.values()),
        "dans_jira": sum(1 for t in taches if t.get("jira")),
    }

def taches_triees(etat: dict) -> list[dict]:
    ordre = {"Haute": 0, "Moyenne": 1, "Basse": 2}

    return sorted(
        (etat.get("taches") or {}).values(),
        key=lambda t: (
            t.get("epic", ""),
            ordre.get(t.get("priorite"), 1),
            t.get("cle", ""),
        )
    )

def vue_publique(etat: dict) -> dict:
    """État envoyé au navigateur — le jeton Jira n'en sort jamais."""
    jira = dict(etat.get("jira") or {})
    jeton = jira.get("token") or ""
    jira["token"] = ("•" * 12) if jeton else ""
    jira["configure"] = bool(jira.get("url") and jira.get("email") and jeton)
    jira["resultats"] = (jira.get("resultats") or [])[-40:]
    return {
        "projet": etat.get("projet"),
        "validation": _validation(etat),
        "validations": [{"cle": k, "libelle": v} for k, v in VALIDATIONS.items()],
        "taches": taches_triees(etat),
        "jira": jira,
        "statistiques": statistiques(etat),
        "statuts": [{"cle": s, "libelle": STATUT_LIB[s]} for s in STATUTS],
        "roles": ROLES,
        "journal": (etat.get("journal") or [])[-40:],
    }
