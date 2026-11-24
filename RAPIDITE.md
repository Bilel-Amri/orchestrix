# Orchestrix — la génération accélérée

Compte rendu de la passe de rapidité. Tous les chiffres sont mesurés sur cette
machine, pas estimés.

---

## 1. Le diagnostic : le temps n'était pas là où on le croyait

Avant d'optimiser quoi que ce soit, j'ai chronométré chaque poste.

| Poste | Mesure | Verdict |
|---|---|---|
| 9 sources web interrogées **en parallèle** | **0,44 s** | hors de cause |
| Les mêmes sources, l'une après l'autre (référence) | 11,41 s | ce qu'on aurait payé sans parallélisme |
| Chaîne de recherche locale (24 documents, 312 passages) | **0,13 s** | hors de cause |
| Traduction des preuves, 1 requête par lot de 20 | 3 à 12 s **après** la fin du travail utile | en cause |
| Rédaction du plan (6 000 à 12 000 jetons) | 20 à 40 s | poste principal, incompressible |

Autrement dit : le réseau et la recherche ne coûtaient rien. Tout le temps
partait dans les appels au modèle, et une partie de ces appels ne servait
qu'à **traduire des citations** que l'utilisateur n'avait pas encore ouvertes.

## 2. Ce qui a été corrigé

**Connexion gardée ouverte.** `urllib` refermait la connexion après chaque
réponse : chaque appel repayait poignée de main TCP et négociation TLS.
`httpclient.Session` conserve la connexion par hôte et par fil d'exécution.

```
1er appel  0,059 s   →   3e appel  0,024 s      (api.groq.com)
```

**Découverte des modèles mise en cache.** `modele_rapide()` interrogeait
`/models` à *chaque* génération ; la liste est désormais gardée en mémoire.

**Préchauffage au démarrage.** La connexion et la liste des modèles sont
préparées pendant que l'utilisateur lit la page : le premier clic ne paie plus
ces allers-retours.

**Lecture en flux.** La réponse du modèle arrive jeton par jeton au lieu
d'attendre la fin. Le monde extérieur ne va pas plus vite, mais l'attente
devient lisible — et une coupure à `max_tokens` n'est plus une perte sèche :
le JSON tronqué est refermé proprement (`_ferme_les_accolades`) au lieu d'être
jeté et repayé.

**Traduction en deux temps.** Les 12 premières citations sont traduites avant
l'affichage (réglage `PREUVES_TRADUITES_IMMEDIAT`) ; les autres suivent en
tâche de fond, par lots de 20 **en parallèle**, et la page les reçoit au
rechargement suivant.

**Affichage anticipé du plan.** Dès que le plan est écrit, la page se remplit.
Le statut passe par un état `traduction` intermédiaire : plus personne
n'attend une étape qui ne le concerne pas.

## 3. Ce que voit l'utilisateur

Le sablier muet a été remplacé par un suivi réel, alimenté par le compteur de
jetons du modèle :

```
Génération en cours
Rédaction du plan · 6 500 jetons écrits
████████████████████░░░░░  77 %
Temps écoulé 22 s
```

L'état est servi par `/api/etat` (champ `avancement`) et affiché sans
rechargement de page.

## 4. Ce qui reste lent, et pourquoi ce n'est pas un défaut

Un plan de 10 000 jetons demande 20 à 40 secondes de rédaction : c'est le
débit du modèle, pas celui du code. Deux leviers existent, tous deux au prix
d'un compromis :

- **réduire `MAX_TOKENS_PLAN`** (16000 aujourd'hui) : plan plus court donc
  moins de tâches détaillées ;
- **changer de modèle** : `llama-3.1-8b-instant` est plus rapide, plus
  superficiel sur un plan de cette taille.

Ni l'un ni l'autre n'a été appliqué sans votre accord.

## 5. Vérifications

| Suite | Résultat |
|---|---|
| moteur / plateforme | **35/35** |
| validation du prompt | **11/11** |
| bout en bout | **21/21** |
| interface | **23/23** |
| validation | **17/17** |
| formes du plan | **6/6** |

Contrôles supplémentaires de cette passe :

- flux SSE validé contre un faux serveur Groq : 40 fragments, 6 remontées de
  compteur, texte reconstitué à l'identique ;
- erreur 429 : le délai `Retry-After` est respecté (7 s annoncés → 7 s
  attendus) pour le flux comme pour l'appel simple ;
- JSON tronqué : `{"epics":[{"nom":"Stock","taches":[{"t":1},{"t":2` est
  refermé et redevient lisible ;
- archive dézippée dans un environnement **sans `requests`** : démarrage OK,
  `/` répond 200, `/api/etat` répond `{"statut": "idle"}` ;
- chaîne d'états rejouée de bout en bout (`en_cours` → `traduction` → `termine`)
  avec 30 preuves : le plan est servi avant la fin des traductions, et les
  30 citations sont traduites à l'issue de la passe de fond.

## 6. Réglages utiles

```bash
MAX_TOKENS_PLAN=12000                 # plan plus court, génération plus rapide
PREUVES_TRADUITES_IMMEDIAT=6          # affichage encore plus tôt
PLANAGENT_TRADUIRE_PREUVES=0          # citer les preuves dans leur langue d'origine
```
