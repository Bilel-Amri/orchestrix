"""Contrôles de l'intégration du modèle de complexité et du serveur MCP.

Aucun réseau, aucune dépendance : un faux service de modèle est monté en
mémoire, et un faux artefact remplace `model_bundle.joblib`.

    python3 tests/test_modele_complexite.py        (depuis la racine du projet)
"""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

OK = 0
KO = 0


def verifier(nom: str, condition: bool, detail: str = "") -> None:
    global OK, KO
    if condition:
        OK += 1
        print(f"✓ {nom}" + (f" — {detail}" if detail else ""))
    else:
        KO += 1
        print(f"✗ {nom}" + (f" — {detail}" if detail else ""))


# ── faux service de modèle ───────────────────────────────────────────
APPELS: list[dict] = []


class _FauxModele(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, code, d):
        c = json.dumps(d).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(c)))
        self.end_headers()
        self.wfile.write(c)

    def do_GET(self):
        self._json(200, {"statut": "pret", "version": "9.9.9",
                         "artefact": "/modele/model_bundle.joblib"})

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        corps = json.loads(self.rfile.read(n) or b"{}")
        APPELS.append(corps)
        taches = corps.get("taches") or []
        # règle du faux modèle : plus le corps est long, plus c'est complexe
        preds = [{"complexite": max(1, min(5, 1 + len(t.get("body", "")) // 40))}
                 for t in taches]
        self._json(200, {"predictions": preds, "modele": {"version": "9.9.9"}})


def _demarrer_faux():
    s = ThreadingHTTPServer(("127.0.0.1", 0), _FauxModele)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s, f"http://127.0.0.1:{s.server_address[1]}"


# ── 1. client de complexité ──────────────────────────────────────────
print("\n--- CLIENT DE COMPLEXITÉ ---")
from orchestrix import complexite                      # noqa: E402

verifier("sans URL, aucune requête", complexite.predire_lot(
    [{"title": "a", "body": "b"}]) == [] and not complexite.disponible())
verifier("diagnostic lisible sans service",
         "règles internes" in complexite.diagnostiquer())

serveur, url = _demarrer_faux()
complexite.URL = url
complexite.DELAI = 3.0

sante = complexite.sante()
verifier("santé interrogée", sante.get("actif") is True and sante.get("version") == "9.9.9")
verifier("diagnostic nomme le modèle",
         "modèle 9.9.9" in complexite.diagnostiquer(),
         complexite.diagnostiquer())

APPELS.clear()
preds = complexite.predire_lot([
    {"title": "Connexion", "body": "court"},
    {"title": "Migration", "body": "x" * 160},
])
verifier("lot de deux renvoyé", len(preds) == 2, str(preds))
verifier("complexité bornée 1-5", all(1 <= p["complexite"] <= 5 for p in preds))
verifier("origine tracée", all(p["origine"] == "modele" for p in preds))
verifier("un seul appel réseau pour tout le lot", len(APPELS) == 1,
         f"{len(APPELS)} appel(s)")
verifier("titre et corps transmis séparément",
         APPELS[0]["taches"][1]["title"] == "Migration"
         and len(APPELS[0]["taches"][1]["body"]) == 160)

# service muet : repli, pas d'exception
complexite.URL = "http://127.0.0.1:9"          # port fermé
verifier("service muet → liste vide, sans exception",
         complexite.predire_lot([{"title": "a", "body": "b"}]) == [])
verifier("service muet signalé dans le diagnostic",
         "règles internes" in complexite.diagnostiquer())
complexite.URL = url

# ── 2. application au plan ───────────────────────────────────────────
print("\n--- APPLICATION AU PLAN ---")
from orchestrix.agent import Orchestrix                 # noqa: E402


class _FauxLLM:
    model = "faux"


agent = Orchestrix(llm=_FauxLLM(), verbose=False)
plan = {"epics": [{"title": "Socle", "stories": [{"title": "Auth", "tasks": [
    {"title": "Connexion", "description": "court", "charge": 5},
    {"title": "Migration", "description": "x" * 160, "charge": 2},
]}]}]}
resume = agent._appliquer_complexite(plan)
taches = plan["epics"][0]["stories"][0]["tasks"]
verifier("origine du modèle consignée", resume["origine"] == "modele", str(resume))
verifier("charge remplacée", taches[1]["charge"] == 5 and taches[0]["charge"] == 1,
         f"{taches[0]['charge']} / {taches[1]['charge']}")
verifier("ancienne valeur conservée", taches[0]["charge_regles"] == 5)
verifier("origine par tâche", taches[0]["charge_origine"] == "modele")
verifier("points de story recalculés",
         plan["epics"][0]["stories"][0]["points"] == 6,
         str(plan["epics"][0]["stories"][0]["points"]))
verifier("moyenne publiée", resume["moyenne"] == 3.0)

complexite.URL = ""
plan2 = {"epics": [{"title": "S", "stories": [{"title": "s", "tasks": [
    {"title": "t", "description": "d", "charge": 3}]}]}]}
r2 = agent._appliquer_complexite(plan2)
verifier("sans service : règles conservées",
         r2["origine"] == "regles"
         and plan2["epics"][0]["stories"][0]["tasks"][0]["charge"] == 3
         and plan2["epics"][0]["stories"][0]["tasks"][0]["charge_origine"] == "regles")
complexite.URL = url

# ── 3. serveur MCP ───────────────────────────────────────────────────
print("\n--- SERVEUR MCP ---")
sys.path.insert(0, str(RACINE / "mcp_complexite"))
import serveur as mcp                                   # noqa: E402

out = RACINE / "out"
out.mkdir(exist_ok=True)
plan_essai = out / "plan_test_mcp.json"
plan_essai.write_text(json.dumps({"meta": {"date": "2026-11-24 10:00"},
                                  "plan": plan}, ensure_ascii=False), encoding="utf-8")
import os                                               # noqa: E402
os.environ["ORCHESTRIX_OUT"] = str(out)
mcp._dossier_sorties = lambda: out

init = mcp.traiter({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
verifier("initialize répond", init["result"]["protocolVersion"] == "2024-11-05")
verifier("capacités tools annoncées",
         "tools" in init["result"]["capabilities"])

notif = mcp.traiter({"jsonrpc": "2.0", "method": "notifications/initialized"})
verifier("notification sans réponse", notif is None)

liste = mcp.traiter({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
noms = [t["name"] for t in liste["result"]["tools"]]
verifier("cinq outils exposés", len(noms) == 5, ", ".join(noms))
verifier("chaque outil a un schéma",
         all(t.get("inputSchema", {}).get("type") == "object"
             for t in liste["result"]["tools"]))
verifier("aucune fonction interne divulguée",
         all("_fn" not in t for t in liste["result"]["tools"]))


def appeler(nom, args=None):
    r = mcp.traiter({"jsonrpc": "2.0", "id": 9, "method": "tools/call",
                     "params": {"name": nom, "arguments": args or {}}})
    contenu = r["result"]["content"][0]["text"]
    try:
        return json.loads(contenu), r["result"].get("isError")
    except ValueError:
        return contenu, r["result"].get("isError")


etat, _ = appeler("etat_service")
verifier("etat_service renvoie la version", etat.get("version") == "9.9.9")

plans, _ = appeler("lister_plans")
verifier("lister_plans voit le plan écrit",
         any(p["fichier"] == "plan_test_mcp.json" for p in plans["plans"]))

detail, _ = appeler("lire_plan", {"fichier": "plan_test_mcp.json"})
verifier("lire_plan compte les tâches", detail["taches"] == 2)
verifier("lire_plan expose la charge", detail["detail"][0]["charge"] == 1)

pred, _ = appeler("predire_complexite", {"title": "Connexion", "body": "court"})
verifier("predire_complexite répond 1 pour un texte court",
         pred["predictions"][0]["complexite"] == 1, str(pred))

tout, _ = appeler("complexite_plan", {"fichier": "plan_test_mcp.json"})
verifier("complexite_plan couvre toutes les tâches", tout["taches"] == 2)
verifier("complexite_plan donne une moyenne", tout["moyenne"] == 3.0,
         str(tout["moyenne"]))

verifier("outil inconnu rejeté", mcp.traiter(
    {"jsonrpc": "2.0", "id": 9, "method": "tools/call",
     "params": {"name": "outil_inexistant"}})["error"]["code"] == -32602)

mauvais = mcp.traiter({"jsonrpc": "2.0", "id": 3, "method": "methode/bidon"})
verifier("méthode inconnue rejetée", mauvais["error"]["code"] == -32601)

# ── 4. transport stdio ───────────────────────────────────────────────
print("\n--- TRANSPORT STDIO ---")
import io                                               # noqa: E402
entree = io.StringIO('{"jsonrpc":"2.0","id":5,"method":"ping"}\n'
                     'pas du json\n'
                     '{"jsonrpc":"2.0","id":6,"method":"tools/list"}\n')
sortie = io.StringIO()
mcp.boucle(entree, sortie)
lignes = [json.loads(l) for l in sortie.getvalue().strip().split("\n")]
verifier("trois réponses pour trois entrées", len(lignes) == 3, str(len(lignes)))
verifier("ping répondu", lignes[0]["result"] == {})
verifier("JSON illisible signalé", lignes[1]["error"]["code"] == -32700)
verifier("tools/list après l'erreur", "tools" in lignes[2]["result"])

plan_essai.unlink(missing_ok=True)
serveur.shutdown()

print(f"\n{'TOUT PASSE' if KO == 0 else 'ÉCHECS'} ({OK} contrôles)")
sys.exit(0 if KO == 0 else 1)
