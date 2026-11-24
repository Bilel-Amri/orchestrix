"""Les 9 sources de collecte. Toutes gratuites, sans clé API.

  Wikipédia      vocabulaire du métier          (tout domaine)
  iTunes         applications concurrentes
  GitHub         projets similaires + README
  GitLab         projets similaires + README
  Apache         projets open source documentés
  OWASP          sécurité : exigences et bonnes pratiques
  SoftwareH      archive de code source
  TED            cahiers des charges publics UE
  SRS            squelette de document de référence

Toutes interrogées EN PARALLÈLE. Cache disque de 30 minutes.
"""

from __future__ import annotations

import base64
import hashlib
import math
import os
import json
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

from . import httpclient as requests

from . import config

UA = "Orchestrix/3.0 (https://example.org; contact@example.org)"
CACHE_DIR = Path.home() / ".cache" / "orchestrix"
TIMEOUT = config.TIMEOUT_SOURCE
CACHE_TTL = config.CACHE_MINUTES * 60
# Dernière erreur rencontrée par source (« 429 », « timeout »…). Un zéro peut
# vouloir dire « rien trouvé » ou « quota épuisé » ; l'utilisateur doit savoir
# lequel, sinon il croit que son sujet n'existe pas.
ERREURS: dict[str, str] = {}

SEUIL_TITRE = config.SEUIL_TITRE
SEUIL_CORPS = config.SEUIL_CORPS


VIDES = {"application", "logiciel", "systeme", "system", "service", "gestion",
         "app", "the", "and", "pour", "avec", "des", "les", "une", "dans", "sur",
         "par", "of", "for", "with"}


@dataclass
class Evidence:
    """Un document récupéré. Numéroté au moment de l'assemblage."""

    source: str
    title: str
    text: str
    url: str = ""
    meta: dict = field(default_factory=dict)


# ──────────────────────────────────────────────────────────────────────
# Utilitaires
# ──────────────────────────────────────────────────────────────────────
def norm(texte: str) -> str:
    t = unicodedata.normalize("NFD", texte.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def mots_significatifs(texte: str) -> list[str]:
    t = re.sub(r"[,;:/|()\[\]\"'«»]", " ", texte)
    return [m for m in t.split() if len(m) > 2 and m.lower() not in VIDES]


# Écritures non latines : un projet documenté dans ces écritures peut être
# pertinent pour le domaine, mais sa préférence vocale ne correspond pas à la
# requête. On ne l'écarte pas d'office ; on exige plus de recouvrement.
HORS_LATIN = re.compile(r"[\u0400-\u04FF\u0370-\u03FF\u4E00-\u9FFF\u0600-\u06FF]")


def _racine(mot: str) -> str:
    """Réduit un pluriel simple : projets → projet, taches → tache.

    Volontairement minimal : le but est d'éviter les faux positifs de
    sous-chaîne (« PME » trouvé dans « pmem »), pas de faire de la morphologie.
    """
    return mot[:-1] if len(mot) > 4 and mot.endswith("s") else mot


def _traits(mots: set[str], texte: str) -> int:
    """Nombre de mots de la requête réellement présents, en mots entiers."""
    jetons = {_racine(t) for t in re.findall(r"[a-z0-9]{3,}", norm(texte))}
    return sum(1 for m in mots if _racine(m) in jetons)


def _pertinents(evs: list[Evidence], graine: str, minimum: int = 0) -> list[Evidence]:
    """Garde les documents qui parlent vraiment du métier.

    Un document doit citer les mots de la requête dans son titre ou dans son
    corps, en mots entiers. C'est ce qui écarte un dépôt hors sujet qu'un
    simple « project » perdu dans 3000 caractères laissait passer.
    """
    mots = {m for m in norm(graine).split() if len(m) > 2 and m not in VIDES}
    if not mots:
        return evs
    besoin = 2 if len(mots) >= 3 else 1
    garde: list[Evidence] = []
    for e in evs:
        dans_titre = _traits(mots, e.title)
        dans_corps = _traits(mots, e.text[:2000])
        exige = besoin + (2 if HORS_LATIN.search(e.text[:500]) else 0)
        if (dans_titre >= 1 and dans_corps >= besoin) or dans_corps >= exige:
            garde.append(e)
    return garde or evs[:minimum]


def _raw_readme(depot: str) -> str:
    """Lit un README sans passer par l'API GitHub — donc sans quota.

    `raw.githubusercontent.com` n'est pas soumis à la limite de 60 lectures/heure
    de l'API. C'est le chemin à privilégier : sans jeton, l'API `core` tombe à
    zéro en quelques exécutions, et toutes les sources GitHub se vident.
    """
    for branche in ("HEAD", "main", "master"):
        for nom in ("README.md", "readme.md", "README.rst", "README.txt"):
            r = _get(f"https://raw.githubusercontent.com/{depot}/{branche}/{nom}")
            if r is not None and r.status_code == 200 and len(r.text) >= 200:
                return r.text
    return ""


def _repos_html(requete: str, limite: int) -> list[dict]:
    """Cherche des dépôts via la page HTML de GitHub — sans limite d'API.

    Repli quand l'API refuse ou renvoie zéro : la page publique de recherche
    contient les mêmes noms de dépôts, et son HTML ne coûte aucun quota.
    """
    r = _get("https://github.com/search",
             headers={"Accept": "text/html"},
             params={"q": requete, "type": "repositories"})
    if r is None or r.status_code != 200:
        return []
    vus: set[str] = set()
    out: list[dict] = []
    for m in re.finditer(r'href="/([\w.-]+/[\w.-]+)"', r.text):
        nom = m.group(1)
        if nom in vus or "/" not in nom:
            continue
        if nom.split("/")[0] in {"search", "topics", "orgs", "collections", "sponsors",
                                 "login", "signup", "features", "about", "pricing"}:
            continue
        vus.add(nom)
        out.append({"full_name": nom, "description": "", "topics": [],
                    "stargazers_count": 0, "html_url": f"https://github.com/{nom}"})
        if len(out) >= limite:
            break
    return out


def _requetes_progressives(requete: str, maxi: int = 3) -> list[str]:
    """Requêtes du plus fidèle au plus large : requête entière, puis paires.

    Les moteurs de recherche de GitHub et GitLab font un ET implicite : quatre
    mots deviennent quatre contraintes, et le résultat tombe à zéro. On dégrade
    donc progressivement au lieu de renvoyer une source vide.
    """
    mots = mots_significatifs(requete)[:4]
    if not mots:
        return []
    q = [" ".join(mots)]
    q += [" ".join(mots[i:i + 2]) for i in range(len(mots) - 1)]
    return q[:maxi]


def _cache_get(cle: str) -> list[Evidence] | None:
    f = CACHE_DIR / f"{hashlib.md5(cle.encode()).hexdigest()}.json"
    if not f.exists() or time.time() - f.stat().st_mtime > CACHE_TTL:
        return None
    try:
        return [Evidence(**d) for d in json.loads(f.read_text(encoding="utf-8"))]
    except Exception:
        return None


def _cache_set(cle: str, evs: list[Evidence]) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        f = CACHE_DIR / f"{hashlib.md5(cle.encode()).hexdigest()}.json"
        f.write_text(json.dumps([e.__dict__ for e in evs], ensure_ascii=False),
                     encoding="utf-8")
    except Exception:
        pass


def _get(url: str, headers: dict | None = None, **kw) -> requests.Response | None:
    entetes = {"User-Agent": UA}
    entetes.update(headers or {})
    try:
        return requests.get(url, headers=entetes, timeout=TIMEOUT, **kw)
    except requests.RequestException:
        return None


# ──────────────────────────────────────────────────────────────────────
# 1. Wikipédia
# ──────────────────────────────────────────────────────────────────────
def search_wikipedia(sujet: str, limite: int = 2) -> list[Evidence]:
    cle = f"wiki:{sujet}"
    if (c := _cache_get(cle)) is not None:
        return c

    for langue in ("fr", "en"):
        url = f"https://{langue}.wikipedia.org/w/api.php"
        r = _get(url, params={"action": "query", "list": "search", "srsearch": sujet,
                              "format": "json", "srlimit": limite})
        if r is None or r.status_code == 429:
            time.sleep(3)
            r = _get(url, params={"action": "query", "list": "search", "srsearch": sujet,
                                  "format": "json", "srlimit": limite})
        if r is None or r.status_code != 200:
            continue
        hits = r.json().get("query", {}).get("search", [])
        if not hits:
            continue

        out: list[Evidence] = []
        for h in hits:
            titre = h.get("title", "")
            e = _get(url, params={"action": "query", "prop": "extracts", "exintro": 1,
                                  "explaintext": 1, "titles": titre, "format": "json"})
            if e is None or e.status_code != 200:
                continue
            pages = e.json().get("query", {}).get("pages", {})
            extrait = next(iter(pages.values()), {}).get("extract", "") or ""
            if len(extrait) < 150:
                continue
            out.append(Evidence(
                source=f"wikipedia_{langue}", title=titre[:80], text=extrait[:2200],
                url=f"https://{langue}.wikipedia.org/wiki/{titre.replace(' ', '_')}"))
        if out:
            _cache_set(cle, out)
            return out
    return []


# ──────────────────────────────────────────────────────────────────────
# 2. iTunes
# ──────────────────────────────────────────────────────────────────────
def search_itunes(requete: str, pays: str = "fr", limite: int = 5) -> list[Evidence]:
    cle = f"itunes:{requete}:{pays}"
    if (c := _cache_get(cle)) is not None:
        return c

    mots = mots_significatifs(requete)
    out: list[Evidence] = []
    for i in range(len(mots)):
        essai = mots[i:]
        if not essai:
            break
        r = _get("https://itunes.apple.com/search",
                 params={"term": " ".join(essai), "entity": "software",
                         "country": pays, "limit": limite})
        if r is None or r.status_code != 200:
            continue
        res = r.json().get("results", [])
        if not res:
            continue
        out = [Evidence(
            source="itunes", title=it.get("trackName", "")[:80],
            text=(it.get("description") or "")[:2200],
            url=it.get("trackViewUrl", ""),
            meta={"note": it.get("averageUserRating")})
            for it in res if len(it.get("description") or "") >= 150]
        if out:
            out = _pertinents(out, requete)
            break
    _cache_set(cle, out)
    return out


# ──────────────────────────────────────────────────────────────────────
# 3. GitHub
# ──────────────────────────────────────────────────────────────────────
# Jetons facultatifs. Sans jeton, GitHub plafonne à 10 recherches/minute et
# 60 lectures/heure : sur des runs rapprochés, les sources GitHub et OWASP
# reviennent vides. Un jeton personnel lève ce plafond (rien à changer au code).
GH = {"Accept": "application/vnd.github+json", "User-Agent": UA}
if os.environ.get("GITHUB_TOKEN"):
    GH["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
GL = {"User-Agent": UA}
if os.environ.get("GITLAB_TOKEN"):
    GL["PRIVATE-TOKEN"] = os.environ["GITLAB_TOKEN"]


def _gh_get(url: str, **kw):
    try:
        return requests.get(url, headers=GH, timeout=TIMEOUT, **kw)
    except requests.RequestException:
        return None


def search_github(requete: str, limite: int = 3) -> list[Evidence]:
    """Projets GitHub proches du sujet, puis leur README.

    Deux chemins, dans cet ordre :

      1. l'API de recherche (précise, mais 10 requêtes/minute sans jeton) ;
      2. la page HTML de recherche (aucun quota) si l'API refuse ou ne trouve rien.

    La lecture des README passe par `raw.githubusercontent.com`, qui n'a pas de
    quota. L'API `core` de GitHub (60 lectures/heure) tombait à zéro en deux
    exécutions, et toutes les sources GitHub se vidaient d'un coup.
    """
    cle = f"github:{requete}"
    if (c := _cache_get(cle)) is not None:
        return c

    mots = mots_significatifs(requete)[:4]
    if not mots:
        return []
    mots_requete = {m for m in norm(requete).split() if len(m) > 2 and m not in VIDES}

    def chercher(q: str, n: int) -> list[dict]:
        for essai in range(2):
            r = _gh_get("https://api.github.com/search/repositories",
                        params={"q": q, "sort": "stars", "order": "desc", "per_page": n})
            if r is None:
                return []
            if r.status_code == 403:            # quota
                time.sleep(2 + 2 * essai)
                continue
            if r.status_code != 200:
                return []
            return r.json().get("items", [])
        return []

    def fiche(repo: dict) -> Evidence:
        return Evidence(source="github_readme", title=repo["full_name"],
                        text=(repo.get("description") or "") + " "
                             + " ".join(repo.get("topics") or []),
                        url=repo.get("html_url", ""))

    # ── requêtes, de la plus fidèle à la plus large ──────────────────
    essais = [f"{q} in:name,description" for q in _requetes_progressives(requete)]

    candidats: dict[str, dict] = {}
    for q in essais[:3]:
        for repo in chercher(q, limite * 6):
            if repo["full_name"] in candidats:
                continue
            if not _pertinents([fiche(repo)], requete):
                continue
            desc = (repo.get("description") or "") + " " + " ".join(repo.get("topics") or [])
            titre = repo["full_name"].replace("/", " ").replace("-", " ").replace("_", " ")
            repo["_score"] = (_traits(mots_requete, titre) >= 1,
                              _traits(mots_requete, desc),
                              min(repo["stargazers_count"], 500))
            candidats[repo["full_name"]] = repo
        if len(candidats) >= limite * 2:
            break

    # ── repli HTML : pas de quota, pas de description ────────────────
    if not candidats:
        for q in _requetes_progressives(requete):
            for repo in _repos_html(q, limite * 3):
                candidats[repo["full_name"]] = repo
            if len(candidats) >= limite:
                break

    # ── lecture des README, du meilleur candidat au moins bon ────────
    out: list[Evidence] = []
    for repo in sorted(candidats.values(),
                       key=lambda r: r.get("_score", (False, 0, 0)), reverse=True)[: limite * 3]:
        txt = _raw_readme(repo["full_name"])
        if not txt:
            continue
        ev = Evidence(source="github_readme", title=repo["full_name"], text=txt[:3000],
                      url=repo.get("html_url", ""),
                      meta={"stars": repo.get("stargazers_count", 0)})
        if _pertinents([ev], requete):
            out.append(ev)
        if len(out) >= limite:
            break

    _cache_set(cle, out)
    return out


# ──────────────────────────────────────────────────────────────────────
# 4. GitLab
# ──────────────────────────────────────────────────────────────────────
def search_gitlab(requete: str, limite: int = 3) -> list[Evidence]:
    cle = f"gitlab:{requete}"
    if (c := _cache_get(cle)) is not None:
        return c

    def chercher(q: str, n: int) -> list[dict]:
        r = _get("https://gitlab.com/api/v4/projects", headers=GL,
                 params={"search": q, "per_page": n, "order_by": "star_count",
                         "sort": "desc", "search_namespaces": "false"})
        if r is None:
            ERREURS["gitlab"] = "réseau"
            return []
        if r.status_code != 200:
            ERREURS["gitlab"] = f"HTTP {r.status_code}"
            return []
        projets = r.json()
        return projets if isinstance(projets, list) else []

    def fiche(p: dict) -> Evidence:
        return Evidence(source="gitlab_readme",
                        title=p.get("path_with_namespace", ""),
                        text=p.get("description") or "",
                        url=p.get("web_url", ""))

    candidats: dict[str, dict] = {}
    for q in _requetes_progressives(requete):
        for p in chercher(q, limite * 5):
            nom = p.get("path_with_namespace", "")
            if nom in candidats:
                continue
            if not _pertinents([fiche(p)], requete):
                continue
            candidats[nom] = p
        if len(candidats) >= limite * 2:
            break

    def lire(p: dict) -> Evidence | None:
        nom = p.get("path_with_namespace", "")
        # chemin direct d'abord : pas de quota d'API, pas de 404 de branche
        for branche in ("main", "master"):
            rd = _get(f"https://gitlab.com/{nom}/-/raw/{branche}/README.md")
            if rd is not None and rd.status_code == 200 and len(rd.text) >= 200:
                return Evidence(source="gitlab_readme", title=nom[:80],
                                text=rd.text[:3000], url=p.get("web_url", ""),
                                meta={"stars": p.get("star_count")})
        pid = str(p.get("id", ""))
        if not pid:
            return None
        rd = _get(f"https://gitlab.com/api/v4/projects/{pid}/repository/files/README.md/raw",
                  headers=GL, params={"ref": p.get("default_branch") or "main"})
        if rd is None or rd.status_code != 200 or len(rd.text) < 200:
            return None
        return Evidence(source="gitlab_readme", title=nom[:80],
                        text=rd.text[:3000], url=p.get("web_url", ""),
                        meta={"stars": p.get("star_count")})

    out: list[Evidence] = []
    for p in list(candidats.values())[: limite * 3]:
        ev = lire(p)
        if ev:
            out.append(ev)
        if len(out) >= limite:
            break
    _cache_set(cle, out)
    return out


# ──────────────────────────────────────────────────────────────────────
# 5. Apache Software Foundation
# ──────────────────────────────────────────────────────────────────────
APACHE_JSON = "https://projects.apache.org/json/foundation/projects.json"


def search_apache(requete: str, limite: int = 2) -> list[Evidence]:
    cle = f"apache:{requete}"
    if (c := _cache_get(cle)) is not None:
        return c

    r = _get(APACHE_JSON)
    if r is None or r.status_code != 200:
        return []
    try:
        projets = r.json()
    except Exception:
        return []

    mots = {w for w in norm(requete).split() if len(w) > 3}
    if not mots:
        return []

    out: list[Evidence] = []
    for nom, p in projets.items():
        if not isinstance(p, dict):
            continue
        cat = " ".join(p.get("category") or [])
        desc = " ".join(p.get("description") or [])
        blob = norm(f"{nom} {desc} {cat}")
        if not any(m in blob for m in mots):
            continue
        if not desc.strip():
            continue
        out.append(Evidence(
            source="apache", title=f"Apache {nom}",
            text=f"{desc[:1200]}\nCatégories : {cat}\nLicence : {p.get('license','')}",
            url=f"https://projects.apache.org/project.html?name={nom}",
            meta={"created": p.get("created")}))
        if len(out) >= limite:
            break
    _cache_set(cle, out)
    return out


# ──────────────────────────────────────────────────────────────────────
# 6. OWASP (sécurité)
# ──────────────────────────────────────────────────────────────────────
OWASP_REPOS = ["OWASP/CheatSheetSeries", "OWASP/Top10", "OWASP/wstg"]


def search_owasp(requete: str = "", limite: int = 2) -> list[Evidence]:
    """Les guides de sécurité OWASP : exigences techniques valables pour tout projet."""
    cle = f"owasp:{requete}"
    if (c := _cache_get(cle)) is not None:
        return c

    def lire(nom: str) -> Evidence | None:
        rd = _gh_get(f"https://api.github.com/repos/{nom}/readme")
        if rd is None or rd.status_code != 200:
            return None
        try:
            txt = base64.b64decode(rd.json()["content"]).decode("utf-8", "ignore")
        except Exception:
            return None
        return Evidence(source="owasp", title=nom, text=txt[:2500],
                        url=f"https://github.com/{nom}")

    out = [e for e in ThreadPoolExecutor(max_workers=3).map(lire, OWASP_REPOS) if e]
    out = out[:limite]
    _cache_set(cle, out)
    return out


# ──────────────────────────────────────────────────────────────────────
# 7. Software Heritage
# ──────────────────────────────────────────────────────────────────────
def search_softwareheritage(requete: str, limite: int = 2) -> list[Evidence]:
    cle = f"swh:{requete}"
    if (c := _cache_get(cle)) is not None:
        return c

    mot = (mots_significatifs(requete) or ["software"])[0]
    r = _get(f"https://archive.softwareheritage.org/api/1/origin/search/{mot}/",
             params={"limit": limite * 3})
    if r is None or r.status_code != 200:
        return []
    try:
        origines = r.json()
    except Exception:
        return []

    out: list[Evidence] = []
    for o in origines:
        url = (o.get("url") or "").strip()
        if not url:
            continue
        nom = url.rstrip("/").split("/")[-1][:80]
        texte = _readme_depuis_url(url)
        if texte:
            out.append(Evidence(source="softwareheritage", title=nom,
                                text=texte[:3000], url=url))
        else:
            out.append(Evidence(
                source="softwareheritage", title=nom,
                text=f"Dépôt archivé par Software Heritage : {url}\n"
                     f"Types de visite : {o.get('visit_types') or 'dépôt public archivé'}",
                url=url))
        if len(out) >= limite:
            break
    _cache_set(cle, out)
    return out


def _readme_depuis_url(url: str) -> str:
    """Software Heritage ne donne que des URLs : on va chercher le README derrière."""
    url = url.rstrip("/")
    candidats: list[str] = []
    m = re.match(r"https?://github\.com/([^/]+)/([^/]+)", url)
    if m:
        candidats.append(f"https://raw.githubusercontent.com/{m.group(1)}/{m.group(2)}/HEAD/README.md")
    m = re.match(r"https?://gitlab\.com/(.+?)(?:\.git)?$", url)
    if m:
        candidats.append(f"https://gitlab.com/{m.group(1)}/-/raw/HEAD/README.md")
    candidats += [f"{url}/raw/HEAD/README.md", f"{url}/-/raw/HEAD/README.md"]

    for c in candidats:
        r = _get(c)
        if r is None or r.status_code != 200:
            continue
        txt = r.text
        if len(txt) < 300 or "<html" in txt[:200].lower():
            continue
        return txt
    return ""


# ──────────────────────────────────────────────────────────────────────
# 8. TED — marchés publics
# ──────────────────────────────────────────────────────────────────────
def search_ted(requete: str, limite: int = 3) -> list[Evidence]:
    cle = f"ted:{requete}"
    if (c := _cache_get(cle)) is not None:
        return c
    try:
        r = requests.post(
            "https://api.ted.europa.eu/v3/notices/search",
            headers={"Content-Type": "application/json", "User-Agent": UA},
            json={"query": f'classification-cpv=72* AND FT~"{requete}"',
                  "fields": ["notice-title", "buyer-name", "description-lot"],
                  "limit": limite, "scope": "ACTIVE"},
            timeout=TIMEOUT)
    except requests.RequestException:
        return []
    if r.status_code != 200:
        return []

    out: list[Evidence] = []
    for n in r.json().get("notices", []) or []:
        titre = n.get("notice-title")
        if isinstance(titre, dict):
            titre = titre.get("fra") or next(iter(titre.values()), "")
        desc = n.get("description-lot")
        if isinstance(desc, dict):
            desc = desc.get("fra") or next(iter(desc.values()), "")
        if not desc:
            continue
        out.append(Evidence(source="ted", title=str(titre)[:120],
                            text=f"Cahier des charges public — {titre}\n{desc}"[:2200],
                            url="https://ted.europa.eu"))
    _cache_set(cle, out)
    return out


# ──────────────────────────────────────────────────────────────────────
# 9. SRS — squelette de document
# ──────────────────────────────────────────────────────────────────────
SRS_URL = "https://raw.githubusercontent.com/jam01/SRS-Template/master/srs-template-bare.md"


# ══════════════════════════════════════════════════════════════════════
# OWASP Top 10 — les 10 catégories officielles, en français
# ══════════════════════════════════════════════════════════════════════
# Chercher « sécurité » dans les README d'OWASP ne donne que des titres de
# dépôt (« ## OWASP Top 10 Leadership »). Les vrais intitulés de risques sont
# dans les fiches du Top 10 : on les récupère directement, et ils valent pour
# tout projet web, quel que soit le métier.
OWASP_BASE = "https://raw.githubusercontent.com/OWASP/Top10/master/2021/docs/fr/"
OWASP_FICHES = [
    "A01_2021-Broken_Access_Control.md",
    "A02_2021-Cryptographic_Failures.md",
    "A03_2021-Injection.md",
    "A04_2021-Insecure_Design.md",
    "A05_2021-Security_Misconfiguration.md",
    "A06_2021-Vulnerable_and_Outdated_Components.md",
    "A07_2021-Identification_and_Authentication_Failures.md",
    "A08_2021-Software_and_Data_Integrity_Failures.md",
    "A09_2021-Security_Logging_and_Monitoring_Failures.md",
    "A10_2021-Server-Side_Request_Forgery_(SSRF).md",
]


def fetch_owasp_top10() -> list[Evidence]:
    """Une fiche par catégorie de risque, avec son intitulé et son principe."""
    cle = "owasp_top10"
    if (c := _cache_get(cle)) is not None:
        return c

    def lire(nom: str) -> Evidence | None:
        r = _get(OWASP_BASE + nom)
        if r is None or r.status_code != 200:
            return None
        texte = r.text
        titre = ""
        for ligne in texte.splitlines():
            if ligne.startswith("# "):
                titre = re.split(r"!\[", ligne)[0]        # coupe au badge
                titre = re.sub(r"[#*\[\]]", " ", titre)
                titre = re.sub(r"\s+", " ", titre).strip()
                break
        # corps : badges, icônes, attributs de style et liens d'images retirés
        corps = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", texte)
        corps = re.sub(r"\{[^}]*\}", " ", corps)
        corps = re.sub(r"assets/\S+", " ", corps)
        corps = re.sub(r"\bicon\b", " ", corps)
        return Evidence(source="owasp", title=titre[:90] or nom,
                        text=(titre + "\n" + corps)[:2200],
                        url=f"https://owasp.org/Top10/{nom.split('_')[0]}_2021/")

    with ThreadPoolExecutor(max_workers=5) as pool:
        out = [e for e in pool.map(lire, OWASP_FICHES) if e]
    _cache_set(cle, out)
    return out


def fetch_srs() -> list[Evidence]:
    cle = "srs"
    if (c := _cache_get(cle)) is not None:
        return c
    r = _get(SRS_URL)
    if r is None or r.status_code != 200:
        return []
    titres = [l.lstrip("#").strip() for l in r.text.splitlines()
              if l.startswith("#") and len(l.lstrip("#").strip()) > 4][:22]
    if not titres:
        return []
    out = [Evidence(
        source="srs",
        title="Structure de référence d'un cahier des charges (IEEE SRS)",
        text="Sections attendues : " + " | ".join(titres),
        url=SRS_URL)]
    _cache_set(cle, out)
    return out


# ──────────────────────────────────────────────────────────────────────
# Orchestration : 9 sources en parallèle
# ──────────────────────────────────────────────────────────────────────
def collect_all(requete_fr: str, requete_en: str, sujet: str,
                concepts: list[str] | None = None,
                intention: str = "") -> tuple[list[Evidence], dict]:
    """Interroge les 9 sources.

    `concepts` et `intention` viennent de l'étape ① : ce sont les capacités
    GÉNÉRIQUES déduites du brief. Ils servent de requêtes de repli quand la
    requête principale ne rend rien — un brief commercial (« que mes équipes
    sachent qui fait quoi ») ne contient pas les mots « gestion de tâches »,
    mais l'analyse les a produits.

    Chaque source a sa requête naturelle : Wikipédia veut un concept
    encyclopédique, GitHub du vocabulaire de projet, iTunes du vocabulaire
    grand public. On ne leur envoie donc pas la même chaîne.
    """
    concepts = [c for c in (concepts or []) if c and len(c) > 3]
    replis = [*concepts, intention] if (concepts or intention) else []
    replis = [r for r in replis if r and len(r) > 3][:3]

    def avec_repli(source_fn, principales: list[str]):
        """Essaie la requête principale, puis les concepts si ça ne donne rien."""
        def executer() -> list[Evidence]:
            for q in principales:
                if not q or not q.strip():
                    continue
                res = source_fn(q)
                if res:
                    return res
            return []
        return executer

    taches: dict[str, object] = {
        # Wikipédia : un concept, pas une marque ni une phrase
        "wikipedia": avec_repli(search_wikipedia,
                                [sujet, *concepts[:2], requete_fr]),
        # iTunes : le grand public décrit une app par son usage
        "itunes": avec_repli(search_itunes, [requete_fr, *concepts[:2]]),
        # GitHub/GitLab : du vocabulaire de projet, en anglais
        "github": avec_repli(search_github,
                             [requete_en or requete_fr,
                              *[c for c in concepts[:2]], intention]),
        "gitlab": avec_repli(search_gitlab,
                             [requete_en or requete_fr, intention]),
        "apache": avec_repli(search_apache, [requete_en or requete_fr, intention]),
        # Les fiches officielles du Top 10 d'abord ; les README ensuite.
        "owasp": lambda: fetch_owasp_top10() or search_owasp(requete_fr),
        "swh": avec_repli(search_softwareheritage,
                          [requete_en or requete_fr, intention]),
        "ted": avec_repli(search_ted, [requete_fr, *concepts[:1]]),
        "srs": fetch_srs,
    }

    preuves: list[Evidence] = []
    traces: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=9) as pool:
        futures = {pool.submit(fn): nom for nom, fn in taches.items()}
        for fut in as_completed(futures):
            nom = futures[fut]
            try:
                res = fut.result()
            except Exception as exc:
                traces[nom] = {"n": 0, "erreur": str(exc)[:60]}
                continue
            traces[nom] = {"n": len(res)}
            if not res and nom in ERREURS:
                traces[nom]["erreur"] = ERREURS[nom]
            preuves.extend(res)
    preuves = dedupe(preuves)
    for nom in traces:
        traces[nom]["gardes"] = sum(1 for e in preuves if e.source == nom)
    return preuves, traces


# Sources de référence : elles apportent des exigences transverses (structure
# de cahier des charges, sécurité) qui ne citent jamais le domaine. Les filtrer
# sur le vocabulaire du métier reviendrait à les supprimer systématiquement.
# Seules les sources qui ne dépendent PAS du domaine : un squelette de cahier
# des charges et un guide de sécurité valent pour tout projet. Apache, GitHub,
# GitLab, iTunes et Software Heritage sont, eux, sélectionnés par mot-clé :
# ils doivent donc passer le filtre de pertinence comme les autres.
SOURCES_STRUCTURELLES = {"srs", "owasp", "ted"}


# ══════════════════════════════════════════════════════════════════════
# ÉTAPE 4 — VÉRIFICATION DE LA PERTINENCE DES PROJETS
# ══════════════════════════════════════════════════════════════════════
# Éliminer un projet AVANT de découper ses documents en passages évite de
# traiter (et de citer) des textes hors sujet. Le tri se fait sur trois
# signaux, du plus fiable au plus grossier :
#
#   1. recouvrement pondéré   — mots distinctifs de la requête présents ;
#   2. densité                — le sujet occupe-t-il le texte, ou y flotte-t-il ?
#   3. cohérence de section   — les puces du document parlent-elles du sujet ?
#
# Aucun de ces signaux ne dépend d'un domaine : ce sont des proportions.
@dataclass
class Verdict:
    evidence: Evidence
    score: float
    retenu: bool
    motif: str = ""


def _mots_requete(requete: str) -> list[str]:
    """Mots de la requête, ponctuation retirée.

    Sans ce nettoyage, « pme. » (avec le point de fin de phrase) devient un mot
    qui ne correspond à rien et fausse tous les scores de pertinence.
    """
    mots = re.findall(r"[a-z0-9]{3,}", norm(requete))
    return [m for m in dict.fromkeys(mots) if m not in VIDES]


def verifier_projets(documents: list[Evidence], requete: str,
                     plancher: float = 0.30) -> tuple[list[Evidence], list[Verdict]]:
    """Écarte les documents qui ne parlent pas du sujet, et explique pourquoi.

    Renvoie (documents retenus, verdicts complets). Les sources de référence
    (cahier des charges, OWASP, Apache, TED) sont conservées sans score : elles
    apportent des exigences transverses qui ne citent jamais le métier.
    """
    docs = list(documents)
    if not docs:
        return [], []

    mots = _mots_requete(requete)
    if not mots:
        return docs, [Verdict(d, 1.0, True, "pas de requête à vérifier") for d in docs]

    N = len(docs)
    textes = [norm(d.title + " " + d.text[:2500]) for d in docs]
    jetons = [{_racine(t) for t in re.findall(r"[a-z0-9]{3,}", t)} for t in textes]

    # poids d'un mot = sa rareté dans le corpus collecté. Un mot présent
    # partout ne distingue rien ; un mot présent deux fois distingue tout.
    idf: dict[str, float] = {}
    for m in dict.fromkeys(mots):
        df = sum(1 for j in jetons if _racine(m) in j)
        idf[m] = math.log((N + 1) / (df + 0.5))

    verdicts: list[Verdict] = []
    for doc, texte, jetons_doc in zip(docs, textes, jetons):
        if doc.source in SOURCES_STRUCTURELLES:
            verdicts.append(Verdict(doc, 1.0, True, "source de référence"))
            continue

        presents = [m for m in dict.fromkeys(mots) if _racine(m) in jetons_doc]
        total_poids = sum(idf.values()) or 1.0

        # 1. recouvrement pondéré
        recouvrement = sum(idf[m] for m in presents) / total_poids
        # 2. densité : le sujet est-il au cœur du document ?
        occurrences = sum(texte.count(m) for m in presents)
        densite = min(1.0, occurrences / max(1, len(texte) / 120))
        # 3. cohérence : le sujet apparaît-il dans le titre ?
        dans_titre = 1.0 if any(_racine(m) in jetons_doc and m in norm(doc.title) for m in presents) else 0.0

        score = round(0.6 * recouvrement + 0.3 * densite + 0.1 * dans_titre, 3)
        # Un document dont le TITRE porte un mot du sujet est presque toujours
        # pertinent, même si son texte est court : « Gestion de projet » sur
        # Wikipédia ne répétera pas « gérer » et « suivre », mais c'est le bon
        # sujet. Sans cette règle, les fiches courtes sont éliminées à tort.
        retenu = score >= plancher or (dans_titre and recouvrement >= 0.20)
        motif = "" if retenu else ("aucun mot du sujet" if not presents
                                  else "sujet trop peu présent")
        verdicts.append(Verdict(doc, score, retenu, motif))

    gardes = [v.evidence for v in verdicts if v.retenu]
    # plancher de sécurité : un filtre trop strict ne doit pas assécher la
    # collecte ; on garde le meilleur document de chaque source représentée.
    deja = {id(e) for e in gardes}
    meilleur: dict[str, Verdict] = {}
    for v in verdicts:
        if v.evidence.source in SOURCES_STRUCTURELLES:
            continue
        if v.evidence.source not in meilleur or v.score > meilleur[v.evidence.source].score:
            meilleur[v.evidence.source] = v
    # Le plancher ne sauve que le meilleur d'une source s'il porte un minimum
    # de signal. Un document à 0,00 n'est pas « le moins mauvais » : il est
    # hors sujet, et le garder reviendrait à réintroduire le bruit filtré.
    seuil_plancher = plancher * 0.5
    for v in meilleur.values():
        if id(v.evidence) not in deja and v.score >= seuil_plancher:
            v.retenu = True
            v.motif = "meilleur de sa source"
            gardes.append(v.evidence)

    return gardes, verdicts


def dedupe(preuves: list[Evidence]) -> list[Evidence]:
    par_titre: dict[str, Evidence] = {}
    for e in preuves:
        cle = re.sub(r"\W+", "", e.title.lower())[:40] or e.source
        if cle not in par_titre or len(e.text) > len(par_titre[cle].text):
            par_titre[cle] = e
    return list(par_titre.values())
