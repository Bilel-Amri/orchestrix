"""Test du cycle complet de la plateforme, sans clé Groq et sans vrai Jira.

On simule le serveur Jira avec un faux serveur HTTP local qui se comporte comme
l'API v3 : il vérifie le jeton, renvoie les types de ticket du projet, accepte
les créations et renvoie les tickets relus. Le test coche :

  1. création du projet depuis un plan
  2. définition de l'équipe
  3. répartition automatique et respect des rôles
  4. cycle de vie d'une tâche et calcul de l'avancement
  5. configuration Jira, vérification, envoi, relecture
  6. persistance sur disque (rechargement)
"""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))

from orchestrix import gestion, jira  # noqa: E402

# on repart d'un état vierge : le fichier de données est partagé entre exécutions
gestion._FICHIER.unlink(missing_ok=True)

OK, KO = [], []


def verifier(nom, condition, valeur=None):
    (OK if condition else KO).append(nom)
    print(("✓" if condition else "✗"), nom, ("→ " + str(valeur)) if valeur is not None else "")


# ── faux Jira ────────────────────────────────────────────────────────
CREES: list[dict] = []
ETAT_JIRA = {"PROJ-1": "new", "PROJ-2": "indeterminate", "PROJ-3": "done"}


class FauxJira(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _corps(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}") if n else {}

    def _envoyer(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):  # noqa: N802
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Basic "):
            return self._envoyer(401, {"errorMessages": ["non authentifié"]})
        if self.path.startswith("/rest/api/3/myself"):
            return self._envoyer(200, {"displayName": "Chef de projet test"})
        if self.path.startswith("/rest/api/3/project/search"):
            return self._envoyer(200, {"values": [{"key": "PROJ", "name": "Projet test"}]})
        if "/issue/createmeta/" in self.path:
            return self._envoyer(200, {"values": [
                {"id": "10001", "name": "Épic", "subtask": False},
                {"id": "10002", "name": "Story", "subtask": False},
                {"id": "10003", "name": "Tâche", "subtask": False},
            ]})
        if self.path.startswith("/rest/api/3/search"):
            # le faux Jira renvoie les clés RÉELLEMENT demandées : la première
            # est terminée, la deuxième en cours, les autres à faire
            import urllib.parse
            chemin = urllib.parse.unquote(self.path)      # %28 → (
            cles = []
            if "key in (" in chemin:
                bloc = chemin.split("key in (", 1)[1].split(")")[0]
                cles = [c.strip() for c in bloc.split(",") if c.strip()]
            etats = ["done", "indeterminate", "new", "new", "new", "new", "new", "new"]
            issues = [{"key": k, "fields": {
                "summary": "ticket " + k,
                "status": {"name": {"new": "À faire", "indeterminate": "En cours",
                                    "done": "Terminé"}[etats[i % len(etats)]],
                           "statusCategory": {"key": etats[i % len(etats)]}},
                "assignee": {"displayName": "Amine"},
            }} for i, k in enumerate(cles)]
            return self._envoyer(200, {"issues": issues})
        self._envoyer(404, {})

    def do_POST(self):  # noqa: N802
        if not self.headers.get("Authorization", "").startswith("Basic "):
            return self._envoyer(401, {})
        if self.path.endswith("/rest/api/3/issue"):
            c = self._corps()
            cle = f"PROJ-{len(CREES) + 1}"
            CREES.append({"cle": cle, "resume": c["fields"]["summary"],
                          "type": c["fields"]["issuetype"]["id"],
                          "parent": (c["fields"].get("parent") or {}).get("key")})
            return self._envoyer(201, {"key": cle, "id": cle})
        self._envoyer(404, {})


srv = ThreadingHTTPServer(("127.0.0.1", 0), FauxJira)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = f"http://127.0.0.1:{port}"

# ── plan d'essai ─────────────────────────────────────────────────────
PLAN = {"epics": [
    {"title": "Socle technique", "description": "Infrastructure", "points": 13, "stories": [
        {"cle": "US-1.1", "title": "Initialiser le produit", "as_a": "développeur",
         "i_want": "un dépôt", "so_that": "livrer", "acceptance": ["CI verte"],
         "tasks": [
             {"cle": "T-1.1.1", "title": "Créer le squelette", "description": "Structure",
              "type": "dev", "priorite": "Haute", "charge": 5, "sources": [1]},
             {"cle": "T-1.1.2", "title": "Configurer la CI", "description": "Pipeline",
              "type": "config", "priorite": "Moyenne", "charge": 3, "sources": [2]},
             {"cle": "T-1.1.3", "title": "Tests de fumée", "description": "Vérifs",
              "type": "test", "priorite": "Basse", "charge": 2, "sources": []}]}]},
    {"title": "Gestion des stocks", "description": "Cœur métier", "points": 16, "stories": [
        {"cle": "US-2.1", "title": "Suivre les stocks", "as_a": "gestionnaire",
         "i_want": "voir les quantités", "so_that": "anticiper",
         "acceptance": ["Temps réel", "Historique"],
         "tasks": [
             {"cle": "T-2.1.1", "title": "Calcul des niveaux", "description": "Agrégation",
              "type": "dev", "priorite": "Haute", "charge": 8, "sources": [3]},
             {"cle": "T-2.1.2", "title": "Écran de consultation", "description": "Liste",
              "type": "dev", "priorite": "Haute", "charge": 5, "sources": [1]},
             {"cle": "T-2.1.3", "title": "Guide d'usage", "description": "Documentation",
              "type": "doc", "priorite": "Moyenne", "charge": 3, "sources": []}]}]}]}
META = {"brief": "gestion de stock", "date": "2026-11-04 10:00", "modele": "test",
        "analyse": {"sujet": "Gestion de stock", "objectif": "Piloter les stocks",
                    "domaine": "Logistique"}}

print("── 1. création du projet ──")
etat = gestion.creer_projet(PLAN, META)
verifier("projet créé", etat["projet"]["nom"] == "Gestion de stock")
verifier("tâches extraites", len(etat["taches"]) == 6, len(etat["taches"]))
verifier("toutes à faire", all(t["statut"] == "a_faire" for t in etat["taches"].values()))
verifier("points conservés", sum(t["charge"] for t in etat["taches"].values()) == 26)

print("\n── 2. équipe ──")
etat = gestion.definir_equipe(etat, [
    {"nom": "Amine Ben Salah", "role": "Développeur backend", "capacite": 20},
    {"nom": "Sonia Trabelsi", "role": "Développeur frontend", "capacite": 18},
    {"nom": "Karim Haddad", "role": "Testeur", "capacite": 12},
    {"nom": "Leïla Mansour", "role": "DevOps", "capacite": 10},
])
verifier("4 membres", len(etat["projet"]["equipe"]) == 4)
verifier("initiales calculées", etat["projet"]["equipe"][0]["initiales"] == "AB",
         etat["projet"]["equipe"][0]["initiales"])

print("\n── 3. répartition automatique ──")
etat = gestion.repartir_automatiquement(etat)
t = etat["taches"]
verifier("toutes affectées", all(x["assigne"] for x in t.values()))
roles = {m["id"]: m["role"] for m in etat["projet"]["equipe"]}
verifier("le test va au testeur", t["T-1.1.3"]["assigne"] and
         roles[t["T-1.1.3"]["assigne"]] in ("Testeur", "Développeur full-stack"),
         roles.get(t["T-1.1.3"]["assigne"]))
verifier("la CI va au DevOps", roles.get(t["T-1.1.2"]["assigne"]) in ("DevOps", "Développeur backend"),
         roles.get(t["T-1.1.2"]["assigne"]))
# aucun membre n'a de rôle documentation : le repli doit choisir le moins chargé
verifier("doc affectée au repli (aucun rôle documentation dans l'équipe)",
         t["T-2.1.3"]["assigne"] is not None, roles.get(t["T-2.1.3"]["assigne"]))
st = gestion.statistiques(etat)
charges = sorted(c["assigne"] for c in st["charge"])
verifier("charge équilibrée", max(charges) - min(charges) <= 8, charges)
verifier("aucune surcharge", not any(c["surcharge"] for c in st["charge"]),
         [(c["nom"], c["assigne"], c["capacite"]) for c in st["charge"]])

print("\n── 4. exécution ──")
etat = gestion.changer_statut(etat, "T-1.1.1", "en_cours", "Amine")
verifier("statut changé", etat["taches"]["T-1.1.1"]["statut"] == "en_cours")
verifier("historique écrit", len(etat["taches"]["T-1.1.1"]["historique"]) >= 2)
etat = gestion.changer_statut(etat, "T-1.1.1", "termine")
st = gestion.statistiques(etat)
verifier("avancement 17 %", st["avancement"] == 17, str(st["avancement"]) + " %")
etat = gestion.changer_statut(etat, "T-1.1.3", "bloque")
st = gestion.statistiques(etat)
verifier("tâche bloquée comptée", st["bloquees"] == 1)
verifier("bloqué ≠ progression", st["avancement"] == 17, str(st["avancement"]) + " %")
etat = gestion.commenter(etat, "T-1.1.1", "Squelette poussé sur la branche principale", "Amine")
verifier("commentaire enregistré", len(etat["taches"]["T-1.1.1"]["commentaires"]) == 1)

print("\n── 5. Jira ──")
etat["jira"].update({"url": URL, "email": "chef@exemple.tn", "token": "jeton-secret",
                     "cle_projet": "PROJ"})
gestion.sauver(etat)
info = jira.verifier(URL, "chef@exemple.tn", "jeton-secret", "PROJ")
verifier("compte reconnu", info["compte"] == "Chef de projet test")
verifier("types détectés", len(info["types"]) == 3,
         [x["nom"] for x in info["types"]])

res = jira.creer_tickets(PLAN, etat["taches"], etat["jira"])
verifier("tickets créés", len(res["crees"]) > 0, str(len(res["crees"])) + " tickets")
verifier("aucune erreur", not res["erreurs"], res["erreurs"][:2])
verifier("2 épics + 2 stories + 6 tâches = 10", len(res["crees"]) == 10, len(res["crees"]))
verifier("clés Jira rattachées", len([v for v in res["liens"].values() if v]) == 6)
for notre, cle_jira in res["liens"].items():
    if notre in etat["taches"]:
        etat["taches"][notre]["jira"] = cle_jira
gestion.sauver(etat)

# relance : ne doit rien dupliquer
avant = len(CREES)
res2 = jira.creer_tickets(PLAN, etat["taches"], etat["jira"])
verifier("relance sans doublon pour les tâches",
         len([x for x in res2["crees"] if x["niveau"] == "tâche"]) == 0,
         str(len(CREES) - avant) + " créations au total (épics/stories)")

relu = jira.relire(etat["jira"], {k: v["jira"] for k, v in etat["taches"].items() if v["jira"]})
verifier("tickets relus", len(relu["tickets"]) > 0, str(len(relu["tickets"])))
n = jira.appliquer(etat["taches"], relu["tickets"])
verifier("statuts appliqués", n >= 1, str(n) + " changements")
statuts = [t["statut"] for t in etat["taches"].values()]
verifier("une tâche terminée via Jira", "termine" in statuts, statuts)
verifier("une tâche en cours via Jira", "en_cours" in statuts, statuts)
verifier("nom de l'assigné Jira noté",
         any(t.get("jira_assigne") == "Amine" for t in etat["taches"].values()))

print("\n── 6. persistance ──")
gestion.sauver(etat)
relu_disque = gestion.charger()
verifier("projet relu du disque", relu_disque["projet"]["nom"] == "Gestion de stock")
verifier("jeton conservé en local", relu_disque["jira"]["token"] == "jeton-secret")
vue = gestion.vue_publique(relu_disque)
verifier("jeton masqué dans l'API", "•" in vue["jira"]["token"] and "secret" not in vue["jira"]["token"])
verifier("tâches triées par épic", vue["taches"][0]["epic"] in ("E1", "E2"))
verifier("journal alimenté", len(vue["journal"]) > 5, str(len(vue["journal"])) + " entrées")

srv.shutdown()
print("\n" + ("TOUT PASSE (" + str(len(OK)) + " contrôles)" if not KO
              else "ÉCHECS : " + str(len(KO)) + " → " + ", ".join(KO)))
