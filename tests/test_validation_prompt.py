"""Validation du plan par le chef de projet (7 contrôles).

Vérifie le cycle aucune → en_attente → rejete → approuve, la règle des
10 caractères sur le motif, l'historique, et le fait que le motif du rejet
arrive bien dans le prompt envoyé au modèle.
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from orchestrix import agent, gestion  # noqa: E402

# on travaille sur un état jetable : le fichier réel n'est pas touché
import tempfile  # noqa: E402
from pathlib import Path as _P  # noqa: E402
gestion._FICHIER = _P(tempfile.mkdtemp()) / "etat.json"

_ok = 0


def verifie(nom, condition, detail=""):
    global _ok
    if not condition:
        raise AssertionError(f"{nom} — {detail}")
    _ok += 1
    print(f"✓ {nom}")


# ── 1. le prompt de génération reprend le motif ────────────────────────
bloc = agent.bloc_retour("Trop de documentation, et il manque les rôles.")
verifie("bloc de retour non vide", bool(bloc.strip()))
verifie("motif cité entre guillemets",
        "« Trop de documentation, et il manque les rôles. »" in bloc)
verifie("motif vide → aucun bloc", agent.bloc_retour("") == "")

# les espaces et retours à la ligne du motif sont normalisés dans la citation
bloc2 = agent.bloc_retour("Trop de documentation,\n et il   manque les rôles.")
citation = bloc2[bloc2.index("«") + 1:bloc2.index("»")].strip()
verifie("espaces normalisés",
        "\n" not in citation and "  " not in citation
        and citation == "Trop de documentation, et il manque les rôles.")

# ── 2. le cycle de validation ──────────────────────────────────────────
etat = gestion._vide()
plan = {"epics": [{"titre": "Socle", "taches": [
    {"title": "Poser le schéma de données", "type": "dev", "charge": 5,
     "priorite": "haute", "description": "Tables et migrations."}]}]}
etat["plan"] = plan
etat["brief"] = "Application de suivi de livraisons."

verifie("validation initiale absente",
        gestion._validation(etat)["statut"] in ("aucune", "en_attente"))

gestion.soumettre(etat)
verifie("soumission → en attente",
        gestion._validation(etat)["statut"] == "en_attente")

motif_court = False
try:
    gestion.rejeter(etat, "court")
except ValueError:
    motif_court = True
verifie("motif < 10 caractères refusé", motif_court)
verifie("toujours en attente après refus",
        gestion._validation(etat)["statut"] == "en_attente")

gestion.rejeter(etat, "Trop de documentation, il manque les rôles.")
v = gestion._validation(etat)
verifie("rejet → rejete avec motif",
        v["statut"] == "rejete" and "rôles" in v["motif"])
verifie("historique du rejet conservé", len(v["historique"]) >= 2)

gestion.soumettre(etat)
gestion.approuver(etat)
verifie("approbation → approuve", gestion._validation(etat)["statut"] == "approuve")

print(f"\nTOUT PASSE ({_ok} contrôles)")
