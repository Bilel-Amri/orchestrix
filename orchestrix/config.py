"""Tous les réglages en un seul endroit.

Les valeurs par défaut conviennent. Si vous voulez ajuster le comportement,
copiez ce fichier en `config_local.py` et surchargez ce que vous voulez — ou
plus simple, utilisez les variables d'environnement indiquées.

Aucun de ces réglages ne dépend d'un domaine particulier : ce sont des
proportions et des seuils, pas des listes de métiers.
"""

from __future__ import annotations

import os


def _env(nom: str, defaut: str = "") -> str:
    """Lit ORCHESTRIX_<NOM>, et retombe sur l'ancien PLANAGENT_<NOM>."""
    return os.environ.get("ORCHESTRIX_" + nom,
                          os.environ.get("PLANAGENT_" + nom, defaut))


def _entier(nom: str, defaut: int) -> int:
    try:
        return int(_env(nom, str(defaut)))
    except (TypeError, ValueError):
        return defaut


def _booleen(nom: str, defaut: bool) -> bool:
    v = _env(nom, "") or None
    if v is None:
        return defaut
    return v.strip().lower() not in {"0", "false", "non", "no", "off", ""}


def _flottant(nom: str, defaut: float) -> float:
    try:
        return float(_env(nom, str(defaut)))
    except (TypeError, ValueError):
        return defaut


# ── Découpage en passages ────────────────────────────────────────────
# 600 caractères ≈ un paragraphe. Plus petit = passages plus précis mais plus
# nombreux ; plus grand = plus de contexte par passage mais un bruit diffus.
TAILLE_PASSAGE = _entier("TAILLE_PASSAGE", 600)
CHEVAUCHEMENT = _entier("CHEVAUCHEMENT", 120)

# ── Recherche ────────────────────────────────────────────────────────
# Nombre de passages transmis au modèle. 12 par défaut ; montez à 16-20 si vos
# plans manquent de détails, descendez à 8 si le modèle dérive.
TOP_PASSAGES = _entier("TOP_PASSAGES", 12)
RRF_K = _entier("RRF_K", 60)

# Poids du reranking — la somme des trois doit valoir 1.
POIDS_HYBRIDE = _flottant("POIDS_HYBRIDE", 0.50)
POIDS_COUVERTURE = _flottant("POIDS_COUVERTURE", 0.35)
POIDS_SOURCE = _flottant("POIDS_SOURCE", 0.15)
PENALITE_REPETITION = _flottant("PENALITE_REPETITION", 0.25)
# Pénalité par SOURCE : évite qu'une seule source (App Store, README d'un
# unique dépôt) occupe toutes les places et appauvrisse le plan.
PENALITE_SOURCE = _flottant("PENALITE_SOURCE", 0.08)

# ── Filtrage des sources ─────────────────────────────────────────────
# Un document doit citer les mots de la requête, en mots entiers.
SEUIL_TITRE = _entier("SEUIL_TITRE", 1)
SEUIL_CORPS = _entier("SEUIL_CORPS", 2)

# Étape 4 — pertinence des projets. Plus haut = plus sévère = moins de
# documents mais plus sûrs. 0.30 convient ; descendre à 0.20 pour un sujet
# rare où l'on préfère du bruit à une source vide.
SEUIL_PERTINENCE = _flottant("SEUIL_PERTINENCE", 0.30)

# ── Extraction des fonctionnalités ───────────────────────────────────
# Proportionnel au volume collecté, jamais un nombre figé.
FONCTIONS_MIN = _entier("FONCTIONS_MIN", 15)
FONCTIONS_MAX = _entier("FONCTIONS_MAX", 80)
CARACTERES_PAR_FONCTION = _entier("CARACTERES_PAR_FONCTION", 400)

# ── Génération ───────────────────────────────────────────────────────
# 0.2 = ancré sur les preuves. Montez à 0.5 si vous voulez des plans plus
# créatifs (et moins sourcés), descendez à 0 si vous voulez de la constance.
TEMPERATURE_ANALYSE = _flottant("TEMPERATURE_ANALYSE", 0.1)
TEMPERATURE_PLAN = _flottant("TEMPERATURE_PLAN", 0.2)
TEMPERATURE_CORRECTION = _flottant("TEMPERATURE_CORRECTION", 0.3)
# Un backlog détaillé (épics → stories → tâches, avec critères d'acceptation)
# demande beaucoup de tokens. 6000 suffisait pour un plan de 23 tâches ; un
# backlog complet en réclame davantage. Aucun nombre d'éléments n'est imposé.
MAX_TOKENS_PLAN = _entier("MAX_TOKENS_PLAN", 16000)
# L'analyse produit 9 champs, dont deux listes (concepts, fonctionnalités) et
# trois phrases. 800 tokens étaient trop justes : le JSON était coupé, puis
# réparé, puis — en Python 3.14 — refusé. 2000 laisse de la marge.
MAX_TOKENS_ANALYSE = _entier("MAX_TOKENS_ANALYSE", 2000)
# Nombre de preuves envoyées au modèle. Chaque preuve pèse ~40 mots ; 40 preuves
# suffisent à couvrir un projet, et 60 faisaient dépasser la limite de contexte
# du modèle (erreur 413) lors de la relance de correction.
MAX_PREUVES_PROMPT = _entier("MAX_PREUVES_PROMPT", 40)
# Garde-fou en caractères : ~4 caractères par token, on reste sous 24 000
# caractères de preuves, soit ~6 000 tokens, très en dessous de la limite.
MAX_CARACTERES_PROMPT = _entier("MAX_CARACTERES_PROMPT", 24000)

# ── Réseau ───────────────────────────────────────────────────────────
TIMEOUT_SOURCE = _entier("TIMEOUT_SOURCE", 14)
CACHE_MINUTES = _entier("CACHE_MINUTES", 30)

# ── Langue de sortie ─────────────────────────────────────────────────
# Le plan, les libellés de l'interface et l'export sont rédigés en FRANÇAIS,
# quel que soit la langue du brief. Mettre PLANAGENT_FRANCAIS=0 pour revenir à
# l'ancien comportement (plan dans la langue du brief).
FRANCAIS = _booleen("FRANCAIS", True)
# Les preuves sont des extraits de documents réels, souvent anglais. Les citer
# mot pour mot est plus fidèle ; les traduire rend le plan plus lisible.
# Mettre PLANAGENT_TRADUIRE_PREUVES=0 pour les citer telles quelles.
# Rappel : le texte AFFICHÉ dans le brief et dans la fiche de preuve suit
# toujours la langue de l'interface.
TRADUIRE_PREUVES = _booleen("TRADUIRE_PREUVES", True)

# Nombre de preuves traduites dans l'attente de la génération. Chaque preuve
# citée dans le plan doit être lisible ; au-delà, la traduction se poursuit
# en tâche de fond et la page se rafraîchit quand elle aboutit. Traduire 40
# extraits avant de rendre la main coûtait une dizaine de secondes pour des
# citations que personne n'avait encore ouvertes.
PREUVES_TRADUITES_IMMEDIAT = _entier("PREUVES_TRADUITES_IMMEDIAT", 12)

# ── Service de modèle de complexité (facultatif) ─────────────────────
# Laissé vide, aucune requête n'est faite : la charge des tâches reste
# calculée par les règles internes. Renseigné, la plateforme envoie le titre
# et la description de chaque tâche au service et reprend sa prédiction.
# Voir INTEGRATION-MODELE.md.
URL_MODELE = os.environ.get("URL_MODELE", "").rstrip("/")
