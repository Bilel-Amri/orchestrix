"""Orchestrix — architecture en 7 étapes, 2 appels LLM.

  1. INPUT            brief en langage naturel
  2. ANALYSE          LLM : besoin, domaine, contraintes, fonctionnalités
  3. QUERY ENG.       code : requêtes FR/EN + description sémantique
  4. COLLECTE         code : 9 sources en parallèle
  5. EVIDENCE PROC.   code : chunking → BM25 → vector → RRF → rerank → extraction
  6. GÉNÉRATION       LLM : épics → user stories → tâches, ancrées sur preuves
  7. VALIDATION       code : citations, doublons, couverture, export
"""

from __future__ import annotations

import json
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import complexite
from .evidence import EvidencePack, traiter
from .llm import GroqClient, GroqError
from . import config
from .sources import Evidence, collect_all, norm, verifier_projets

# ──────────────────────────────────────────────────────────────────────
# ÉTAPE 2 — ANALYSE
# ──────────────────────────────────────────────────────────────────────
def retirer_noms_propres(brief: str, analyse: dict) -> dict:
    """Écarte les noms de produit de la requête de recherche.

    Un nom propre inventé (« TaskFlow », « GestiPro ») ne désignera aucun
    document sur le web : le chercher vide la collecte. On le repère
    mécaniquement — mot capitalisé ailleurs qu'en début de phrase — plutôt que
    de faire confiance au modèle pour respecter la consigne.
    """
    propres: set[str] = set()
    for phrase in re.split(r"(?<=[.!?])\s+|\n", brief):
        mots = phrase.split()
        for i, mot in enumerate(mots):
            noyau = re.sub(r"[^\wÀ-ÿ]", "", mot)
            if not noyau or not noyau[0].isupper():
                continue
            if i == 0 and len(mots) > 1:
                continue          # majuscule de début de phrase : pas un signal
            propres.add(norm(noyau))
    if not propres:
        return analyse

    def nettoyer(texte: str) -> str:
        gardes = [m for m in texte.split() if norm(re.sub(r"[^\wÀ-ÿ]", "", m)) not in propres]
        return " ".join(gardes) if gardes else texte

    for cle in ("requete_fr", "requete_en", "intention"):
        if analyse.get(cle):
            analyse[cle] = nettoyer(str(analyse[cle]))
    if analyse.get("mots_cles"):
        analyse["mots_cles"] = [
            m for m in analyse["mots_cles"] if norm(str(m)) not in propres
        ] or analyse["mots_cles"]
    if analyse.get("concepts"):
        gardes = [c for c in analyse["concepts"] if norm(str(c)) not in propres]
        analyse["concepts"] = gardes or analyse["concepts"]
    if analyse.get("sujet"):
        sujet_nettoye = nettoyer(str(analyse["sujet"]))
        analyse["sujet"] = sujet_nettoye if sujet_nettoye.strip() else str(analyse.get("domaine") or "")
    return analyse


ANALYSE_SYSTEM = """Tu analyses une demande de projet pour préparer une recherche documentaire.

Réponds en JSON :
{"objectif": "ce que le projet doit faire, 20 mots max, EN FRANÇAIS",
 "intention": "ce que le logiciel gère, en termes GÉNÉRIQUES, 4 à 8 mots, EN FRANÇAIS",
 "concepts": ["4 à 8 capacités génériques que possède ce type de logiciel, EN FRANÇAIS"],
 "domaine": "secteur d'activité, 3 mots max, EN FRANÇAIS",
 "sujet": "le domaine en 2 à 4 mots, comme dans une encyclopédie, EN FRANÇAIS",
 "utilisateurs": "à qui le projet sert, 12 mots max, EN FRANÇAIS",
 "contraintes": ["contraintes explicites du brief, EN FRANÇAIS"],
 "fonctionnalites": ["fonctions EXPLICITEMENT demandées, EN FRANÇAIS"],
 "requete_fr": "3 à 6 mots en FRANÇAIS décrivant ce que le système gère",
 "requete_en": "traduction ANGLAISE de requete_fr",
 "mots_cles": ["4 à 8 mots du vocabulaire du métier (peut rester en anglais)"]}

TU DOIS COMPRENDRE LE SENS, PAS RECOPIER LES MOTS DU CLIENT.
Le client écrit une phrase commerciale ; toi tu en tires ce que le logiciel
EST. Exemple de raisonnement : un client décrit « une plateforme pour que mes
équipes sachent qui fait quoi et quand » → l'intention est « suivi de tâches et
de planning d'équipe », les concepts sont « gestion de tâches, assignation,
échéances, tableau de bord ». Les mots du client ne sont pas les mots à chercher.

RÈGLE SECONDE — LES NOMS PROPRES NE SE CHERCHENT PAS.
Un nom de produit, de marque ou de projet (« TaskFlow », « MonAppli »,
« GestiPro ») est inventé : il ne désignera aucun document sur le web. Ces mots
ne doivent JAMAIS apparaître dans intention, concepts, requete_fr, requete_en
ni mots_cles. Tu cherches le MÉTIER, pas la marque.

AUTRES RÈGLES
- Le domaine est libre : ne présuppose aucun secteur, aucun métier.
- requete_fr / requete_en : pas de « application », « logiciel », « plateforme »,
  « souhaitons », « développer », pas de virgules. Décris ce qui est géré.
- requete_en doit être un vrai anglais, jamais la requête française recopiée.
- intention et concepts servent à trouver des logiciels COMPARABLES : ils doivent
  être cherchables dans une encyclopédie ou un dépôt de code.
- fonctionnalites et contraintes : uniquement ce qui est écrit dans la demande.

LANGUE
La demande peut être écrite en anglais : tous les champs de ta réponse sont en
FRANÇAIS, sans exception. Les deux seuls champs qui restent en anglais sont
requete_en (un vrai anglais, pour interroger les sources) et mots_cles (le
vocabulaire du métier, qui sert aussi à interroger des dépôts anglophones).
Traduis les termes de métier dans objectif, intention, concepts, domaine, sujet,
utilisateurs, contraintes et fonctionnalites : « library management » devient
« gestion de bibliothèque ».
"""

ANALYSE_USER = """DEMANDE DU CHEF DE PROJET :
{brief}

JSON uniquement."""

# ──────────────────────────────────────────────────────────────────────
# ÉTAPE 6 — GÉNÉRATION AGILE
# ──────────────────────────────────────────────────────────────────────
PLAN_SYSTEM = """Tu es chef de projet agile. Tu écris un backlog complet, au format
Jira, à partir d'une demande et de PREUVES extraites de documents réels.

Réponds UNIQUEMENT en JSON :
{"epics": [{
  "title": "...",
  "description": "...",
  "stories": [{
    "title": "...",
    "as_a": "rôle de l'utilisateur",
    "i_want": "ce qu'il veut faire",
    "so_that": "le bénéfice attendu",
    "acceptance": ["critère d'acceptation vérifiable"],
    "tasks": [{
      "title": "...",
      "description": "ce qu'il faut faire, concrètement",
      "type": "dev | test | config | doc | design | securite",
      "sources": [1]
    }]
  }]
}]}

EXIGENCES DE DÉCOUPAGE — c'est ici que se joue la qualité du backlog.
1. Un épic = un domaine fonctionnel large, pas une tâche déguisée. Vise 4 à 8
   épics pour couvrir le projet : socle technique, gestion des utilisateurs et
   des accès, puis les grands domaines métier, puis le reporting, puis la
   qualité et la mise en production.
2. Chaque épic contient PLUSIEURS stories (3 à 6). Une story sans au moins
   trois stories sœurs est le signe d'un découpage trop grossier.
3. Chaque story contient PLUSIEURS tâches (3 à 6). Une story à une seule tâche
   n'est pas décomposée : redécoupe-la.
4. Une story raconte un besoin utilisateur ; une tâche raconte un travail
   d'équipe. Ne mets pas de « tâche » qui soit en réalité une story.
5. Couvre les quatre natures de travail, avec le champ "type" :
   - "dev"      : construire la fonctionnalité ;
   - "test"     : vérifier qu'elle marche, y compris les cas d'erreur ;
   - "config"   : environnement, base de données, déploiement, CI/CD ;
   - "doc"      : ce qui doit être écrit pour que le projet vive sans toi.
   Ajoute "design" pour les maquettes et "securite" pour les obligations OWASP.
6. Chaque story porte 2 à 4 critères d'acceptation VÉRIFIABLES (observables,
   pas « ça marche bien »).

LANGUE — RÈGLE ABSOLUE
Tout le plan est rédigé EN FRANÇAIS, même quand la demande est écrite en
anglais. Cela vaut pour les titres d'épics, les titres de stories, les
descriptions, as_a, i_want, so_that et les critères d'acceptation. Un terme
technique sans traduction courante peut rester en anglais, mais la phrase qui
l'entoure est française : aucune phrase anglaise ne doit subsister.
Un brief en anglais donne donc un plan en français : « As a librarian, I want
to search books » devient « En tant que bibliothécaire, je veux rechercher des
ouvrages ». Les titres des preuves citées, eux, ne se traduisent pas : tu les
cites tels quels.

SOURÇAGE
7. Toutes les fonctionnalités demandées doivent apparaître dans le plan.
8. Les preuves [FONCTION] sont des fonctionnalités observées dans des projets
   comparables : sers-t'en pour nommer et compléter les tâches.
9. Les preuves [EXIGENCE] sont des risques de sécurité (OWASP Top 10). Ce sont
   des obligations, pas des fonctions : chacune doit produire une tâche de type
   "securite". Un plan d'application web sans tâche de sécurité est incomplet.
10. Les preuves [EXTRAIT] donnent le contexte ; elles ne justifient pas seules.
11. "sources" contient UNIQUEMENT des numéros de preuves fournies. Si aucune
    preuve ne justifie la tâche, mets []. Une tâche non sourcée n'est pas un
    défaut : une tâche inventée pour se donner bonne conscience en est un.
12. Les contraintes du brief doivent être traitées en tâches.
13. Titres courts et uniques. Aucun nombre d'épics, de stories ou de tâches
    n'est imposé : la seule règle est que chaque niveau soit réellement
    décomposé.
"""

PLAN_USER = """DEMANDE :
{brief}

OBJECTIF : {objectif}
UTILISATEURS : {utilisateurs}
FONCTIONNALITÉS DEMANDÉES (obligatoires) : {fonctionnalites}
CONTRAINTES (obligatoires) : {contraintes}

PREUVES — fonctionnalités observées dans des projets comparables :
{preuves}

Écris le backlog complet (épics → user stories → tâches) en JSON, EN FRANÇAIS,
même si la demande ci-dessus est en anglais.
Chaque story doit avoir plusieurs tâches, et chaque épic plusieurs stories.{retour}"""

RETOUR_SYSTEM = """Un chef de projet a REFUSÉ un plan précédent et explique pourquoi.
Tu produis un nouveau plan, pas une correction cosmétique : tiens compte de sa
remarque comme d'une exigence, tout en gardant les règles habituelles (français,
épics → stories → tâches, sources uniquement prises dans la liste fournie)."""


def bloc_retour(motif: str) -> str:
    """Fragment ajouté au prompt quand un plan a été refusé par un humain.

    Le motif est repris tel quel entre guillemets : c'est la parole du chef de
    projet, pas une consigne qu'on réécrit. Sans cette reprise, la régénération
    produirait un plan quasi identique — le modèle ne saurait pas quoi changer.
    """
    motif = " ".join((motif or "").split())
    if not motif:
        return ""
    return ("RETOUR DU CHEF DE PROJET SUR LE PLAN PRÉCÉDENT (plan REFUSÉ) :\n"
            f"« {motif[:1500]} »\n"
            "Écris un nouveau plan qui répond à cette remarque.")


CORRIGER_SYSTEM = """On te signale des défauts dans un plan de projet.
Corrige-les et renvoie le plan COMPLET au même format JSON.

RÈGLES DE CORRECTION
- Corrige UNIQUEMENT les défauts signalés. Ne supprime ni épic, ni story, ni
  tâche pour « simplifier » : le plan corrigé doit contenir au moins autant de
  tâches que le plan d'origine.
- Si un défaut porte sur la LANGUE, réécris tout le texte du plan EN FRANÇAIS,
  y compris les titres, les critères d'acceptation et les descriptions. Le plan
  est toujours en français, même si la demande est en anglais.
  Ne traduis pas les titres des preuves citées : tu les cites tels quels.
- Si un défaut porte sur une FONCTIONNALITÉ ABSENTE, ajoute une story qui la
  couvre, avec ses tâches.
- Titres uniques. Sources prises uniquement dans la liste fournie.
"""

CORRIGER_USER = """DEMANDE :
{brief}

DÉFAUTS À CORRIGER :
{defauts}

PREUVES (numéros autorisés) :
{preuves}

Renvoie le plan corrigé en JSON."""


@dataclass
class Resultat:
    plan: dict
    pack: EvidencePack
    metadonnees: dict = field(default_factory=dict)

    # ── export markdown ─────────────────────────────────────────────
    def to_markdown(self) -> str:
        m = self.metadonnees
        # Gabarit bilingue conservé, mais la sortie est française par défaut :
        # `PLANAGENT_FRANCAIS=0` rétablit les libellés dans la langue du brief.
        # On ne redétecte pas la langue à partir de "en", ce mot ne contenant
        # aucun marqueur et retombant sur "fr".
        en = m.get("langue") == "en" or (
            not m.get("langue") and _langue(str(m.get("brief", ""))) == "en")
        T = {
            "titre": "Project plan" if en else "Plan de projet",
            "epic": "Epic" if en else "Épic",
            "stories": "stories" if en else "stories",
            "complexite": "Complexity" if en else "Complexité",
            "as_a": "As a" if en else "En tant que",
            "i_want": "I want" if en else "je veux",
            "so_that": {"en": "so that ", "fr": "afin de "},
            "acceptance": "Acceptance criteria" if en else "Critères d'acceptation",
            "key": "Key" if en else "Clé",
            "task": "Task" if en else "Tâche",
            "type": "Type" if en else "Type",
            "prio": "Priority" if en else "Priorité",
            "proof": "Evidence" if en else "Preuve",
            "metrics": "Metrics" if en else "Métriques",
            "sources": "Sources" if en else "Sources",
            "rejected": "Rejected documents (step 4)" if en else "Projets écartés (étape 4)",
            "cats": "Validated features by category (step 7)" if en else "Fonctionnalités validées par catégorie (étape 7)",
            "chain": "Processing chain" if en else "Chaîne de traitement",
            "cited": "Cited evidence" if en else "Preuves citées",
            "warn": "Warnings" if en else "Avertissements",
            "cat": "Category" if en else "Catégorie",
            "utter": "Statements" if en else "Énoncés",
            "doc": "Document" if en else "Document",
            "src": "Source" if en else "Source",
            "score": "Score",
            "reason": "Reason" if en else "Motif",
        }
        q = m.get("qualite", {})
        l = [
            "# Project plan" if en else "# Plan de projet",
            "",
            f"> {m.get('brief', '')}",
            "",
            f"*{m.get('date', '')} · {q.get('epics')} épics · {q.get('stories')} user "
            f"stories · {q.get('taches')} tâches · {m.get('duree_s')}s · {m.get('modele')}*",
            "",
        ]
        if m.get("non_ancre"):
            l += [
                "> ⚠️ **Plan non ancré.** Aucune preuve exploitable n'a été trouvée",
                "> pour ce brief : ni les sources GitHub/GitLab (quota d'API ?), ni",
                "> les applications comparables, ni les références de sécurité.",
                "> Les tâches ci-dessous viennent du brief seul, pas de documents",
                "> collectés. Relancez avec `GITHUB_TOKEN` ou un brief plus",
                "> explicite avant de vous appuyer sur ce plan.",
                "",
            ]

        for i, epic in enumerate(self.plan.get("epics", []), 1):
            l += [f"## {T['epic']} {i} · {epic.get('title', '')}", ""]
            if epic.get("description"):
                l += [f"*{epic['description']}*", ""]
            l += [f"**{len(epic.get('stories', []))} {T['stories']}**", ""]

            for j, st in enumerate(epic.get("stories", []), 1):
                l.append(f"### TF-{i}.{j} · {st.get('title', '')}")
                l.append("")
                but = str(st.get("so_that", "")).strip()
                if en:
                    lien = "so that "
                else:
                    lien = "afin d'" if but[:1].lower() in "aeiouéèêh" else "afin de "
                l.append(f"> **{T['as_a']}** {st.get('as_a','')}, "
                         f"**{T['i_want']}** {st.get('i_want','')} {lien}{but}." if en else
                         f"> **{T['as_a']}** {st.get('as_a','')}, "
                         f"**{T['i_want']}** {st.get('i_want','')} {lien}{but}.")
                l.append("")
                if st.get("acceptance"):
                    l.append(f"**{T['acceptance']}**")
                    l += [f"- [ ] {c}" for c in st["acceptance"]]
                    l.append("")
                l.append(f"| {T['key']} | {T['task']} | {T['type']} | "
                         f"{T['prio']} | {T['complexite']} | {T['proof']} |")
                l.append("|---|---|---|---|---|---|")
                for t in st.get("tasks", []):
                    refs = ", ".join(f"[{x}]" for x in t.get("sources", [])) or "—"
                    t_type = TYPES_TACHE.get(t.get("type", ""), t.get("type", ""))
                    l.append(f"| `{t.get('cle','')}` | **{t.get('title','')}** — "
                             f"{t.get('description','')} | {t_type} | "
                             f"{t.get('priorite','')} | "
                             f"{t.get('complexite_classe') or '—'} | {refs} |")
                l.append("")

        if q:
            l += ["---", "", f"## {T['metrics']}", "",
                  ("| Metric | Value |" if en else "| Métrique | Valeur |"), "|---|---|"]
            l += [
                f"| {'Epics' if en else 'Épics'} | {q.get('epics')} |",
                f"| {'User stories' if en else 'User stories'} | {q.get('stories')} |",
                f"| {'Tasks' if en else 'Tâches'} | {q.get('taches')} |",
                f"| {'Sourced tasks' if en else 'Tâches sourcées'} | "
                f"{q.get('sourcees')} ({q.get('taux_ancrage',0):.0%}) |",
                f"| {'Duplicate titles' if en else 'Titres en double'} | {q.get('doublons')} |",
                f"| {'Feature coverage' if en else 'Couverture des fonctionnalités'} | "
                f"{q.get('couverture',0):.0%} |",
                f"| {'Distinct evidence cited' if en else 'Preuves citées distinctes'} | {q.get('diversite')} |",
                f"| {'Tasks per story' if en else 'Tâches par story'} | {q.get('taches_par_story')} |",
                f"| {'Breakdown' if en else 'Répartition'} | "
                f"{', '.join(f'{k} {v}' for k, v in (q.get('types') or {}).items())} |",
                "",
            ]

        if m.get("avertissements"):
            l += [f"## {T['warn']}", ""] + [f"- {a}" for a in m["avertissements"]] + [""]
        if m.get("non_ancre"):
            l += ["## Remède", "",
                  "1. `export GITHUB_TOKEN=ghp_...` (quota GitHub : 10 recherches/minute sans jeton)",
                  "2. rendre le brief explicite : le métier, pas seulement le nom du produit",
                  "3. vérifier la collecte dans l'onglet Sources & preuves de l'interface",
                  ""]

        src = m.get("sources_collectees") or {}
        if src:
            l += ["---", "", f"## {T['sources']}", ""]
            for nom, info in sorted(src.items()):
                if nom.startswith("_"):
                    continue          # compteurs techniques, pas des sources
                err = f" — {info['erreur']}" if info.get("erreur") else ""
                l.append(f"- {nom} : {info.get('n', 0)} document(s){err}")
            l.append("")

        verdicts = m.get("verdicts_projets") or []
        ecartes = [v for v in verdicts if not v.get("retenu")]
        if ecartes:
            l += ["---", "", f"## {T['rejected']}", "",
                  f"| {T['doc']} | {T['src']} | {T['score']} | {T['reason']} |",
                  "|---|---|---|---|"]
            for v in ecartes[:12]:
                l.append(f"| {v['titre'][:44]} | {v['source']} | {v['score']:.2f} | {v['motif']} |")
            l.append("")

        cats = m.get("categories_fonctionnalites") or {}
        if cats:
            l += [f"## {T['cats']}", "",
                  f"| {T['cat']} | {T['utter']} |", "|---|---|"]
            for nom, n in sorted(cats.items(), key=lambda x: -x[1]):
                l.append(f"| {nom} | {n} |")
            l.append("")

        s = m.get("pipeline", {})
        if s:
            l += [
                "---", "", f"## {T['chain']}", "",
                f"- Documents collectés : {s.get('documents')}",
                f"- Passages après chunking : {s.get('passages')}",
                f"- Passages retenus (hybride + rerank) : {s.get('passages_retenus')}",
                f"- Énoncés bruts : {s.get('fonctions_brutes')}",
                f"- Énoncés validés : {s.get('fonctionnalites')} "
                f"({s.get('fonctions_doublons',0)} doublons, {s.get('fonctions_hors_sujet',0)} hors sujet écartés)",
                f"- Extraits de documents : {s.get('extraits')}",
                f"- Documents distincts dans le top : {s.get('documents_dans_top')}",
                "",
            ]

        if self.pack.preuves:
            # seules les preuves réellement citées par une tâche sont publiées
            citees = sorted({s for e in self.plan.get("epics", [])
                             for st in e.get("stories", [])
                             for t in st.get("tasks", []) for s in t.get("sources", [])})
            if citees:
                l += ["---", "", f"## {T['cited']}", ""]
                for i in citees:
                    if 1 <= i <= len(self.pack.preuves):
                        f = self.pack.preuves[i - 1]
                        l.append(f"[{i}] {f['texte']} — *{f['document']}* "
                                 f"({f['source']}) {f['url']}")
        return "\n".join(l)


class Orchestrix:
    def __init__(self, llm: GroqClient, verbose: bool = True) -> None:
        self.llm = llm
        self.verbose = verbose
        # Appelé à chaque jalon, et pendant la rédaction du plan à chaque
        # paquet de jetons reçus : ({"etape": str, "jetons": int}) -> None
        self.sur_progression = None
        self._dernier_jeton = 0.0

    def _say(self, msg: str) -> None:
        if self.verbose:
            print(msg, flush=True)

    # ==================================================================
    def _progres(self, **infos) -> None:
        """Prévient l'appelant de l'avancement (étape, jetons reçus)."""
        if infos.get("jetons"):
            self._dernier_jeton = time.perf_counter()
        if self.sur_progression:
            try:
                self.sur_progression(infos)
            except Exception:                     # noqa: BLE001
                pass

    def run(self, brief: str, motif_rejet: str = "") -> Resultat:
        """Les neuf étapes, dans l'ordre.

        ① analyse · ② requêtes · ③ collecte · ④ pertinence des projets ·
        ⑤ chunking/BM25/vectoriel/RRF/rerank · ⑥ extraction ·
        ⑦ validation des fonctionnalités · ⑧ plan agile · ⑨ validation finale
        """
        t0 = time.perf_counter()

        # ── ① ANALYSE DU BESOIN ─────────────────────────────────────
        self._say("① analyse du besoin")
        self._progres(etape="analyse du besoin", jetons=0)
        try:
            analyse = self.llm.chat_json(
                ANALYSE_SYSTEM, ANALYSE_USER.format(brief=brief),
                max_tokens=config.MAX_TOKENS_ANALYSE, model=self.llm.modele_rapide(),
                temperature=config.TEMPERATURE_ANALYSE)
        except GroqError as exc:
            # Sans analyse, on peut encore travailler : la requête de recherche
            # se rabat sur le brief nettoyé de son vocabulaire commercial.
            self._say(f"    ⚠️  analyse illisible ({str(exc)[:70]})")
            self._say("    ↻ repli sur une analyse minimale")
            analyse = _analyse_de_secours(brief)
        analyse = normaliser_analyse(retirer_noms_propres(brief, analyse))
        sujet = str(analyse.get("sujet") or analyse.get("domaine") or "")
        req_fr = str(analyse.get("requete_fr") or brief[:60])
        req_en = str(analyse.get("requete_en") or req_fr)
        fonctionnalites = _filtrer_fonctionnalites(analyse.get("fonctionnalites") or [])
        contraintes = [str(c) for c in (analyse.get("contraintes") or [])]
        self._say(f"    🎯 {analyse.get('objectif','')}")
        if analyse.get("intention"):
            self._say(f"    🧠 intention : {analyse['intention']}")
        if analyse.get("concepts"):
            self._say(f"    🔗 concepts : {', '.join(str(c) for c in analyse['concepts'][:6])}")
        self._say(f"    👥 {analyse.get('utilisateurs','')}")
        self._say(f"    🔎 FR «{req_fr}» · EN «{req_en}»")

        # ── ② CONSTRUCTION DES REQUÊTES ─────────────────────────────
        # Objectif + requête FR + requête EN + fonctionnalités + mots-clés +
        # contraintes : plus la requête porte de vocabulaire du métier, mieux
        # BM25 et le vectoriel classent les passages.
        # La recherche est pilotée par la COMPRÉHENSION du besoin, pas par les
        # mots du brief : l'intention, les concepts génériques et les
        # fonctionnalités déduites par le modèle pèsent plus que les mots-clés.
        # C'est ce qui fait qu'un brief commercial (« que mes équipes sachent
        # qui fait quoi ») cherche « gestion de tâches, assignation, échéances ».
        briques = [
            str(analyse.get("intention") or ""),          # priorité 1 : le sens
            " ".join(str(c) for c in (analyse.get("concepts") or [])),   # priorité 2
            " ".join(fonctionnalites),                    # priorité 3
            req_fr, req_en,
            str(analyse.get("sujet") or ""),
            " ".join(str(m) for m in (analyse.get("mots_cles") or [])),
            str(analyse.get("objectif") or ""),
            " ".join(contraintes),
        ]
        description = " ".join(b for b in briques if b.strip()).strip()
        self._say(f"② requête de recherche construite ({len(description.split())} mots)")

        # ── ③ COLLECTE DES SOURCES ──────────────────────────────────
        self._say("③ collecte des 9 sources (parallèle)")
        self._progres(etape="collecte des sources", jetons=0)
        documents, traces = collect_all(
            req_fr, req_en, sujet,
            concepts=[str(c) for c in (analyse.get("concepts") or [])],
            intention=str(analyse.get("intention") or ""))
        for nom, tr in traces.items():
            self._say(f"    {nom:16} → {tr['n']}")
        self._say(f"    ✅ {len(documents)} documents")

        # ── ④ PERTINENCE DES PROJETS ────────────────────────────────
        # On élimine les projets non similaires AVANT de découper leurs
        # documents : traiter puis filtrer coûterait du calcul et, surtout,
        # laisserait des passages hors sujet concourir pour les 12 places.
        self._say("④ vérification de la pertinence des projets")
        documents, verdicts = verifier_projets(
            documents, f"{description} {req_en}",
            plancher=config.SEUIL_PERTINENCE)
        ecartes = [v for v in verdicts if not v.retenu]
        self._say(f"    {len(documents)} retenus · {len(ecartes)} écartés")
        for v in ecartes[:4]:
            self._say(f"    – {v.evidence.title[:38]:40} {v.score:.2f} {v.motif}")

        # ── ⑤ CHUNKING → BM25 → VECTOR → RRF → RERANK ───────────────
        self._say("⑤ chunking → BM25 → vectoriel → RRF → reranking")
        pack = traiter(documents, description)
        self._say(
            f"    {pack.stats.get('passages',0)} passages · "
            f"{len(pack.passages)} retenus · "
            f"{pack.stats.get('documents_dans_top',0)} documents distincts"
        )

        # ── ⑥ EXTRACTION DES FONCTIONNALITÉS ────────────────────────
        self._say("⑥ extraction des fonctionnalités")
        self._say(
            f"    {pack.stats.get('fonctions_brutes',0)} brutes · "
            f"{pack.stats.get('fonctions_doublons',0)} doublons · "
            f"{pack.stats.get('fonctions_hors_sujet',0)} hors sujet"
        )

        # ── ⑦ VALIDATION DES FONCTIONNALITÉS ────────────────────────
        self._say("⑦ validation des fonctionnalités (doublons, preuves, pertinence, classement)")
        categories: dict[str, int] = {}
        for f in pack.fonctionnalites:
            categories[f.get("categorie", "général")] = categories.get(f.get("categorie", "général"), 0) + 1
        if pack.preuves:
            self._say(f"    ✅ {len(pack.fonctionnalites)} validées · "
                      f"{', '.join(f'{k} {v}' for k, v in sorted(categories.items(), key=lambda x: -x[1])[:5])}")
        else:
            self._say("    ⚠️  aucune preuve exploitable")
        # Budget de contexte : on borne le nombre de preuves envoyées. Un prompt
        # trop gros provoque une erreur 413 côté Groq, et la relance de
        # correction échoue alors qu'elle était la plus utile.
        preuves_txt = self._preuves(pack, taille=config.MAX_PREUVES_PROMPT)
        # Les fonctionnalités validées sont la matière première du découpage :
        # on les donne à part, en clair, pour que le modèle n'en oublie aucune.
        fonctions_txt = ""
        if pack.fonctionnalites:
            fonctions_txt = (
                "\n\nCAPACITÉS IDENTIFIÉES DANS LES DOCUMENTS (à couvrir par des stories) :\n"
                + "\n".join(f"- {f['texte'][:110]}" for f in pack.fonctionnalites[:20])
            )

        # ── ⑧ GÉNÉRATION AGILE ──────────────────────────────────────
        self._say("⑧ génération du plan (épics → stories → tâches)")
        self._progres(etape="rédaction du plan", jetons=0)
        self._progres(etape="rédaction du plan", jetons=0)
        plan = self.llm.chat_json(
            PLAN_SYSTEM,
            PLAN_USER.format(
                brief=brief,
                objectif=analyse.get("objectif", ""),
                utilisateurs=analyse.get("utilisateurs", ""),
                fonctionnalites=", ".join(fonctionnalites) or "(voir la demande)",
                contraintes=", ".join(contraintes) or "(aucune)",
                preuves=_tronquer(preuves_txt + fonctions_txt, config.MAX_CARACTERES_PROMPT),
                retour=bloc_retour(motif_rejet)),
            max_tokens=config.MAX_TOKENS_PLAN, temperature=config.TEMPERATURE_PLAN,
            jeton=lambda n: self._progres(etape="rédaction du plan", jetons=n))
        plan = nettoyer(plan, len(pack.preuves))
        # Collecte vide : un plan sans preuve n'est pas faux, il est non ancré.
        # On le dit dans le document au lieu de laisser croire à un sourçage.
        if not pack.preuves and nb_taches(plan):
            plan["_non_ancre"] = True

        # ── ⑨ VALIDATION FINALE ─────────────────────────────────────
        self._say("⑨ validation finale")
        defauts = valider(plan, fonctionnalites, contraintes, len(pack.preuves), brief)
        if defauts:
            for d in defauts:
                self._say(f"    ⚠️  {d}")
            self._say("    ↻ une relance ciblée")
            self._progres(etape="correction du plan", jetons=0)
            try:
                plan2 = self.llm.chat_json(
                    CORRIGER_SYSTEM,
                    CORRIGER_USER.format(
                        brief=brief,
                        defauts="\n".join(f"- {d}" for d in defauts),
                        preuves=_tronquer(preuves_txt + fonctions_txt, config.MAX_CARACTERES_PROMPT)),
                    max_tokens=config.MAX_TOKENS_PLAN,
                    temperature=config.TEMPERATURE_CORRECTION,
                    jeton=lambda n: self._progres(etape="correction du plan", jetons=n))
                plan2 = nettoyer(plan2, len(pack.preuves))
                if nb_taches(plan2) >= nb_taches(plan):
                    plan = plan2
                    self._say("    ✅ plan corrigé retenu")
                else:
                    self._say("    ⚠️  correction moins bonne — plan initial conservé")
            except GroqError as exc:
                self._say(f"    ⚠️  correction impossible : {str(exc)[:60]}")
            defauts = valider(plan, fonctionnalites, contraintes, len(pack.preuves), brief)

        duree = round(time.perf_counter() - t0, 1)
        q = metriques(plan, fonctionnalites, len(pack.preuves))
        avertissements = list(defauts)
        if not documents:
            avertissements.append("aucune source disponible : plan non ancré")

        # ── complexité prédite par le modèle, si un service est configuré ──
        # Un seul appel de lot, avec un délai court : si le service ne répond
        # pas, chaque tâche garde son estimation par règles et la génération
        # n'a pas perdu une seconde de plus.
        modele_complexite = self._appliquer_complexite(plan)

        meta = {
            "brief": brief,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "complexite": modele_complexite,
            "modele": self.llm.model,
            # Langue de SORTIE : français par défaut, quel que soit le brief.
            "langue": "fr" if config.FRANCAIS else _langue(brief),
            "analyse": analyse,
            "requete_fr": req_fr,
            "requete_en": req_en,
            "sources_collectees": traces,
            "verdicts_projets": [
                {"titre": v.evidence.title, "source": v.evidence.source,
                 "score": v.score, "retenu": v.retenu, "motif": v.motif}
                for v in sorted(verdicts, key=lambda v: -v.score)],
            "categories_fonctionnalites": categories,
            "pipeline": pack.stats,
            "qualite": q,
            "duree_s": duree,
            "avertissements": avertissements,
            "motif_rejet": (motif_rejet or "").strip(),
            "non_ancre": not pack.preuves,
        }
        self._say(
            f"\n✅ {q['epics']} épics · {q['stories']} stories · {q['taches']} tâches · "
            f"{q['taux_ancrage']:.0%} sourcées · couverture {q['couverture']:.0%} · {duree}s"
        )
        return Resultat(plan=plan, pack=pack, metadonnees=meta)

    # ==================================================================
    def _appliquer_complexite(self, plan: dict) -> dict:
        """Applique la classe textuelle prédite à chaque tâche.

        Chaque tâche reçoit une seule classe parmi :
        Faible, Moyenne, Elevee, Tres_elevee.

        Aucune estimation numérique ni règle de secours n'est utilisée.
        """

        taches = [
            t
            for e in plan.get("epics", [])
            for s in e.get("stories", [])
            for t in s.get("tasks", [])
        ]

        if not taches:
            return {
                "origine": "aucune",
                "raison": "aucune tâche",
            }

        if not complexite.disponible():
            self._say("    ⚠️ PlanAgent non configuré")
            return {
                "origine": "indisponible",
                "raison": "service non configuré",
            }

        self._say("⑪ classification textuelle des tâches (PlanAgent)")

        predictions = complexite.predire_lot([
            {
                "title": t.get("title", ""),
                "body": t.get("description", ""),
            }
            for t in taches
        ])

        if not predictions or len(predictions) != len(taches):
            self._say("    ⚠️ Classification indisponible")
            return {
                "origine": "indisponible",
                "raison": "service muet ou réponse incomplète",
            }

        classes = {
            "Faible",
            "Moyenne",
            "Elevee",
            "Tres_elevee",
        }

        for t, prediction in zip(taches, predictions):
            classe = prediction.get("complexite_classe")

            if classe not in classes:
                self._say("    ⚠️ Classe invalide reçue de PlanAgent")
                return {
                    "origine": "indisponible",
                    "raison": "classe invalide",
                }

        for t, prediction in zip(taches, predictions):
            t["complexite_classe"] = prediction["complexite_classe"]

        self._say(f"    ✅ {len(taches)} tâches classifiées")

        return {
            "origine": "modele",
            "taches": len(taches),
            "latence_ms": predictions[0].get("latence_ms"),
        }

    # ==================================================================
    @staticmethod
    def _preuves(pack: EvidencePack, taille: int = 0) -> str:
        """Liste numérotée des preuves montrées au LLM — les numéros servent de citations.

        On donne des énoncés de fonctionnalité ET des extraits de documents :
        un énoncé seul est souvent trop pauvre pour en déduire une tâche.
        """
        preuves = pack.preuves or []
        if not preuves:
            return "(aucune preuve extraite)"
        taille = taille or len(preuves)
        etiquettes = {"exigence": "EXIGENCE", "extrait": "EXTRAIT",
                      "fonctionnalite": "FONCTION"}
        return "\n".join(
            f"[{i}] [{etiquettes.get(p.get('type', ''), 'FONCTION')}] {p['texte']}"
            f"  ({p['source']} · {p['document'][:40]})"
            for i, p in enumerate(preuves[:taille], 1)
        )

    def sauver(self, r: Resultat, dossier: str = "out") -> tuple[Path, Path]:
        d = Path(dossier)
        d.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        j, m = d / f"plan-{stamp}.json", d / f"plan-{stamp}.md"
        j.write_text(json.dumps({
            "plan": r.plan,
            "metadonnees": r.metadonnees,
            "preuves": [
                {"id": i, "type": f.get("type", ""), "texte": f["texte"],
                 "document": f["document"], "source": f["source"], "url": f["url"]}
                for i, f in enumerate(r.pack.preuves, 1)
            ],
            "passages": [
                {"document": p.doc_titre, "source": p.doc_source,
                 "scores": p.scores, "texte": p.texte[:400]}
                for p in r.pack.passages
            ],
        }, indent=2, ensure_ascii=False), encoding="utf-8")
        m.write_text(r.to_markdown(), encoding="utf-8")
        return j, m


# ══════════════════════════════════════════════════════════════════════
# ÉTAPE 7 — validation déterministe
# ══════════════════════════════════════════════════════════════════════
# Le modèle d'analyse glisse parfois des fragments du brief dans la liste des
# fonctionnalités (« single online platform »). Les garder fait échouer le
# contrôle de couverture sur une exigence qui n'en est pas une.
FRAGMENTS = {"single", "online", "seul", "seule", "unique", "platform", "plateforme",
             "modern", "moderne", "multiple", "plusieurs", "same", "même", "whole",
             "entire", "global", "global", "simple", "easy", "facile", "nouveau",
             "new", "based", "basé", "web", "mobile", "app", "application"}


def _en_liste(valeur) -> list:
    """Ramène à une liste ce que le modèle a pu rendre en texte ou en objet.

    Un plan valide ne doit pas être rejeté parce que « utilisateurs » a été
    rédigé en phrase. On découpe sur les virgules, points-virgules et « et ».
    """
    if isinstance(valeur, list):
        return [v for v in valeur if v is not None and str(v).strip()]
    if valeur is None:
        return []
    if isinstance(valeur, str):
        import re as _re
        morceaux = _re.split(r"\s*[;·•]\s*|\s+et\s+|,\s*", valeur.strip())
        return [m.strip() for m in morceaux if m.strip()]
    if isinstance(valeur, dict):
        return [str(v) for v in valeur.values() if v is not None]
    return [valeur]


def normaliser_analyse(analyse: dict) -> dict:
    """Garantit le type attendu pour chaque champ de l'analyse."""
    if not isinstance(analyse, dict):
        return {}
    for champ in ("utilisateurs", "contraintes", "concepts", "fonctionnalites", "mots_cles"):
        if champ in analyse:
            analyse[champ] = _en_liste(analyse[champ])
    return analyse


def _filtrer_fonctionnalites(brutes) -> list[str]:
    """Ne garde que les vraies capacités, pas les bouts de phrase du brief."""
    gardees: list[str] = []
    for f in brutes:
        texte = re.sub(r"\s+", " ", str(f)).strip()
        mots = [m for m in norm(texte).split() if len(m) > 2]
        if len(mots) < 2:
            continue
        # une capacité exprime une action ou un objet métier
        if all(m in FRAGMENTS or m in VIDES_FONCTION for m in mots):
            continue
        if texte not in gardees:
            gardees.append(texte)
    return gardees


VIDES_FONCTION = {"des", "les", "une", "pour", "avec", "dans", "sur", "par", "and",
                  "the", "of", "to", "for", "with", "a", "an", "in", "on"}


def _langue(texte: str) -> str:
    """Devine si un texte est en français ou en anglais.

    Volontairement simple : quelques mots-outils très fréquents suffisent à
    trancher, et une erreur de détection ne coûte que des libellés de gabarit.
    """
    t = f" {norm(texte)} "
    marqueurs_fr = (" le ", " la ", " les ", " des ", " une ", " pour ", " nous ",
                    " souhaitons ", " gestion ", " avec ")
    marqueurs_en = (" the ", " and ", " we ", " aim ", " develop ", " system ",
                    " platform ", " within ")
    fr = sum(t.count(m) for m in marqueurs_fr)
    en = sum(t.count(m) for m in marqueurs_en)
    return "en" if en > fr else "fr"


def _tronquer(texte: str, maximum: int) -> str:
    """Ramène un bloc de preuves sous la limite, en coupant à la bonne ligne.

    On ne coupe pas au milieu d'une preuve : la dernière ligne incomplète est
    supprimée, sinon le modèle lit une phrase tronquée et l'interprète.
    """
    if len(texte) <= maximum:
        return texte
    coupe = texte[:maximum]
    derniere_ligne = coupe.rfind("\n")
    if derniere_ligne > maximum * 0.7:
        coupe = coupe[:derniere_ligne]
    return coupe + "\n[… liste de preuves tronquée pour tenir dans le contexte …]"


def _analyse_de_secours(brief: str) -> dict:
    """Analyse minimale si le modèle ne rend pas un JSON exploitable.

    On ne renonce pas : le brief contient déjà de quoi chercher, à condition
    d'en retirer le vocabulaire de la demande (« nous souhaitons développer
    une application… »), qui ne désigne aucun document.
    """
    from .secours import mots_metier

    mots = mots_metier(brief)[:6]
    # même filtre que pour le modèle : un nom de produit ne se cherche pas
    sans_propres = retirer_noms_propres(
        brief, {"requete_fr": " ".join(mots), "requete_en": " ".join(mots),
                "intention": " ".join(mots[:3]), "concepts": list(mots),
                "sujet": " ".join(mots[:4]), "mots_cles": list(mots)})
    mots = [m for m in sans_propres["mots_cles"]] or mots
    return {
        "objectif": brief.strip().split(".")[0][:160],
        "intention": " ".join(mots[:3]),
        "concepts": mots[:4],
        "domaine": "",
        "sujet": " ".join(mots[:4]),
        "utilisateurs": [],
        "contraintes": [],
        "fonctionnalites": [],
        "requete_fr": " ".join(mots[:4]),
        "requete_en": " ".join(mots[:4]),
        "mots_cles": mots,
    }


def _toutes_taches(plan: dict) -> list[dict]:
    return [
        t
        for e in plan.get("epics", [])
        for s in e.get("stories", [])
        for t in s.get("tasks", [])
    ]


def nb_taches(plan: dict) -> int:
    return len(_toutes_taches(plan))


# ══════════════════════════════════════════════════════════════════════
# STRUCTURE DE TYPE JIRA
# ══════════════════════════════════════════════════════════════════════
# Un plan utile n'est pas une liste de titres : c'est un backlog. Chaque tâche
# porte donc ce qu'un ticket porte dans Jira, et le code calcule les clés
# (TF-12) et le chemin (TF-2.1.3) comme le ferait un outil de suivi.
TYPES_TACHE = {"dev": "Développement", "test": "Test", "config": "Configuration",
               "doc": "Documentation", "design": "Conception", "securite": "Sécurité"}
PRIORITES = ("Haute", "Moyenne", "Basse")
MOTS_TEST = {"test", "vérifier", "verifier", "valider", "recette", "scénario",
             "scenario", "couvrir", "contrôler", "controler", "non-régression"}
MOTS_CONFIG = {"configurer", "installation", "installer", "déployer", "deployer",
               "environnement", "pipeline", "ci", "cd", "terraform", "docker",
               "migration", "base de données", "serveur", "infrastructure"}
MOTS_SECU = {"authentification", "autorisation", "sécurité", "securite", "chiffrement",
             "injection", "csrf", "xss", "rôle", "role", "permission", "accès",
             "acces", "jeton", "token", "owasp", "contrôle d'accès", "hachage",
             "chiffrement", "authorization", "privilege", "force brute",
             "brute force", "rate limit", "limitation des tentatives"}
MOTS_DOC = {"documentation", "documenter", "guide", "manuel", "readme", "spécification",
            "specification", "cahier des charges"}
MOTS_DESIGN = {"maquette", "design", "ergonomie", "parcours", "ux", "interface",
               "charte", "prototype", "wireframe"}


def _type_tache(titre: str, description: str, annonce: str = "") -> str:
    """Déduit la nature d'une tâche de son vocabulaire, jamais d'une liste figée.

    Le TITRE fait foi. Une tâche nommée « Formulaire d'inscription » est du
    développement, même si sa description parle de mot de passe : sinon tout ce
    qui touche de près ou de loin à l'authentification serait classé
    « sécurité », et le backlog n'aurait plus de tâches de développement.
    La description ne sert qu'à départager un titre muet.
    """
    if annonce in TYPES_TACHE:
        return annonce
    familles = (("test", MOTS_TEST), ("securite", MOTS_SECU), ("config", MOTS_CONFIG),
                ("doc", MOTS_DOC), ("design", MOTS_DESIGN))
    titre_n = norm(titre)
    for type_, mots in familles:
        if any(m in titre_n for m in mots):
            return type_
    desc_n = norm(f"{titre} {description}")
    for type_, mots in familles:
        if any(m in desc_n for m in mots):
            return type_
    return "dev"


def _priorite(tache: dict, rang_tache: int, nb_taches: int) -> str:
    """Priorité calculée : sécurité et socle d'abord, puis l'ordre du backlog."""
    if tache.get("type") == "securite":
        return "Haute"
    if tache.get("sources"):
        return "Haute" if rang_tache < max(1, nb_taches // 3) else "Moyenne"
    return "Basse"


def nettoyer(plan: dict, nb_preuves: int) -> dict:
    """Normalise le plan et lui donne sa structure de backlog.

    Aucun nombre n'est imposé : ni épics, ni stories, ni tâches. Seules les
    structures vides sont supprimées, et chaque tâche reçoit les champs que
    réclame un outil de suivi (clé, type, priorité, critères et classe textuelle
    ajoutée ensuite par PlanAgent).
    """
    vues: set[str] = set()
    epics: list[dict] = []
    compteur = 0

    for i_epic, epic in enumerate(plan.get("epics", []), 1):
        if not isinstance(epic, dict):
            continue
        titre = str(epic.get("title", "")).strip()
        if not titre:
            continue
        stories = []
        for i_story, st in enumerate(epic.get("stories", []), 1):
            if not isinstance(st, dict):
                continue
            st_titre = str(st.get("title", "")).strip() or str(st.get("i_want", ""))[:60]
            if not st_titre:
                continue
            taches = []
            for t in st.get("tasks", []):
                if not isinstance(t, dict):
                    continue
                tt = str(t.get("title", "")).strip()
                if not tt or tt.lower() in vues:
                    continue          # doublon : on garde la première occurrence
                vues.add(tt.lower())
                src = []
                for s_ in t.get("sources") or []:
                    try:
                        n = int(s_)
                    except (TypeError, ValueError):
                        continue
                    if 1 <= n <= nb_preuves:
                        src.append(n)
                description = str(t.get("description", "")).strip()
                annonce = str(t.get("type", ""))
                taches.append({
                    "title": tt,
                    "description": description,
                    "sources": sorted(set(src)),
                    "type_brut": annonce,
                })

            if not taches:
                continue

            # ── champs Jira, calculés par le code ────────────────────
            for rang, t in enumerate(taches):
                t["type"] = _type_tache(t["title"], t["description"], t.pop("type_brut", ""))
                t["priorite"] = _priorite(t, rang, len(taches))
                if not t.get("criteres"):
                    t["criteres"] = _criteres(t)
                if not t.get("labels"):
                    t["labels"] = _labels(t, st_titre)
                compteur += 1
                t["cle"] = f"TF-{compteur}"
                t["chemin"] = f"TF-{i_epic}.{i_story}.{rang + 1}"

            stories.append({
                "cle": f"TF-{i_epic}.{i_story}",
                "title": st_titre,
                "as_a": str(st.get("as_a", "")).strip(),
                "i_want": str(st.get("i_want", "")).strip(),
                "so_that": str(st.get("so_that", "")).strip(),
                "acceptance": st.get("acceptance") or _acceptance(st, taches),
                "tasks": taches,
            })

        if stories:
            epics.append({
                "title": titre,
                "description": str(epic.get("description", "")).strip(),
                "stories": stories,
            })

    return {"epics": epics}


def _criteres(tache: dict) -> list[str]:
    """Critères d'acceptation déduits du type : ce qui rend la tâche « finie »."""
    t = tache["type"]
    titre = tache["title"]
    if t == "test":
        return [f"Le scénario de test de « {titre} » passe",
                "Le cas d'erreur est couvert",
                "La non-régression des tâches liées est vérifiée"]
    if t == "securite":
        return ["Le contrôle est effectif sur tous les points d'entrée",
                "Un test dédié prouve que l'accès non autorisé échoue",
                "Le comportement est journalisé"]
    if t == "config":
        return ["La configuration est reproductible sur un environnement neuf",
                "Elle est documentée et versionnée",
                "Un déploiement de bout en bout réussit"]
    if t == "doc":
        return ["Le document est relu et publié",
                "Il couvre le cas nominal et un cas d'erreur"]
    if t == "design":
        return ["La maquette est validée par le demandeur",
                "Les états vide, erreur et chargement sont représentés"]
    return ["Le comportement décrit est implémenté",
            "Les données invalides sont rejetées avec un message clair",
            "La fonctionnalité est couverte par au moins un test"]


def _labels(tache: dict, story: str) -> list[str]:
    return [tache["type"], norm(story).replace(" ", "-")[:24]]


def _acceptance(story: dict, taches: list[dict]) -> list[str]:
    """Critères d'acceptation de la story, dérivés de ses tâches.

    Un critère doit être observable. On part donc du besoin exprimé
    (« je veux… »), et on ajoute les critères que le contenu de la story
    impose : sécurité si elle touche aux accès, cas d'erreur toujours.
    """
    if not taches:
        return []
    veut = str(story.get("i_want", "")).strip() or str(story.get("title", ""))
    criteres = [
        f"Un utilisateur peut « {veut} » sans erreur",
        "Les données invalides sont refusées avec un message explicite",
        f"Les {len(taches)} tâches de la story sont terminées et relues",
    ]
    if any(t.get("type") == "securite" for t in taches):
        criteres.insert(1, "Un accès non autorisé à cette fonction est refusé et journalisé")
    return criteres


# Une contrainte n'est pas un mot à retrouver : c'est une exigence à couvrir.
# « web-based » se traduit par « responsive », « navigateur », « API REST » ;
# « mobile » par « responsive », « PWA ». Chercher la chaîne littérale fait
# signaler une contrainte comme absente alors que le plan la traite.
EQUIVALENTS = {
    "web": ("web", "navigateur", "browser", "responsive", "http", "api rest",
            "frontend", "front-end", "spa", "https", "webapp"),
    "web-based": ("web", "navigateur", "browser", "responsive", "http", "api"),
    "mobile": ("mobile", "responsive", "pwa", "application mobile", "tablette"),
    "responsive": ("responsive", "mobile", "tablette", "adaptive"),
    "temps réel": ("temps réel", "real-time", "websocket", "sse", "live"),
    "real-time": ("real-time", "temps réel", "websocket", "sse"),
    "multi": ("multi", "plusieurs", "multiple", "multi-tenant", "multi-utilisateur"),
    "multi-utilisateurs": ("multi", "plusieurs utilisateurs", "rôle", "role", "rbac"),
    "hors ligne": ("hors ligne", "offline", "indexeddb", "cache local"),
    "offline": ("offline", "hors ligne", "indexeddb", "cache local"),
    "sécurité": ("sécurité", "security", "rbac", "chiffrement", "encryption",
                 "owasp", "authentification", "authentication"),
    "security": ("security", "sécurité", "rbac", "encryption", "owasp"),
    "cloud": ("cloud", "aws", "azure", "gcp", "kubernetes", "déploiement"),
    "scalable": ("scalable", "scalabilité", "autoscale", "load balancer",
                 "répartition de charge"),
    "api": ("api", "rest", "endpoint", "graphql"),
}


def _couverture_contrainte(contrainte: str, texte: str) -> bool:
    """La contrainte est-elle traitée, directement ou par un équivalent connu ?"""
    c = norm(contrainte)
    if c and c in texte:
        return True
    for cle, variantes in EQUIVALENTS.items():
        if norm(cle) in c or c in norm(cle):
            return any(norm(v) in texte for v in variantes)
    return False


def _manquantes(plan: dict, elements: list[str]) -> list[str]:
    if not elements:
        return []
    texte = norm(" ".join(
        f"{e.get('title','')} {s.get('title','')} {s.get('i_want','')} "
        f"{t.get('title','')} {t.get('description','')}"
        for e in plan.get("epics", [])
        for s in e.get("stories", [])
        for t in s.get("tasks", [])
    ))
    vides = {"des", "les", "une", "pour", "avec", "dans", "sur", "par", "and", "the"}
    out = []
    for el in elements:
        if _couverture_contrainte(el, texte):
            continue
        mots = [m for m in norm(el).split() if len(m) > 3 and m not in vides]
        if mots and not any(m[:6] in texte for m in mots):
            out.append(el)
    return out


def valider(plan: dict, fonctionnalites: list[str], contraintes: list[str],
            nb_preuves: int, brief: str = "") -> list[str]:
    defauts: list[str] = []
    taches = _toutes_taches(plan)
    if not taches:
        return ["le plan ne contient aucune tâche"]

    titres = [t["title"].lower() for t in taches]
    doublons = [t for t, n in Counter(titres).items() if n > 1]
    if doublons:
        defauts.append(f"titres en double : {doublons[:3]}")

    if nb_preuves and not any(t["sources"] for t in taches):
        defauts.append("aucune tâche ne cite de preuve")

    mf = _manquantes(plan, fonctionnalites)
    if mf:
        defauts.append("fonctionnalités demandées absentes : " + ", ".join(mf))
    mc = _manquantes(plan, contraintes)
    if mc:
        defauts.append("contraintes non traitées : " + ", ".join(mc))
    md = _defauts_decoupage(plan)
    defauts.extend(md)
    if brief:
        defauts.extend(_defaut_langue(plan, brief))
    return defauts


# Mots-outils qui trahissent une rédaction française, et leur équivalent anglais.
_TRACES_FR = (" le ", " la ", " les ", " des ", " une ", " du ", " au ", " aux ",
              " pour ", " avec ", " sur ", " dans ", " et ", " ou ", " ne ",
              " est ", " sont ", " être ", " avoir ", " faire ", " afin ")
_TRACES_EN = (" the ", " and ", " with ", " for ", " of ", " to ", " is ", " are ",
              " from ", " into ", " a ", " an ", " in ", " on ", " by ", " that ")


def _langue_du_plan(plan: dict) -> float:
    """Proportion de français dans le texte du plan : 0 = anglais, 1 = français.

    On mesure sur les titres et descriptions, pas sur les preuves citées : le
    plan peut citer des sources anglaises tout en étant rédigé en français.
    """
    morceaux = []
    for e in plan.get("epics", []):
        morceaux += [e.get("title", ""), e.get("description", "")]
        for st in e.get("stories", []):
            morceaux += [st.get("title", ""), st.get("i_want", ""), st.get("so_that", "")]
            morceaux += list(st.get("acceptance") or [])
            for t in st.get("tasks", []):
                morceaux += [t.get("title", ""), t.get("description", "")]
    texte = " " + norm(" ".join(str(m) for m in morceaux)) + " "
    if len(texte) < 80:
        return 0.5
    fr = sum(texte.count(m) for m in _TRACES_FR)
    en = sum(texte.count(m) for m in _TRACES_EN)
    return fr / (fr + en) if (fr + en) else 0.5


def _defaut_langue(plan: dict, brief: str) -> list[str]:
    """Le plan doit être en français, et dans une seule langue.

    Le contrôle est le même quel que soit le brief : le français est la langue
    de sortie. Il porte sur le texte rédigé (titres, descriptions, critères),
    jamais sur les preuves citées, qui peuvent être anglaises.
    """
    part_fr = _langue_du_plan(plan)
    if part_fr >= 0.35:
        return []
    return [f"plan rédigé en anglais ({1 - part_fr:.0%} de mots anglais) alors "
            f"que le plan doit être en français — traduis TOUT le plan"]


def _defauts_decoupage(plan: dict) -> list[str]:
    """Repère ce qui n'est pas un vrai backlog : stories et tâches trop rares.

    Aucun nombre n'est imposé — on ne réclame pas « 5 épics ». On signale
    seulement les niveaux qui ne sont pas DÉCOMPOSÉS : une story à une tâche,
    un épic à une seule story. Ce sont des symptômes, pas des quotas.
    """
    defauts: list[str] = []
    epics = plan.get("epics", [])
    if not epics:
        return defauts

    maigres_stories = [s["title"] for e in epics for s in e.get("stories", [])
                       if len(s.get("tasks", [])) < 2]
    if maigres_stories:
        defauts.append(f"{len(maigres_stories)} story(s) non décomposée(s) "
                       f"(une seule tâche) : {maigres_stories[:3]}")

    epics_plats = [e["title"] for e in epics if len(e.get("stories", [])) < 2]
    if epics_plats and len(epics) > 1:
        defauts.append(f"{len(epics_plats)} épic(s) à story unique : {epics_plats[:3]}")

    # un backlog sans test ni sécurité est incomplet pour une application
    types = {t.get("type") for e in epics for s in e.get("stories", [])
             for t in s.get("tasks", [])}
    if "test" not in types and nb_taches(plan) >= 10:
        defauts.append("aucune tâche de test")
    if "securite" not in types and nb_taches(plan) >= 10:
        defauts.append("aucune tâche de sécurité")
    return defauts


def metriques(plan: dict, fonctionnalites: list[str], nb_preuves: int) -> dict:
    taches = _toutes_taches(plan)
    stories = [s for e in plan.get("epics", []) for s in e.get("stories", [])]
    sourcees = [t for t in taches if t["sources"]]
    titres = [t["title"].lower() for t in taches]
    cites = [s for t in taches for s in t["sources"]]
    couv_f = len(fonctionnalites) - len(_manquantes(plan, fonctionnalites))
    return {
        "epics": len(plan.get("epics", [])),
        "stories": len(stories),
        "taches": len(taches),
        "sourcees": len(sourcees),
        "taux_ancrage": round(len(sourcees) / len(taches), 2) if taches else 0.0,
        "doublons": len(titres) - len(set(titres)),
        "diversite": len(set(cites)),
        "couverture": round(couv_f / len(fonctionnalites), 2) if fonctionnalites else 1.0,
        "types": {ty: sum(1 for t in taches if t.get("type") == ty)
                  for ty in sorted({t.get("type") for t in taches if t.get("type")})},
        "taches_par_story": round(len(taches) / len(stories), 2) if stories else 0.0,
    }
