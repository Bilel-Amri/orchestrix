"""Bout en bout sur le vrai serveur HTTP : plan → projet → équipe → exécution."""
import json, sys, urllib.request
from pathlib import Path
RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from orchestrix import server, jira
PLAN = json.load(open(RACINE / "tests" / "fixture.json"))["PLAN"]
META = json.load(open(RACINE / "tests" / "fixture.json"))["META"]
PREUVES = json.load(open(RACINE / "tests" / "fixture.json"))["PREUVES"]

# serveur réel, démarré dans CE processus : les appels HTTP touchent bien
# les gestionnaires du serveur, et l'état injecté est le même que celui servi.
import threading
from http.server import ThreadingHTTPServer
from orchestrix import gestion
gestion._FICHIER.unlink(missing_ok=True)
_srv = ThreadingHTTPServer(("127.0.0.1", 0), server._Handler)
_port = _srv.server_address[1]
threading.Thread(target=_srv.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{_port}"

def appel(chemin, corps=None):
    if corps is None:
        r = urllib.request.urlopen(BASE + chemin, timeout=10)
    else:
        r = urllib.request.urlopen(urllib.request.Request(
            BASE + chemin, data=json.dumps(corps).encode(),
            headers={"Content-Type": "application/json"}, method="POST"), timeout=10)
    return json.loads(r.read())

ok, ko = [], []
def c(nom, cond, val=None):
    (ok if cond else ko).append(nom)
    print(("✓" if cond else "✗"), nom, ("→ " + str(val)) if val is not None else "")

print("── état initial ──")
c("page servie", urllib.request.urlopen(BASE + "/", timeout=10).status == 200)
c("projet vide", appel("/api/projet")["projet"] is None)

print("\n── sans plan, la création est refusée ──")
try:
    appel("/api/projet/creer", {})
    c("création refusée sans plan", False)
except urllib.error.HTTPError as e:
    c("création refusée sans plan", e.code == 400, e.code)

print("\n── on injecte un plan comme le ferait la génération ──")
with server._VERROU:
    server._ETAT.update({"plan": PLAN, "meta": META, "preuves": PREUVES,
                         "statut": "termine"})
c("plan en mémoire", appel("/api/plan")["plan"]["epics"][0]["title"].startswith("Socle"))

print("\n── création du projet ──")
etat = appel("/api/projet/creer", {"nom": "Gestion de stock"})
c("projet créé", etat["projet"]["nom"] == "Gestion de stock")
c("18 tâches", len(etat["taches"]) == 18, len(etat["taches"]))
c("72 points", etat["statistiques"]["points_total"] == 72, etat["statistiques"]["points_total"])
c("tout non affecté", etat["statistiques"]["non_assigne"] == 18)

print("\n── équipe ──")
etat = appel("/api/projet/equipe", {"membres": [
    {"nom": "Amine Ben Salah", "role": "Développeur backend", "capacite": 25},
    {"nom": "Sonia Trabelsi", "role": "Développeur frontend", "capacite": 25},
    {"nom": "Karim Haddad", "role": "Testeur", "capacite": 15},
    {"nom": "Leïla Mansour", "role": "DevOps", "capacite": 15}]})
c("4 membres", len(etat["projet"]["equipe"]) == 4)

print("\n── répartition ──")
etat = appel("/api/projet/repartir", {})
c("toutes affectées", etat["statistiques"]["non_assigne"] == 0)
noms = {m["id"]: m["role"] for m in etat["projet"]["equipe"]}
tests = [t for t in etat["taches"] if t["type"] == "test"]
c("tests confiés au testeur", all(noms[t["assigne"]] == "Testeur" for t in tests),
  len(tests))
ch = etat["statistiques"]["charge"]
c("charge répartie", ", ".join(f"{x['nom'].split()[0]} {x['assigne']}/{x['capacite']}" for x in ch))

print("\n── exécution ──")
etat = appel("/api/projet/statut", {"cle": "T-1.1.1", "statut": "en_cours"})
etat = appel("/api/projet/statut", {"cle": "T-1.1.1", "statut": "termine"})
c("avancement 6 %", etat["statistiques"]["avancement"] == 6,
  str(etat["statistiques"]["avancement"]) + " %")
etat = appel("/api/projet/statut", {"cle": "T-1.1.3", "statut": "bloque"})
c("1 tâche bloquée", etat["statistiques"]["bloquees"] == 1)
etat = appel("/api/projet/commenter", {"cle": "T-1.1.1",
             "texte": "Squelette poussé, revue faite.", "auteur": "Amine"})
t = [x for x in etat["taches"] if x["cle"] == "T-1.1.1"][0]
c("commentaire ajouté", len(t["commentaires"]) == 1)
c("historique de la tâche", len(t["historique"]) >= 3, len(t["historique"]))

print("\n── persistance : on relit depuis le disque ──")
sur_disque = gestion.charger()
c("projet sur disque", sur_disque["projet"]["nom"] == "Gestion de stock")
c("statuts conservés", sum(1 for x in sur_disque["taches"].values()
                            if x["statut"] == "termine") == 1)

print("\n── Jira : jeton masqué dans l'API ──")
etat = appel("/api/jira/config", {"url": "https://exemple.atlassian.net",
             "email": "chef@exemple.tn", "token": "SECRET-123", "cle_projet": "PROJ"})
c("configuré", etat["jira"]["configure"])
c("jeton masqué", "SECRET" not in json.dumps(etat["jira"]), etat["jira"]["token"])
c("jeton réel sur disque", gestion.charger()["jira"]["token"] == "SECRET-123")

_srv.shutdown()
print("\n" + ("TOUT PASSE (" + str(len(ok)) + " contrôles)" if not ko
              else "ÉCHECS : " + str(len(ko)) + " → " + ", ".join(ko)))
