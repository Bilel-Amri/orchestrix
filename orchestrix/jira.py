"""Synchronisation avec Jira Cloud — API REST v3, bibliothèque standard.

Ce module fait trois choses, dans cet ordre de dépendance :

  1. il **vérifie** les identifiants et récupère les types de ticket réels du
     projet (un projet Jira n'accepte pas forcément « Tâche » ou « Story » :
     les identifiants de type varient d'une instance à l'autre et d'un projet
     à l'autre — les deviner produit une erreur 400 incompréhensible) ;
  2. il **crée** les tickets du plan, épic par épic, story par story ;
  3. il **relit** l'état des tickets pour rapatrier dans Orchestrix ce qui a
     bougé côté Jira (statut, assignation).

Authentification : e-mail + jeton d'API (Basic). C'est la méthode officielle
pour un compte Jira Cloud. Rien n'est stocké ailleurs que dans le fichier
local de la plateforme, et le jeton n'est jamais renvoyé au navigateur.
"""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.parse
import urllib.request

# Types de ticket Jira → type du plan
TYPE_PLAN = {
    "epic": "epic", "épic": "epic",
    "story": "story", "story ": "story", "user story": "story",
    "tâche": "task", "tache": "task", "task": "task",
    "sub-task": "subtask", "subtask": "subtask", "sous-tâche": "subtask",
    "bug": "task", "amélioration": "task", "improvement": "task",
}

# Nos natures de travail → intitulés cherchés côté Jira, par ordre de préférence
PREFERENCE_TYPES = ["story", "task", "tâche", "tache", "bug", "subtask"]


class JiraErreur(RuntimeError):
    """Erreur lisible par un humain, pas une trace HTTP."""


def _net(url: str) -> str:
    u = str(url or "").strip().rstrip("/")
    if u and not u.startswith("http"):
        u = "https://" + u
    if u.endswith("/rest/api/3"):
        u = u[: -len("/rest/api/3")]
    return u


def _entete(email: str, token: str) -> dict:
    brut = f"{email}:{token}".encode()
    return {
        "Authorization": "Basic " + base64.b64encode(brut).decode(),
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Orchestrix/2.0",
    }


def _appel(methode: str, url: str, email: str, token: str,
           corps: dict | None = None, timeout: int = 30) -> dict:
    donnees = json.dumps(corps).encode() if corps is not None else None
    req = urllib.request.Request(url, data=donnees, method=methode,
                                 headers=_entete(email, token))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            texte = r.read().decode("utf-8", "replace")
            return json.loads(texte) if texte.strip() else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:400]
        if exc.code == 401:
            raise JiraErreur("identifiants Jira refusés (401) — vérifiez l'e-mail "
                             "et le jeton d'API.") from exc
        if exc.code == 403:
            raise JiraErreur("accès refusé (403) — le compte n'a pas les droits "
                             f"de création sur ce projet. Détail : {detail}") from exc
        if exc.code == 404:
            raise JiraErreur(f"adresse introuvable (404) : {url}") from exc
        raise JiraErreur(f"Jira a répondu {exc.code} : {detail}") from exc
    except urllib.error.URLError as exc:
        raise JiraErreur(f"Jira injoignable ({exc.reason})") from exc
    except json.JSONDecodeError as exc:
        raise JiraErreur("réponse Jira illisible (JSON attendu)") from exc


# ── 1. Vérification et lecture des types ─────────────────────────────
def verifier(url: str, email: str, token: str, cle_projet: str = "") -> dict:
    base = _net(url)
    if not base:
        raise JiraErreur("adresse Jira manquante (ex. https://votre-entreprise.atlassian.net)")
    if not email or not token:
        raise JiraErreur("e-mail et jeton d'API sont nécessaires")

    moi = _appel("GET", f"{base}/rest/api/3/myself", email, token)
    projets = _appel("GET", f"{base}/rest/api/3/project/search?maxResults=50", email, token)
    liste = [{"cle": p.get("key"), "nom": p.get("name")} for p in projets.get("values", [])]

    types: list[dict] = []
    if cle_projet:
        brut = _appel("GET", f"{base}/rest/api/3/issue/createmeta/"
                             f"{urllib.parse.quote(cle_projet)}/issuetypes?maxResults=50",
                      email, token)
        types = [{"id": t.get("id"), "nom": t.get("name"),
                  "sous_taches": bool((t.get("subtask")))} for t in brut.get("values", [])]
        if not types:
            raise JiraErreur(f"aucun type de ticket créable dans le projet {cle_projet} "
                             "— vérifiez la clé du projet.")

    return {
        "compte": moi.get("displayName") or moi.get("emailAddress") or "compte Jira",
        "adresse_valide": base,
        "projets": liste,
        "types": types,
    }


def _type_pour(nom: str, types: list[dict]) -> dict | None:
    """Trouve le type Jira correspondant, en comparant sans accents."""
    def norm(x: str) -> str:
        return (str(x or "").lower().replace("é", "e").replace("è", "e")
                .replace("ê", "e").replace("â", "a").strip())
    cibles = [norm(x) for x in PREFERENCE_TYPES]
    if norm(nom) == "epic":
        cibles = ["epic"]
    trouve = {norm(t["nom"]): t for t in types}
    for c in cibles:
        for n, t in trouve.items():
            if n == c:
                return t
    for c in cibles:                     # correspondance partielle
        for n, t in trouve.items():
            if c in n:
                return t
    return next((t for t in types if not t.get("sous_taches")), None)


# ── 2. Création des tickets ──────────────────────────────────────────
def _doc(texte: str) -> dict:
    """Texte simple → document Atlassian (ADF), le format exigé par l'API v3."""
    paragraphes = [p.strip() for p in str(texte or "").split("\n") if p.strip()]
    return {
        "type": "doc", "version": 1,
        "content": [{"type": "paragraph",
                     "content": [{"type": "text", "text": p}]} for p in paragraphes]
                   or [{"type": "paragraph", "content": []}],
    }


def creer_tickets(plan: dict, taches_etat: dict, config: dict,
                  progresser=None) -> dict:
    """Crée épics, stories et tâches dans Jira.

    `taches_etat` sert de registre : chaque ticket créé y laisse sa clé Jira
    (`PROJ-123`), ce qui rend la synchronisation idempotente — relancer la
    création ne duplique pas ce qui existe déjà.
    """
    base = _net(config.get("url"))
    email, token = config.get("email", ""), config.get("token", "")
    cle_projet = str(config.get("cle_projet") or "").strip().upper()
    if not (base and email and token and cle_projet):
        raise JiraErreur("configuration Jira incomplète (adresse, e-mail, jeton, clé de projet)")

    info = verifier(base, email, token, cle_projet)
    types = info["types"]
    t_story = _type_pour("story", types)
    t_task = _type_pour("task", types)
    if not t_task:
        raise JiraErreur("le projet Jira n'accepte aucun type de ticket exploitable")
    # comparaison sans accents : « Épic » côté Jira français, « Epic » côté anglais
    t_epic = _type_pour("epic", types)

    liens = {k: v.get("jira") for k, v in taches_etat.items() if v.get("jira")}
    crees, erreurs = [], []
    epics_jira: dict[str, str] = {}
    stories_jira: dict[str, str] = {}

    def dire(txt):
        if progresser:
            progresser(txt)

    epics = plan.get("epics") or []
    for i, epic in enumerate(epics):
        eid = f"E{i + 1}"
        titre = f"{i + 1}. {epic.get('title', 'Épic')}"
        if t_epic:
            try:
                r = _appel("POST", f"{base}/rest/api/3/issue", email, token, {
                    "fields": {
                        "project": {"key": cle_projet},
                        "summary": titre[:250],
                        "description": _doc(epic.get("description", "")),
                        "issuetype": {"id": t_epic["id"]},
                    }})
                epics_jira[eid] = r.get("key")
                crees.append({"cle": epics_jira[eid], "objet": titre, "niveau": "épic"})
                dire(f"épic créé : {epics_jira[eid]}")
            except JiraErreur as exc:
                erreurs.append(f"épic « {titre} » : {exc}")

        for story in epic.get("stories") or []:
            sid = story.get("cle") or f"{eid}-{len(stories_jira) + 1}"
            champs = {
                "project": {"key": cle_projet},
                "summary": str(story.get("title", "Story"))[:250],
                "description": _doc(_recit(story)),
                "issuetype": {"id": (t_story or t_task)["id"]},
            }
            if eid in epics_jira:
                champs["parent"] = {"key": epics_jira[eid]}
            try:
                r = _appel("POST", f"{base}/rest/api/3/issue", email, token,
                           {"fields": champs})
                stories_jira[sid] = r.get("key")
                crees.append({"cle": stories_jira[sid], "objet": champs["summary"],
                              "niveau": "story"})
            except JiraErreur as exc:
                erreurs.append(f"story « {champs['summary']} » : {exc}")
                stories_jira[sid] = ""

            for t in story.get("tasks") or []:
                notre = str(t.get("cle") or "")
                if notre and liens.get(notre):
                    continue                       # déjà créée : on ne duplique pas
                champs = {
                    "project": {"key": cle_projet},
                    "summary": str(t.get("title", "Tâche"))[:250],
                    "description": _doc(t.get("description", "")),
                    "issuetype": {"id": t_task["id"]},
                }
                parent = stories_jira.get(sid)
                if parent:
                    champs["parent"] = {"key": parent}
                try:
                    r = _appel("POST", f"{base}/rest/api/3/issue", email, token,
                               {"fields": champs})
                    cle_jira = r.get("key")
                    if notre and cle_jira:
                        liens[notre] = cle_jira
                    crees.append({"cle": cle_jira, "objet": champs["summary"],
                                  "niveau": "tâche", "notre_cle": notre})
                except JiraErreur as exc:
                    erreurs.append(f"tâche « {champs['summary']} » : {exc}")

    return {"crees": crees, "erreurs": erreurs, "liens": liens,
            "epics": epics_jira, "stories": stories_jira}


def _recit(story: dict) -> str:
    morceaux = [
        f"En tant que {story.get('as_a', 'utilisateur')}, je veux "
        f"{story.get('i_want', '')} afin de {story.get('so_that', '')}.",
    ]
    criteres = story.get("acceptance") or []
    if criteres:
        morceaux.append("\nCritères d'acceptation :")
        morceaux += [f"– {c}" for c in criteres]
    return "\n".join(morceaux)


# ── 3. Relecture de l'état ───────────────────────────────────────────
# Statut Jira → notre statut. La correspondance se fait sur les catégories
# standard de Jira (« To Do », « In Progress », « Done »), qui existent dans
# toutes les langues, plutôt que sur les libellés d'un seul tableau.
CATEGORIE_VERS_STATUT = {
    "new": "a_faire",
    "indeterminate": "en_cours",
    "done": "termine",
}


def relire(config: dict, liens: dict[str, str]) -> dict:
    """Rapatrie le statut et l'assignation réels des tickets connus."""
    base = _net(config.get("url"))
    email, token = config.get("email", ""), config.get("token", "")
    cles = [c for c in liens.values() if c]
    if not cles:
        return {"tickets": [], "erreurs": ["aucun ticket Jira rattaché"]}

    sortie, erreurs = [], []
    # par paquets de 40 : au-delà, l'URL devient trop longue
    for debut in range(0, len(cles), 40):
        paquet = cles[debut:debut + 40]
        jql = "key in (" + ",".join(paquet) + ")"
        url = (f"{base}/rest/api/3/search/jql?jql={urllib.parse.quote(jql)}"
               f"&maxResults=100&fields=summary,status,assignee,issuetype")
        try:
            r = _appel("GET", url, email, token)
        except JiraErreur as exc:
            erreurs.append(str(exc))
            continue
        for issue in r.get("issues", []):
            champs = issue.get("fields") or {}
            statut = champs.get("status") or {}
            categorie = (statut.get("statusCategory") or {}).get("key", "new")
            sortie.append({
                "cle": issue.get("key"),
                "resume": champs.get("summary", ""),
                "statut_jira": statut.get("name", ""),
                "statut_orchestrix": CATEGORIE_VERS_STATUT.get(categorie, "a_faire"),
                "assigne": ((champs.get("assignee") or {}).get("displayName") or ""),
            })
    return {"tickets": sortie, "erreurs": erreurs}


def appliquer(etat_taches: dict, tickets: list[dict]) -> int:
    """Reporte l'état Jira sur nos tâches. Renvoie le nombre de changements."""
    par_cle = {v.get("jira"): k for k, v in etat_taches.items() if v.get("jira")}
    changements = 0
    for tk in tickets:
        notre = par_cle.get(tk.get("cle"))
        if not notre:
            continue
        t = etat_taches[notre]
        if tk.get("statut_orchestrix") and t.get("statut") != tk["statut_orchestrix"]:
            t["historique"].append({
                "date": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M"),
                "texte": f"Jira : {tk.get('statut_jira')} → {tk['statut_orchestrix']}",
                "auteur": "Jira",
            })
            t["statut"] = tk["statut_orchestrix"]
            changements += 1
        if tk.get("assigne"):
            t["jira_assigne"] = tk["assigne"]
    return changements
