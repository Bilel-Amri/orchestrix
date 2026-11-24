"""Repli quand le modèle ne rend pas une analyse exploitable.

L'étape ① est un appel au modèle. Quand cet appel échoue (quota, JSON coupé,
réseau), on ne renonce pas : le brief contient déjà de quoi chercher, à
condition d'en retirer le vocabulaire de la demande (« nous souhaitons
développer une application… »), qui ne désigne aucun document sur le web.

Ces deux tables servaient au mode démonstration, supprimé depuis. Elles restent
ici parce que le repli en a besoin : c'est la seule partie qui garde une valeur
quand il n'y a pas de modèle.
"""

from __future__ import annotations

import re

from .sources import VIDES, norm

# Mots de la demande elle-même : ils décrivent la formulation, pas le métier.
DEMANDE = {
    "souhaitons", "souhaite", "souhait", "voulons", "veut", "veux", "desirons",
    "developper", "developpement", "developpe", "creer", "creation", "cree",
    "application", "applications", "app", "logiciel", "logiciels", "plateforme",
    "plateformes", "systeme", "systemes", "outil", "outils", "solution",
    "solutions", "site", "web", "mobile", "service", "services", "produit",
    "entreprise", "entreprises", "societe", "societes", "client", "clients",
    "permettant", "permet", "permettre", "appelee", "appele",
    "nommee", "notre", "nous", "vous", "leur", "leurs", "celui", "celle",
    "depuis", "ainsi", "aussi", "tous", "toutes", "tout", "toute", "seule",
    "meme", "etre", "avoir", "faire", "cette", "avec", "pour",
    "dans", "sous", "sur", "les", "des", "une", "aux", "par", "que", "qui",
    "son", "ses", "mon", "mes", "est", "sont", "peut", "peuvent",
}

# Racines suffisantes pour retrouver l'équivalent anglais courant. Ce n'est pas
# un traducteur : c'est un filet de sécurité pour que la requête anglaise ne
# soit pas la requête française recopiée.
EN = {
    "gestion": "management", "gerer": "manage", "bibliotheque": "library",
    "livre": "book", "livres": "book", "pret": "loan", "prets": "loan",
    "lecteur": "reader", "lecteurs": "reader", "adherent": "member",
    "adherents": "member", "catalogue": "catalog", "reservation": "reservation",
    "reserver": "reserve", "emprunt": "borrowing", "emprunter": "borrow",
    "retour": "return", "penalite": "fine", "amende": "fine", "stock": "stock",
    "commande": "order", "commandes": "order", "paiement": "payment",
    "facture": "invoice", "panier": "cart", "produit": "product",
    "vendeur": "seller", "vendeurs": "seller", "acheteur": "buyer",
    "utilisateur": "user", "utilisateurs": "user", "compte": "account",
    "comptes": "account", "authentification": "authentication",
    "connexion": "login", "mot": "word", "passe": "password",
    "securite": "security", "role": "role", "roles": "role",
    "droit": "permission", "droits": "permission", "profil": "profile",
    "patient": "patient", "patients": "patient", "medecin": "doctor",
    "medecins": "doctor", "rendez": "appointment", "rendezvous": "appointment",
    "consultation": "consultation", "dossier": "record", "dossiers": "record",
    "ordonnance": "prescription", "pharmacie": "pharmacy", "eleve": "student",
    "eleves": "student", "etudiant": "student", "etudiants": "student",
    "cours": "course", "note": "grade", "notes": "grade", "presence": "attendance",
    "classe": "class", "classes": "class", "emploi": "schedule", "temps": "time",
    "projet": "project", "projets": "project", "tache": "task", "taches": "task",
    "equipe": "team", "equipes": "team", "planifier": "plan",
    "organiser": "organize", "collaborer": "collaborate",
    "assigner": "assign", "affecter": "assign", "valider": "approve",
    "notifier": "notify", "partager": "share", "exporter": "export",
    "importer": "import", "rechercher": "search", "filtrer": "filter",
    "commenter": "comment", "archiver": "archive", "facturer": "invoice",
    "planning": "planning", "echeance": "deadline", "priorite": "priority",
    "statut": "status", "avancement": "progress", "indicateur": "metric",
}


def mots_metier(brief: str) -> list[str]:
    """Mots du brief qui décrivent le métier, pas la formulation de la demande."""
    bruts = re.findall(r"[a-zA-ZÀ-ÿ0-9]{4,}", brief)
    vus: list[str] = []
    for m in bruts:
        n = norm(m)
        if n in DEMANDE or n in VIDES or len(n) < 4:
            continue
        if n not in vus:
            vus.append(n)
    return vus or [norm(m) for m in bruts[:5]]


def traduire(mots: list[str]) -> list[str]:
    """Équivalents anglais connus, mot inchangé sinon."""
    return [EN.get(m, m) for m in mots]
