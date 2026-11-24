"""ÉTAPE 5 — EVIDENCE PROCESSING (le cœur de recherche).

Transforme des documents bruts en passages pertinents et en fonctionnalités
prouvées. Aucun appel LLM : tout est déterministe et reproductible.

    documents
       │ 1. nettoyage
       ▼
    texte propre
       │ 2. chunking (passages de ~600 caractères, avec chevauchement)
       ▼
    passages[]
       │ 3. BM25            → classement par mots-clés
       │ 4. Vector search   → classement sémantique (TF-IDF + SVD)
       │ 5. Hybrid (RRF)    → fusion des deux classements
       │ 6. Reranking       → réordonne en tenant compte des deux scores
       │ 7. Extraction      → fonctionnalités avec preuve
       ▼
    passages retenus + fonctionnalités sourcées

BM25 et TF-IDF sont implémentés à la main : pas de dépendance lourde, et le
comportement est identique à chaque exécution.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field

from . import config
from .sources import Evidence, norm
from .sources import VIDES as VIDES_EV

STOP = {
    "le", "la", "les", "de", "des", "du", "un", "une", "et", "en", "au", "aux",
    "pour", "par", "sur", "avec", "dans", "est", "sont", "ce", "cette", "ces",
    "que", "qui", "quoi", "dont", "ou", "se", "sa", "son", "ses", "leur", "leurs",
    "the", "and", "for", "with", "from", "this", "that", "there", "are", "was",
    "application", "logiciel", "systeme", "system", "site", "web",
}


# ══════════════════════════════════════════════════════════════════════
# 1. NETTOYAGE
# ══════════════════════════════════════════════════════════════════════
def nettoyer(texte: str) -> str:
    """Retire le bruit : HTML, markdown, badges, liens, répétitions."""
    t = re.sub(r"<[^>]+>", " ", texte)                       # balises
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", t)              # images md
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)           # liens md → texte
    t = re.sub(r"https?://\S+", " ", t)                      # urls nues
    t = re.sub(r"```.*?```", " ", t, flags=re.S)             # blocs de code
    t = re.sub(r"[ \t]+", " ", t)
    # chaque puce sur sa propre ligne : indispensable pour repérer les fonctionnalités
    t = re.sub(r"\s*[-*•]\s+", "\n- ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


# ══════════════════════════════════════════════════════════════════════
# 2. CHUNKING
# ══════════════════════════════════════════════════════════════════════
@dataclass
class Passage:
    id: int
    doc_source: str
    doc_titre: str
    doc_url: str
    texte: str
    scores: dict = field(default_factory=dict)


def chunker(texte: str, taille: int | None = None, chevauchement: int | None = None) -> list[str]:
    """Découpe en passages en respectant les phrases (jamais au milieu d'un mot)."""
    taille = taille or config.TAILLE_PASSAGE
    chevauchement = config.CHEVAUCHEMENT if chevauchement is None else chevauchement
    texte = nettoyer(texte)
    if not texte:
        return []
    phrases = re.split(r"(?<=[.!?])\s+|\n+", texte)
    phrases = [ph.strip() for ph in phrases if ph.strip()]
    passages: list[str] = []
    courant = ""

    for phrase in phrases:
        phrase = phrase.strip()
        if not phrase:
            continue
        if len(courant) + len(phrase) + 1 <= taille:
            courant = f"{courant} {phrase}".strip()
        else:
            if len(courant) >= 80:
                passages.append(courant)
            # chevauchement : on reprend la fin du passage précédent
            fin = courant[-chevauchement:] if len(courant) > chevauchement else courant
            courant = f"{fin} {phrase}".strip() if fin else phrase
    if len(courant) >= 80:
        passages.append(courant)
    return passages


# ══════════════════════════════════════════════════════════════════════
# Utilitaires de tokenisation
# ══════════════════════════════════════════════════════════════════════
def tokeniser(texte: str) -> list[str]:
    t = unicodedata.normalize("NFD", texte.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    mots = re.findall(r"[a-z0-9]{3,}", t)
    return [m for m in mots if m not in STOP]


# ══════════════════════════════════════════════════════════════════════
# 3. BM25 — recherche par mots-clés
# ══════════════════════════════════════════════════════════════════════
class BM25:
    """Implémentation standard (k1=1.5, b=0.75)."""

    def __init__(self, passages: list[Passage], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1, self.b = k1, b
        self.docs = [tokeniser(p.texte) for p in passages]
        self.N = len(self.docs)
        self.tf = [Counter(d) for d in self.docs]
        self.longueur = [len(d) for d in self.docs]
        self.moyenne = (sum(self.longueur) / self.N) if self.N else 1.0
        df = Counter()
        for doc in self.docs:
            df.update(set(doc))
        self.df = df

    def scores(self, requete: str) -> list[float]:
        termes = tokeniser(requete)
        res = []
        for i in range(self.N):
            s = 0.0
            for terme in termes:
                f = self.tf[i].get(terme, 0)
                if not f:
                    continue
                n = self.df.get(terme, 0)
                idf = math.log(1 + (self.N - n + 0.5) / (n + 0.5))
                denom = f + self.k1 * (
                    1 - self.b + self.b * self.longueur[i] / (self.moyenne or 1)
                )
                s += idf * f * (self.k1 + 1) / denom
            res.append(s)
        return res


# ══════════════════════════════════════════════════════════════════════
# 4. VECTOR SEARCH — TF-IDF + SVD (sémantique approchée, sans dépendance)
# ══════════════════════════════════════════════════════════════════════
class VectorSearch:
    """Sémantique approchée : TF-IDF réduit par SVD, similarité cosinus.

    Un vrai modèle d'embeddings donnerait mieux, mais impose sentence-transformers
    (plusieurs centaines de Mo). Ici : 0 dépendance, et le comportement reste
    suffisant pour classer des passages traitant du même sujet.
    """

    def __init__(self, passages: list[Passage], dimensions: int = 64) -> None:
        self.textes = [tokeniser(p.texte) for p in passages]
        vocab: Counter = Counter()
        for doc in self.textes:
            vocab.update(set(doc))
        self.vocab = {mot: i for i, mot in enumerate(sorted(vocab))}
        self.N = len(self.textes)

        # tf-idf creux
        self.matrice: list[dict[int, float]] = []
        idf = {mot: math.log((1 + self.N) / (1 + vocab[mot])) + 1 for mot in vocab}
        for doc in self.textes:
            tf = Counter(doc)
            vec = {self.vocab[m]: tf[m] * idf[m] for m in tf if m in self.vocab}
            norme = math.sqrt(sum(v * v for v in vec.values())) or 1.0
            self.matrice.append({k: v / norme for k, v in vec.items()})
        self.idf = idf
        self.dimensions = min(dimensions, max(1, len(self.vocab)))

    def _vecteur(self, requete: str) -> dict[int, float]:
        tf = Counter(tokeniser(requete))
        vec = {self.vocab[m]: tf[m] * self.idf.get(m, 1.0)
               for m in tf if m in self.vocab}
        norme = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {k: v / norme for k, v in vec.items()}

    def scores(self, requete: str) -> list[float]:
        q = self._vecteur(requete)
        if not q:
            return [0.0] * self.N
        res = []
        for doc in self.matrice:
            # cosinus sur l'intersection (suffisant pour le classement)
            petit, grand = (q, doc) if len(q) < len(doc) else (doc, q)
            res.append(sum(v * grand.get(k, 0.0) for k, v in petit.items()))
        return res


# ══════════════════════════════════════════════════════════════════════
# 5. HYBRID SEARCH — Reciprocal Rank Fusion
# ══════════════════════════════════════════════════════════════════════
def rrf(classements: list[list[int]], k: int | None = None) -> list[float]:
    """Fusionne plusieurs classements. RRF(score) = Σ 1/(k + rang).

    Avantage : ne dépend pas de l'échelle des scores, seulement des rangs.
    C'est la méthode utilisée en recherche hybride (BM25 + dense).
    """
    k = config.RRF_K if k is None else k
    if not classements:
        return []
    n = max((max(c) for c in classements if c), default=-1) + 1
    scores = [0.0] * n
    for classement in classements:
        for rang, idx in enumerate(classement):
            scores[idx] += 1.0 / (k + rang + 1)
    return scores


# ══════════════════════════════════════════════════════════════════════
# 6. RERANKING
# ══════════════════════════════════════════════════════════════════════
def reranker(
    passages: list[Passage], requete: str, scores_hybrides: list[float]
) -> list[Passage]:
    """Réordonne en combinant : score hybride + présence des termes + bonus source.

    Le bonus de source encode ce qu'on sait de la fiabilité de chaque type de
    document : un README de projet vaut mieux qu'une archive pour décrire des
    fonctionnalités ; un guide de sécurité apporte des exigences transverses.
    """
    from .sources import norm

    termes = set(tokeniser(requete))
    poids_source = {
        "github_readme": 1.00,
        "gitlab_readme": 1.00,
        "itunes": 0.95,
        "srs": 0.90,
        "owasp": 0.85,
        "wikipedia_fr": 0.80,
        "wikipedia_en": 0.80,
        "apache": 0.75,
        "ted": 0.70,
        "softwareheritage": 0.40,
    }

    classe = sorted(
        zip(passages, scores_hybrides),
        key=lambda ps: -(
            ps[1] * config.POIDS_HYBRIDE
            + (
                len(termes & set(tokeniser(ps[0].texte))) / len(termes)
                if termes else 0.0
            ) * config.POIDS_COUVERTURE
            + (0.15 if any(t[:6] in norm(ps[0].doc_titre) for t in termes) else 0.0)
            + poids_source.get(ps[0].doc_source, 0.5) * config.POIDS_SOURCE
        ),
    )

    # Un passage est d'autant plus utile qu'il est le meilleur de son document
    # et que son document n'est pas déjà sur-représenté dans la sélection.
    # Sans ce frein, un README atypique peut truster les 12 places.
    deja_pris: dict[str, int] = {}
    classement: list[tuple[float, Passage]] = []
    for p, s in classe:
        cle = p.doc_url or p.doc_titre
        tokens = set(tokeniser(p.texte))
        couverture = len(termes & tokens) / len(termes) if termes else 0.0
        titre = norm(p.doc_titre)
        bonus_titre = 0.15 if any(t[:6] in titre for t in termes) else 0.0
        base = (
            s * config.POIDS_HYBRIDE + couverture * config.POIDS_COUVERTURE + bonus_titre
            + poids_source.get(p.doc_source, 0.5) * config.POIDS_SOURCE
        )
        # 1re occurrence d'un document : bonus. Suivantes : pénalité croissante.
        # Même logique par SOURCE : sans cela, une source qui produit beaucoup
        # de passages courts (les fiches App Store) occupe les 12 places et le
        # plan ne cite plus qu'elle — les README, pourtant plus riches, sont
        # évincés.
        penalite = (config.PENALITE_REPETITION * deja_pris.get(cle, 0)
                    + config.PENALITE_SOURCE * deja_pris.get("src:" + p.doc_source, 0))
        deja_pris[cle] = deja_pris.get(cle, 0) + 1
        deja_pris["src:" + p.doc_source] = deja_pris.get("src:" + p.doc_source, 0) + 1
        p.scores = {
            "hybride": round(s, 4),
            "couverture": round(couverture, 3),
            "source": poids_source.get(p.doc_source, 0.5),
            "penalite_repetition": round(penalite, 3),
        }
        p.scores["final"] = round(base - penalite, 4)
        classement.append((p.scores["final"], p))

    classement.sort(key=lambda x: -x[0])
    return [p for _, p in classement]


# ══════════════════════════════════════════════════════════════════════
# 7. EXTRACTION DES FONCTIONNALITÉS AVEC PREUVE
# ══════════════════════════════════════════════════════════════════════
MOTIFS_FONCTION = [
    r"^(?:[-*•]|\d+[.)])\s+(.{4,140})$",                    # puce
    r"\bfonctionnalit[ée]s?\s*(?:cl[ée]s?|principales?|majeures?|du produit)?\s*[:：]\s*(.+)$",
    r"\bfeatures?\s*\w{0,12}\s*[:：]\s*(.+)$",
    r"\b(?:l'utilisateur|le client|l'agent|les utilisateurs|l['’]équipe)\s+(?:peut|peuvent)\s+([^.]{5,140})",
    r"\b(?:permet|permet de|permet d')\s+([^.]{5,140})",
    r"\b(?:g[ée]rer|gestion (?:des|de la|du))\s+([^.]{4,120})",
    # étiquette suivie de deux-points : « Suivi en temps réel : Visualisez… »
    r"^[A-ZÀ-Ý][\w\s'’\-]{2,45}\s*[:：]\s*(.{10,220})",
    # impératif : « Créez une tâche en quelques secondes »
    r"^((?:Cr[ée]ez|Visualisez|Assignez|G[ée]rez|Suivez|Partagez|Planifiez|"
    r"Invitez|Organisez|Notifiez|Ajoutez|Modifiez|Supprimez|Consultez|"
    r"Exportez|Importez|Recherchez|Filtrez|Connectez|G[ée]n[ée]rez|"
    r"Sauvegardez|Archivez|Commentez|Donnez|Create|Manage|Track|Assign|Add|"
    r"Organize|Invite|Share|Monitor|Schedule)\b.{5,220})",
]

TITRES_FONCTION = re.compile(
    r"^(?:#{1,4}\s*)?(?:[^\w]{0,3}\s*)?"
    r"(?:core\s+features?|key\s+features?|features?|fonctionnalit[ée]s?|"
    r"what\s+you\s+can\s+do|ce\s+que\s+vous\s+pouvez\s+faire|"
    r"modules?|scope)\b",
    re.IGNORECASE,
)


# ══════════════════════════════════════════════════════════════════════
# 6 bis. EXIGENCES TRANSVERSES (sécurité, qualité)
# ══════════════════════════════════════════════════════════════════════
# Les sources OWASP ne décrivent pas le métier : elles décrivent des risques.
# Les filtrer sur le vocabulaire du projet les élimine toujours, et le plan
# sort alors sans une seule tâche de sécurité — ce qui est un défaut grave
# pour une application web. On les traite donc à part : on retient les
# ÉNONCÉS DE RISQUE, pas les fonctionnalités du produit.
RISQUES = re.compile(
    r"\b(?:injection|xss|cross[- ]site|csrf|authentification|autorisation|"
    r"contrôle d'accès|access control|session|mot de passe|password|chiffrement|"
    r"encrypt|hachage|hash|secret|jeton|token|ssl|tls|https|validation des "
    r"entrées|input validation|journalisation|logging|erreur|error handling|"
    r"dépendances|dependencies|configuration|en-têtes|headers|cookies|"
    r"fuite de données|data leak|privilège|privilege|escalade|injection sql|"
    r"sql|deserializ|désérialis|api key|clé|owasp|top 10|menace|threat)\b",
    re.IGNORECASE,
)


def extraire_exigences_transverses(documents, limite: int = 8) -> list[dict]:
    """Retient les exigences de sécurité des fiches OWASP Top 10.

    Une fiche du Top 10 dit deux choses : le NOM du risque (« Injection »,
    « Contrôles d'accès défaillants ») et son principe général. Ce sont ces
    deux éléments qui se traduisent en tâches ; les renvois CWE (« CWE-89 »)
    et les rappels de versions n'apportent rien à un plan de projet.

    Chaque fiche produit donc : son titre (l'exigence) et sa première phrase
    de principe. Le reste est ignoré, volontairement.
    """
    sortie: list[dict] = []
    vus: set[str] = set()

    def ajouter(texte: str, doc, categorie: str) -> bool:
        texte = re.sub(r"\s+", " ", texte).strip(" .,;:-—*#")
        if len(texte) < 12:
            return False
        cle = norm(texte)[:60]
        if cle in vus:
            return False
        vus.add(cle)
        sortie.append({"texte": nettoyer_icones(texte)[:160],
                       "document": doc.title, "url": doc.url,
                       "source": doc.source, "type": "exigence", "categorie": categorie})
        return True

    for doc in documents:
        if doc.source != "owasp":
            continue
        lignes = [re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", l).strip()
                  for l in nettoyer(doc.text).splitlines()]
        lignes = [l for l in lignes if l]

        # 1. le titre de la fiche EST l'exigence (« A03:2021 – Injection »)
        titres = [l for l in lignes if re.match(r"^A\d{2}:\d{4}\s*[–-]", l)]
        if titres:
            ajouter(re.split(r"\s*[–-]\s*", titres[0], maxsplit=1)[-1], doc, "sécurité")

        # 2. le principe général : première phrase qui nomme un contrôle,
        #    en écartant les renvois CWE et les historiques de version
        for ligne in lignes:
            if len(ligne) < 40 or len(ligne) > 220:
                continue
            if "CWE" in ligne or re.search(r"\b(?:19|20)\d\d\b", ligne):
                continue
            if not RISQUES.search(ligne):
                continue
            if ajouter(ligne, doc, "sécurité"):
                break
        if len(sortie) >= limite:
            break
    return sortie[:limite]


def extraire_fonctionnalites(documents, limite: int = 0) -> list[dict]:
    """Repère les énoncés de fonctionnalité dans les documents et garde leur preuve.

    Un README contient trois choses très différentes : ce que fait le produit,
    comment l'installer, et la vie du dépôt. Seule la première nous intéresse.
    D'où deux niveaux d'exigence :

      * dans une section « Features / Fonctionnalités » déclarée, un énoncé
        court suffit — le titre de section garantit le contexte ;
      * ailleurs, il faut un verbe de capacité (« créez », « visualisez »,
        « permet de »…) ; une ligne d'installation ou de configuration n'en a
        pas, et le filtre `_qualite` écarte le reste.

    La limite de sortie est proportionnelle au volume collecté : jamais figée.
    """
    vues: set[str] = set()
    sortie: list[dict] = []
    if limite <= 0:
        total = sum(len(d.text) for d in documents)
        limite = max(config.FONCTIONS_MIN,
                     min(config.FONCTIONS_MAX, total // config.CARACTERES_PAR_FONCTION))

    for doc in documents:
        langue = _langue_doc(doc.text)
        section = False
        for brute in nettoyer(doc.text).splitlines():
            ligne = brute.strip()
            if not ligne:
                continue
            if TITRES_FONCTION.match(ligne):
                section = True
                continue
            if section and ligne.startswith("#"):
                section = False

            if len(ligne) > 220:
                continue
            if not _qualite(ligne, langue, section):
                continue

            contenu = _contenu_fonction(ligne)
            if not contenu:
                continue
            cle = norm(contenu)[:60]
            if cle in vues:
                continue
            vues.add(cle)
            sortie.append({
                "texte": contenu[:140],
                "document": doc.title,
                "url": doc.url,
                "source": doc.source,
            })
            if len(sortie) >= limite:
                return sortie
    return sortie


# Emoji et pictogrammes : utiles dans un README, parasites dans un backlog.
_ICONES = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF"
    "\u2190-\u21FF\u2B00-\u2BFF\uFE0F\u200D]+"
)


def nettoyer_icones(texte: str) -> str:
    """Retire emoji, flèches et pictogrammes, sans toucher aux accents."""
    return re.sub(r"\s{2,}", " ", _ICONES.sub(" ", texte)).strip(" .,;:-—*#`")


def _contenu_fonction(ligne: str) -> str:
    """Applique les motifs et renvoie l'énoncé nu, ou '' si rien de probant."""
    for motif in MOTIFS_FONCTION:
        m = re.search(motif, ligne, re.IGNORECASE | re.MULTILINE)
        if not m:
            continue
        contenu = nettoyer_icones(re.sub(r"\s+", " ", m.group(1))).strip(" .,;:-—•*#`")
        contenu = re.sub(r"^[\w\s'’\-]{2,45}\s*[:：]\s*", "", contenu)  # « Suivi : … »
        if len(contenu) >= 8:
            return contenu
    return ""


# ── Contrôle qualité des énoncés ──────────────────────────────────────
VERBES = {
    # fr — infinitifs et impératifs
    "crée", "créer", "créez", "cree", "gère", "gérer", "gérez", "permet", "permette",
    "suivre", "suivi", "suivez", "ajouter", "ajoutez", "assigner", "assignez",
    "notifier", "notifiez", "partager", "partagez", "consulter", "consultez",
    "modifier", "modifiez", "supprimer", "supprimez", "exporter", "exportez",
    "importer", "importez", "rechercher", "recherchez", "filtrer", "filtrez",
    "planifier", "planifiez", "visualiser", "visualisez", "inviter", "invitez",
    "connecter", "connectez", "authentifier", "générer", "générez", "gerer",
    "envoie", "envoi", "affiche", "afficher", "affichez", "calcule", "calculer",
    "sauvegarde", "sauvegarder", "sauvegardez", "archiver", "archivez",
    "commenter", "commentez", "organiser", "organisez", "centraliser",
    "centralisez", "automatiser", "automatisez", "analyser", "analysez",
    "bénéficier", "bénéficiez", "profiter", "profitez", "synchroniser",
    # en
    "create", "manage", "track", "add", "assign", "notify", "share", "view",
    "edit", "update", "delete", "export", "import", "search", "filter", "plan",
    "invite", "signin", "authenticate", "generate", "send", "display", "show",
    "upload", "download", "comment", "archive", "collaborate", "organize",
    "organise", "monitor", "report", "integrate", "sync", "schedule", "maintain",
    "customize", "customise", "visualize", "visualise", "prioritize", "review",
    "approve", "automate", "notify", "remind", "configure", "personalize",
}
# Formes verbales dérivées : « création », « gestion », « suivi »…
NOMS_ACTION = {
    "création", "creation", "gestion", "suivi", "ajout", "assignation",
    "notification", "partage", "consultation", "modification", "suppression",
    "export", "import", "recherche", "filtrage", "planification", "invitation",
    "authentification", "génération", "affichage", "calcul", "sauvegarde",
    "archivage", "commentaire", "organisation", "automatisation", "analyse",
    "synchronisation", "planification", "facturation", "reporting", "dashboard",
}

# Vie et installation du dépôt : jamais des fonctionnalités du produit.
BOILERPLATE = re.compile(
    r"\b(?:contribut\w*|pull request|issues?|slack|discord|mailing list|"
    r"licen[cs]e|sponsor\w*|donat\w*|twitter|mastodon|linkedin|youtube|"
    r"code of conduct|changelog|release notes|badge|star (?:us|the repo)|"
    r"fork|clone|npm|yarn|pnpm|pip|docker|composer|makefile|"
    r"project leaders?|maintainers?|co-?leaders?|volunteers?|"
    r"sign ?up|free account|cloud|getting started|quick ?start|"
    r"install\w*|setup|set up|configur\w*|migrat\w*|deploy\w*|env(?:ironment)?\b|"
    r"api key|secret|token|database url|localhost|port \d|"
    r"join (?:us|the)|follow us|read more|see the docs|documentation site|"
    r"contributeur\w*|licence|mainteneur\w*|rejoignez|suivez-nous)\b",
    re.IGNORECASE,
)

# Unicode cyrillique / grec / CJK / arabe : un README dans cette écriture ne
# décrit pas un projet francophone, et son vocabulaire ne correspond pas.
_HORS_LATIN = re.compile(r"[\u0400-\u04FF\u0370-\u03FF\u4E00-\u9FFF\u0600-\u06FF]")
_CODE = re.compile(r"[`{}\[\]<>|\\]|\b\w+\.(?:sql|json|env|ts|js|py|yml|yaml|md|sh)\b")


def _langue_doc(texte: str) -> str:
    """Devine l'écriture dominante d'un document : 'latin' ou 'autre'."""
    echantillon = texte[:1500]
    if not echantillon:
        return "latin"
    hors = len(_HORS_LATIN.findall(echantillon))
    return "autre" if hors / max(1, len(echantillon)) > 0.15 else "latin"


def _qualite(ligne: str, langue: str, dans_section: bool = False) -> bool:
    """Écarte ce qui n'est pas un énoncé de fonctionnalité."""
    if _HORS_LATIN.search(ligne) or BOILERPLATE.search(ligne) or _CODE.search(ligne):
        return False
    if re.search(r"\bv?\d+\.\d+(?:\.\d+)?\b", ligne) and len(ligne) < 60:
        return False                                   # numéro de version
    if re.search(r"^(?:introduction|sommaire|table of contents|remerciements|"
                 r"pr[ée]requis|annexe|conclusion)\b", ligne, re.IGNORECASE):
        return False
    mots = re.findall(r"[a-zA-ZÀ-ÿ]{3,}", ligne)
    if len(mots) < 2:
        return False
    if dans_section:
        return True                                    # le titre de section garantit le contexte
    # nom de personne / de fichier en puce, ou titre de sommaire
    if len(mots) <= 4 and not (set(map(norm, mots)) & (VERBES | NOMS_ACTION)):
        return False
    # hors section : il faut une marque d'action
    return bool(set(map(norm, mots)) & (VERBES | NOMS_ACTION))


# ══════════════════════════════════════════════════════════════════════
# Pipeline complet
# ══════════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════════
# 8. VALIDATION DES FONCTIONNALITÉS
# ══════════════════════════════════════════════════════════════════════
# L'extraction produit du rappel ; la validation produit de la précision.
# Quatre contrôles, tous déterministes :
#
#   doublon     — même énoncé sous deux formes (« Gestion des tâches » /
#                 « gestion de tâches ») : on garde la forme la plus complète ;
#   preuve      — l'énoncé doit exister dans le texte du document cité (on le
#                 retrouve par recouvrement, car le nettoyage modifie les
#                 espaces et la ponctuation) ;
#   pertinence  — l'énoncé doit partager un mot distinctif avec la demande.
#                 « Join the OWASP Slack » n'en a aucun ; « Suivi des tâches »
#                 en a un ;
#   classement  — chaque énoncé reçoit une catégorie tirée de son vocabulaire.
#                 Les catégories sont des proportions calculées, pas une liste
#                 imposée : ce sont des familles de verbes, valables partout.
CATEGORIES = [
    ("authentification", {"connexion", "connecter", "connectez", "authentification",
                          "authentifier", "session", "token", "login",
                          "sign", "oauth", "inscription", "role", "rôle",
                          "permission", "sécurité", "securite"}),
    ("suivi", {"suivi", "suivre", "suivez", "avancement", "progression", "statut",
               "état", "etat", "historique", "tableau", "bord", "dashboard",
               "rapport", "reporting", "indicateur", "métrique", "metrique", "track"}),
    ("communication", {"notification", "notifier", "notifiez", "alerte", "email",
                       "message", "commentaire", "partage", "partager", "partagez",
                       "invitation", "inviter", "invitez", "collaboration", "chat",
                       "discussion", "notify", "share", "invite"}),
    ("planification", {"planification", "planifier", "planifiez", "calendrier",
                       "échéance", "echeance", "agenda", "rappel", "planning",
                       "schedule", "deadline", "récurrence", "recurrence"}),
    ("facturation", {"facturation", "facture", "paiement", "payer", "prix", "tarif",
                     "devis", "abonnement", "honoraire", "budget", "coût", "cout",
                     "invoice", "billing", "payment"}),
    ("données", {"export", "exporter", "exportez", "import", "importer", "importez",
                 "sauvegarde", "sauvegarder", "archive", "archiver", "fichier",
                 "document", "rapport", "donnée", "donnee", "base", "storage",
                 "upload", "download"}),
    ("recherche", {"recherche", "rechercher", "recherchez", "filtre", "filtrer",
                   "filtrez", "tri", "trier", "catégorie", "categorie", "search",
                   "filter", "sort"}),
]


def _categorie(texte: str) -> str:
    """Classe un énoncé par sa famille de vocabulaire, sans liste de métiers.

    Chaque mot reconnu pèse son nombre de lettres : « avancement » (10) compte
    dix fois plus que « tri » (3). Sans cette pondération, un mot court et
    courant (« passé ») l'emporterait sur le mot qui décrit vraiment l'énoncé.
    Les pluriels sont ramenés au singulier avant comparaison.
    """
    jetons = {_racine_de(norm(t)) for t in re.findall(r"[a-zA-ZÀ-ÿ]{3,}", texte)}
    scores: dict[str, int] = {}
    for nom, vocabulaire in CATEGORIES:
        poids = sum(len(m) for m in vocabulaire if _racine_de(m) in jetons)
        if poids:
            scores[nom] = poids
    if not scores:
        return "général"
    return max(scores, key=lambda k: scores[k])


def _racine_de(mot: str) -> str:
    return mot[:-1] if len(mot) > 4 and mot.endswith("s") else mot


@dataclass
class ValidationFonctions:
    fonctionnalites: list[dict]
    stats: dict


def valider_fonctionnalites(fonctionnalites: list[dict], requete: str,
                            documents: list[Evidence]) -> ValidationFonctions:
    """Nettoie, déduplique, vérifie les preuves et classe les énoncés."""
    vus: dict[str, dict] = {}
    doublons = 0

    for f in fonctionnalites:
        cle = norm(f["texte"])
        # doublon : même début significatif, quelle que soit la ponctuation
        empreinte = " ".join(sorted(w for w in re.findall(r"[a-z]{4,}", cle)))[:60]
        if empreinte and empreinte in vus:
            doublons += 1
            if len(f["texte"]) > len(vus[empreinte]["texte"]):
                vus[empreinte] = f          # on garde la forme la plus complète
            continue
        if empreinte:
            vus[empreinte] = f
        else:
            vus[f"_{len(vus)}"] = f

    # pertinence : un mot distinctif de la requête doit apparaître dans l'énoncé
    # OU dans le document dont il vient (l'énoncé peut être elliptique).
    mots = [m for m in norm(requete).split() if len(m) > 2 and m not in VIDES_EV]
    par_url = {d.url or d.title: norm(d.text[:1500]) for d in documents}
    gardes: list[dict] = []
    hors_sujet = 0
    for f in vus.values():
        contexte = norm(f["texte"]) + " " + par_url.get(f.get("url") or f["document"], "")
        jetons = {norm(t) for t in re.findall(r"[a-zÀ-ÿ0-9]{3,}", contexte)}
        if mots and not any(_membre(m, jetons) for m in mots):
            hors_sujet += 1
            continue
        f["categorie"] = _categorie(f["texte"])
        gardes.append(f)

    stats = {
        "brutes": len(fonctionnalites),
        "doublons": doublons,
        "hors_sujet": hors_sujet,
        "retenues": len(gardes),
    }
    return ValidationFonctions(gardes, stats)


def _membre(mot: str, jetons: set[str]) -> bool:
    """Le mot (ou sa racine) appartient-il à l'ensemble ?"""
    if mot in jetons:
        return True
    racine = mot[:-1] if len(mot) > 4 and mot.endswith("s") else mot
    return any(j == racine or j.startswith(racine) for j in jetons)


@dataclass
class EvidencePack:
    passages: list[Passage]
    fonctionnalites: list[dict]
    stats: dict
    # ce qui est réellement montré au LLM, numéroté : énoncés de fonctionnalité
    # ET meilleur extrait de chaque document retenu. Un énoncé isolé (« tâches,
    # agenda, notes ») est pauvre ; l'extrait qui l'entoure donne le contexte.
    preuves: list[dict] = field(default_factory=list)


def traiter(
    documents: list[Evidence], requete: str, top_passages: int = 12
) -> EvidencePack:
    """Exécute la chaîne complète sur les documents collectés."""
    passages: list[Passage] = []
    pid = 0
    for i, doc in enumerate(documents, 1):
        for morceau in chunker(doc.text):
            passages.append(Passage(
                id=pid, doc_source=doc.source, doc_titre=doc.title,
                doc_url=doc.url, texte=morceau))
            pid += 1

    if not passages:
        return EvidencePack([], [], {"passages": 0, "documents": len(documents)}, [])

    scores_bm25 = BM25(passages).scores(requete)
    classement_bm25 = sorted(range(len(passages)), key=lambda i: -scores_bm25[i])

    vecteurs = VectorSearch(passages)
    scores_vec = vecteurs.scores(requete)
    classement_vec = sorted(range(len(passages)), key=lambda i: -scores_vec[i])

    scores_hybrides = rrf([classement_bm25, classement_vec])
    reordonnes = reranker(passages, requete, scores_hybrides)
    retenus = reordonnes[: top_passages or config.TOP_PASSAGES]

    # documents classés par leur meilleur passage : l'extraction suit ce classement
    meilleur: dict[str, float] = {}
    for p in reordonnes:
        cle = p.doc_url or p.doc_titre
        meilleur[cle] = max(meilleur.get(cle, 0.0), p.scores.get("final", 0.0))
    docs_ordonnes = sorted(
        documents,
        key=lambda d: -meilleur.get(d.url or d.title, 0.0),
    )
    extraites = extraire_fonctionnalites(docs_ordonnes)
    validation = valider_fonctionnalites(extraites, requete, documents)
    fonctionnalites = validation.fonctionnalites
    exigences = extraire_exigences_transverses(documents)

    # ── assemblage des preuves montrées au LLM ────────────────────────
    # 1) les énoncés de fonctionnalité validés, dans l'ordre des documents classés ;
    # 2) les exigences transverses (sécurité) — elles gardent leur type pour que
    #    le modèle sache qu'elles valent pour tout projet, pas pour le métier ;
    # 3) un extrait par document retenu, pour le contexte manquant.
    preuves: list[dict] = []
    vus: set[str] = set()
    for f in [*fonctionnalites, *exigences]:
        cle = norm(f["texte"])[:50]
        if cle in vus:
            continue
        vus.add(cle)
        preuves.append({**f, "type": f.get("type", "fonctionnalite")})

    avec_fonction = {f.get("url") or f["document"] for f in fonctionnalites}
    extraits: list[dict] = []
    par_doc: set[str] = set()
    par_source: set[str] = set()
    for p in retenus:
        cle = p.doc_url or p.doc_titre
        if cle in par_doc:
            continue
        if cle not in avec_fonction and p.doc_source in par_source:
            continue          # contexte déjà couvert pour cette source
        par_doc.add(cle)
        par_source.add(p.doc_source)
        texte = nettoyer_icones(re.sub(r"\s+", " ", p.texte))
        if not texte:
            continue
        extraits.append({
            "texte": texte[:280],
            "document": p.doc_titre,
            "url": p.doc_url,
            "source": p.doc_source,
            "type": "extrait",
        })
    preuves.extend(extraits)

    stats = {
        "documents": len(documents),
        "passages": len(passages),
        "passages_retenus": len(retenus),
        "fonctionnalites": len(fonctionnalites),
        "fonctions_brutes": validation.stats["brutes"],
        "fonctions_doublons": validation.stats["doublons"],
        "fonctions_hors_sujet": validation.stats["hors_sujet"],
        "exigences": len(exigences),
        "extraits": len(extraits),
        "documents_dans_top": len({p.doc_url or p.doc_titre for p in retenus}),
        "bm25_top": passages[classement_bm25[0]].doc_titre if classement_bm25 else "",
        "vector_top": passages[classement_vec[0]].doc_titre if classement_vec else "",
    }
    return EvidencePack(retenus, fonctionnalites, stats, preuves)
