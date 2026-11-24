# Orchestrix — comprendre le projet de A à Z

Ce document explique **ce que fait l'agent, pourquoi il est construit ainsi, et à
quoi sert chaque fichier**. Il est écrit pour être lu sans connaissances
avancées : chaque terme technique est expliqué la première fois qu'il apparaît.

---

## 1. Le problème que le projet résout

Un chef de projet écrit une phrase :

> « Application de gestion de bibliothèque scolaire avec prêt de livres. »

Il attend en retour un **plan de projet complet** : les grands chantiers, les
besoins des utilisateurs, et le travail concret à faire, présenté comme dans
Jira — avec des clés, des types, des priorités, des estimations et des critères
d'acceptation.

Deux choses rendent cela difficile.

**Première difficulté : un plan inventé ne vaut rien.** Un modèle de langage
sait rédiger un plan crédible pour n'importe quel sujet, mais il l'invente. Rien
ne garantit qu'il correspond à ce qui se fait réellement dans ce métier-là.

**Seconde difficulté : un modèle de langage se trompe sur ce qui se vérifie.**
Il cite volontiers une source qui n'existe pas, compte mal, et se contredit.

La réponse du projet tient en une phrase :

> **Aller chercher ce qui existe déjà** dans des logiciels comparables, **garder
> la trace**, et **s'en servir** pour écrire le plan — tout ce qui est
> vérifiable étant confié au programme, pas au modèle.

---

## 2. Vue d'ensemble : qui fait quoi

Le projet est découpé en **deux mondes** qui ne se mélangent pas.

| | Le modèle de langage (LLM) | Le programme (Python) |
|---|---|---|
| **Ce qu'il fait** | comprendre la demande, rédiger le backlog | tout le reste : chercher, filtrer, classer, découper, numéroter, vérifier |
| **Nombre d'interventions** | 2 (+1 en cas de correction) | l'intégralité du parcours |
| **Pourquoi** | il est bon en interprétation et en rédaction | il ne se trompe pas sur le comptage, les citations, les doublons |

Concrètement : le modèle **écrit du texte**, le programme **fabrique la
structure**. Le modèle ne choisit jamais une clé `TF-12`, ne décide jamais
qu'une tâche vaut 5 points, ne peut pas citer une preuve qui n'existe pas — ces
trois choses sont faites par le code, après coup.

Cette frontière est le cœur de l'architecture. Retenez-la, tout le reste en
découle.

---

## 3. Le vocabulaire du projet

Quelques mots reviennent sans cesse. Les voici une fois pour toutes.

- **Brief** — la phrase du chef de projet, au départ. Peut être en français ou
  en anglais.
- **Source** — un site web interrogé (GitHub, Wikipédia…). Il y en a neuf.
- **Document** — ce qu'une source renvoie : un titre, une adresse, un texte.
- **Preuve** — un énoncé court et vérifiable tiré d'un document, par exemple
  « Enregistrez un prêt et sa date de retour ». Chaque preuve garde l'adresse du
  document d'où elle vient.
- **Passage** — un morceau de 600 caractères d'un document, utilisé pour la
  recherche interne.
- **Épic** — un grand chantier (« Gestion des prêts »).
- **Story** — un besoin d'utilisateur, raconté à la première personne
  (« En tant que bibliothécaire, je veux prêter un exemplaire »).
- **Tâche** — le travail concret d'une équipe (« Créer le formulaire de prêt »).
- **Backlog** — l'ensemble épics → stories → tâches.
- **LLM** — le modèle de langage, ici celui de Groq.

---

## 4. Les neuf étapes, une par une

Le parcours suit toujours le même ordre. Les étapes marquées **[LLM]** sollicitent
le modèle ; les autres sont du programme pur.

### ① Analyse du besoin — [LLM]

Le modèle lit le brief et en tire une **fiche de compréhension** à onze champs :
objectif, intention, concepts, domaine, sujet, utilisateurs, contraintes,
fonctionnalités demandées, requête de recherche en français, la même en anglais,
et des mots-clés du métier.

**Pourquoi c'est indispensable.** On ne cherche pas sur le web avec les mots du
client. Quelqu'un qui écrit « une plateforme pour que mes équipes sachent qui
fait quoi et quand » ne doit pas faire chercher cette phrase : elle ne désigne
aucun logiciel. L'étape ① la traduit en vocabulaire métier — « suivi de tâches,
assignation, échéances, planning d'équipe ».

Deux nettoyages sont ensuite faits **par le programme**, pas par le modèle :
les noms propres inventés (« TaskFlow ») sont retirés de la recherche, car une
marque qui n'existe pas ne renverra jamais rien ; et les fausses
fonctionnalités creuses (« plateforme en ligne unique ») sont écartées.

*Si cet appel échoue, le programme fabrique une analyse de secours à partir des
mots métier du brief : le parcours continue, en moins bon.*

### ② Construction de la requête — programme

Le programme assemble une longue requête de recherche en classant les morceaux
par ordre d'importance : d'abord l'intention, puis les concepts, puis les
fonctionnalités, puis les deux requêtes français/anglais, puis le sujet, les
mots-clés, l'objectif et les contraintes.

Cet ordre n'est pas décoratif : c'est ce qui décide de la densité de vocabulaire
métier que verront les étapes suivantes.

### ③ Collecte des neuf sources — programme

Les neuf sources sont interrogées **en même temps**, chacune avec la formulation
qui lui convient.

| Source | Ce qu'elle apporte |
|---|---|
| GitHub | dépôts de code de logiciels comparables (README) |
| GitLab | idem, autre plateforme |
| Apache | projets de la fondation Apache |
| OWASP | les dix risques de sécurité majeurs (obligations, pas fonctionnalités) |
| Software Heritage | archive universelle du code |
| SRS | modèle de cahier des charges (structure d'exigences) |
| Wikipédia | définition encyclopédique du domaine |
| iTunes | applications grand public comparables |
| TED | marchés publics européens |

Trois points techniques importants :

- **Parallélisme.** Neuf requêtes lancées ensemble prennent le temps de la plus
  lente, pas la somme des neuf.
- **Requêtes différentes par source.** Wikipédia veut un concept, GitHub du
  vocabulaire de projet, iTunes du vocabulaire grand public. On ne leur envoie
  pas la même chaîne.
- **Repli en cascade.** Si l'API officielle de GitHub est bloquée par un quota,
  le programme lit le fichier directement sur `raw.githubusercontent.com`, puis
  en dernier recours la page HTML. Une source qui tombe ne vide pas la collecte.
- **Cache.** Les résultats sont gardés 30 minutes sur le disque : relancer le
  même brief ne redemande rien au réseau.

### ④ Vérification de la pertinence — programme

**C'est l'étape que beaucoup d'agents sautent, et elle se fait avant tout
traitement.** Chaque document reçoit une note de 0 à 1 et un verdict : retenu,
ou écarté avec son motif.

La note combine trois choses : le recouvrement avec la requête (en donnant plus
de poids aux mots rares — un mot présent partout ne distingue rien), la densité
du sujet dans le texte, et sa présence dans le titre.

Trois sources (SRS, OWASP, TED) sont **conservées sans note** : elles apportent
des exigences transverses qui ne citent jamais un métier particulier.

**Pourquoi avant ?** Parce que l'étape suivante coûte proportionnellement au
volume de texte. Filtrer d'abord, c'est ne pas gaspiller de calcul sur un dépôt
qui parle d'autre chose. C'est aussi ce qui permet d'afficher, dans l'onglet
Sources, la raison exacte d'un rejet.

### ⑤ Recherche dans les documents — programme

Les documents retenus sont découpés en passages de 600 caractères, avec un
chevauchement de 120 pour ne jamais couper une phrase en deux. Puis **quatre
étages** classent ces passages :

1. **BM25** — classement par mots. Les termes rares et présents dans peu de
   passages pèsent plus lourd.
2. **Vectoriel** — classement par proximité de sens, calculé sur la base des
   mots employés (technique dite LSA). Ce n'est pas un modèle d'intelligence
   artificielle : c'est un calcul statistique. Il capte les textes qui parlent
   de la même chose avec un vocabulaire proche, pas les synonymes lointains.
3. **Fusion (RRF)** — les deux classements sont combinés. Un passage bien placé
   dans les deux remonte ; un passage excellent dans un seul remonte moins.
4. **Reranking** — score final pondéré : 50 % du score fusionné, 35 % de la
   couverture des concepts demandés, 15 % de la fiabilité de la source, plus un
   bonus si le sujet est dans le titre. Puis des **pénalités** : chaque passage
   supplémentaire issu du même document coûte cher, et chaque passage
   supplémentaire issu de la même source coûte un peu.

Cette dernière pénalité est une correction née de l'usage : sans elle, les
fiches d'applications (courtes et nombreuses) occupaient les douze places et les
README, bien plus riches, étaient évincés.

On garde les **12 meilleurs passages**.

### ⑥ Extraction des fonctionnalités — programme

De ces passages, le programme tire des énoncés utilisables, rangés en trois
familles :

- **[FONCTION]** — une fonctionnalité observée dans un logiciel comparable ;
- **[EXIGENCE]** — une obligation de sécurité (OWASP) ;
- **[EXTRAIT]** — un élément de contexte, qui ne justifie pas une tâche à lui
  seul.

### ⑦ Validation des fonctionnalités — programme

Nettoyage (icônes, caractères parasites), suppression des doublons, contrôle que
chaque énoncé possède bien une preuve et qu'il est pertinent, classement par
catégorie, puis bornage entre 15 et 80 énoncés.

Ces bornes ne sont pas des quotas de production : ce sont des garde-fous pour
que l'étape suivante ne reçoive ni trop peu, ni trop.

### ⑧ Génération du backlog — [LLM]

Le modèle reçoit le brief, la fiche de compréhension de l'étape ①, et les
preuves retenues **numérotées**. Il écrit le backlog : épics, stories avec récit
et critères d'acceptation, tâches avec type et numéros de preuves.

**Puis le programme reprend la main** et fabrique tout ce qui doit être exact :

| Ce qui est calculé par le programme | Comment |
|---|---|
| Clé de chaque tâche | `TF-1`, `TF-2`… en séquence |
| Chemin hiérarchique | `TF-2.1.3` (épic 2, story 1, tâche 3) |
| Type de tâche | déduit de l'intitulé (développement, test, configuration, documentation, conception, sécurité) |
| Estimation | table par nature de travail, majorée si la description est riche |
| Priorité | sécurité et socle technique d'abord, puis position dans le backlog |
| Points d'une story | somme des estimations de ses tâches |
| Critères d'acceptation | générés si le modèle n'en a pas donné |

**Aucun de ces nombres n'est fourni au modèle.** C'est ce qui garantit qu'il n'y
a jamais de « valeur statique 5 » posée arbitrairement : l'estimation découle du
contenu de la tâche.

### ⑨ Validation finale et export — programme

Le programme contrôle le plan, point par point :

- **Citations** — toute tâche qui cite une preuve inexistante (le `[7]` alors
  qu'il n'y a que six preuves) **perd sa citation**. C'est le code qui la
  supprime, pas le modèle qui se corrige.
- **Doublons** — deux tâches au même intitulé sont signalées.
- **Couverture** — chaque fonctionnalité et chaque contrainte du brief doit
  apparaître, directement ou par un équivalent connu (« web-based » est
  considéré couvert par « responsive », « navigateur », « API REST », « HTTPS »).
- **Découpage** — une story à une seule tâche, ou un épic à une seule story, est
  signalé comme insuffisamment découpé. Aucun nombre n'est imposé, seul le
  manque de décomposition l'est.
- **Langue** — le plan doit être en français, même si le brief est en anglais.

Si des défauts subsistent, **une relance ciblée** demande la correction. Le plan
corrigé n'est conservé que s'il ne contient pas moins de tâches que l'original —
sinon on garde le premier. C'est la parade au modèle qui « corrige » en
supprimant des stories.

Enfin, export en deux fichiers : un JSON complet et un Markdown lisible.

---

## 5. Les composants du projet, un par un

Le projet tient en dix fichiers Python. Voici le rôle de chacun.

### `config.py` — le tableau de bord des réglages

**Rôle :** centraliser tous les seuils et poids, avec des valeurs par défaut
raisonnables.

**Ce qu'il contient :** la taille des passages, le nombre de passages retenus,
les poids du classement final, les pénalités, les seuils de pertinence, les
bornes de fonctionnalités, les limites de tokens, les températures du modèle, les
délais réseau, la durée du cache, la langue de sortie.

**Pourquoi c'est isolé :** pour régler le comportement sans toucher à la
logique. Chaque réglage est surchargeable par une variable d'environnement
préfixée `ORCHESTRIX_` (par exemple `ORCHESTRIX_SEUIL_PERTINENCE=0.4`).

**Dans l'architecture :** c'est la couche de configuration. Aucun autre fichier
n'écrit de nombre magique.

### `sources.py` — la collecte et le tri des documents

**Rôle :** interroger les neuf sources et décider quels documents méritent d'être
gardés (étapes ③ et ④).

**Ce qu'il contient :**

- une fonction par source (`search_github`, `search_wikipedia`, `search_owasp`…) ;
- `collect_all()` qui lance les neuf en parallèle et assemble le résultat ;
- `avec_repli()` qui réessaie avec d'autres mots si une requête ne donne rien ;
- un cache disque de 30 minutes ;
- `verifier_projets()` — l'étape ④, avec sa note et son motif de rejet ;
- les structures `Evidence` (le document) et `Verdict` (le jugement).

**Dans l'architecture :** c'est la **couche d'accès au monde extérieur**. C'est
le seul fichier qui connaît l'existence d'Internet. Si une source change son API
demain, on ne modifie que ce fichier.

### `evidence.py` — le moteur de recherche interne

**Rôle :** transformer des documents en preuves utilisables (étapes ⑤, ⑥, ⑦).

**Ce qu'il contient :**

- `chunker()` — découpe un texte en passages sans couper les phrases ;
- `BM25` — le classement par mots ;
- `VectorSearch` — le classement par proximité de sens ;
- `rrf()` — la fusion des deux classements ;
- `reranker()` — le score final pondéré avec ses pénalités ;
- `extraire_fonctionnalites()` et `extraire_exigences_transverses()` — l'étape ⑥ ;
- `valider_fonctionnalites()` — l'étape ⑦ ;
- `traiter()` — le chef d'orchestre de toute la chaîne ;
- `EvidencePack` — la boîte qui transporte le résultat.

**Dans l'architecture :** c'est le **moteur de recherche**. Il ne connaît ni
Internet, ni le modèle de langage, ni le format Jira. Il reçoit des documents et
une requête, il rend des passages classés et des preuves. C'est le composant le
plus « algorithmique » du projet.

### `agent.py` — le chef d'orchestre

**Rôle :** enchaîner les neuf étapes dans l'ordre, appeler le modèle aux bons
moments, faire respecter les règles et produire le résultat final.

**Ce qu'il contient :**

- `Orchestrix.run(brief)` — les neuf étapes, dans l'ordre, avec le journal ;
- les trois textes envoyés au modèle (analyse, génération, correction) ;
- `nettoyer()` — la fabrication de la structure Jira (clés, types, priorités,
  charges, critères) et la purge des citations invalides ;
- `valider()` — l'étape ⑨, avec ses contrôles de doublons, couverture,
  découpage et langue ;
- `_tronquer()` — la réduction des preuves pour ne jamais dépasser la taille
  maximale acceptée par le modèle ;
- `Resultat` — l'objet final (plan + preuves + métadonnées) et son export
  Markdown.

**Dans l'architecture :** c'est le **cœur logique**. Presque toutes les règles
métier du projet vivent ici : qu'est-ce qu'un bon découpage, qu'est-ce qu'une
contrainte couverte, qu'est-ce qu'un plan en français.

### `llm.py` — la seule porte vers le modèle

**Rôle :** parler à Groq, et rendre l'échec prévisible.

**Ce qu'il contient :**

- `GroqClient.chat_json()` — l'unique fonction d'appel, qui impose une réponse
  en JSON (le modèle ne peut pas répondre autre chose) ;
- la traduction des erreurs en messages utiles : clé refusée (401), requête trop
  volumineuse (413), quota atteint (429) avec attente automatique ;
- `_loads()` — trois tentatives de lecture du JSON, dont une réparation des
  virgules finales (bug rencontré sur Python 3.14).

**Dans l'architecture :** c'est la **couche d'accès au modèle**. Le reste du
projet ignore totalement que Groq existe : il appelle une fonction qui rend un
dictionnaire. Changer de fournisseur ne demanderait que ce fichier.

### `server.py` — l'interface graphique

**Rôle :** servir la page web, lancer une génération en arrière-plan, exposer le
plan.

**Ce qu'il contient :**

- un serveur HTTP écrit avec la **bibliothèque standard** de Python (aucun
  Flask, aucun Streamlit à installer) ;
- la page complète — HTML, styles et scripts — contenue dans le fichier ;
- cinq routes : la page, l'état d'avancement, le plan, l'export Markdown, et le
  lancement d'une génération ;
- un verrou qui n'autorise **qu'une génération à la fois** (le moteur n'est pas
  réentrant : cache disque et quota) ;
- la traduction des preuves et du brief anglais à l'affichage.

**Dans l'architecture :** c'est la **couche de présentation**. Elle ne contient
aucune règle métier : elle déclenche l'agent et affiche son résultat.

### `cli.py` — la ligne de commande

**Rôle :** permettre de lancer l'agent sans interface, pour un script ou un test.

**Ce qu'il contient :** les options (`--brief`, `--brief-file`, `--ui`, `--port`,
`--model`, `--out`, `--quiet`), la vérification que la clé existe, l'appel à
l'agent et l'écriture des deux fichiers de sortie.

**Dans l'architecture :** c'est la **seconde porte d'entrée**, à côté de
l'interface. Les deux appellent exactement le même agent.

### `secours.py` — le filet de sécurité

**Rôle :** permettre de continuer quand le modèle ne rend pas une analyse
utilisable.

**Ce qu'il contient :** une liste de mots de « formulation de demande » à
ignorer (« nous souhaitons développer une application… »), et un petit
dictionnaire d'équivalences français → anglais pour la recherche.

**Dans l'architecture :** c'est un **utilitaire de repli**. Il ne sert que dans
le cas dégradé, mais il évite qu'un incident sur un appel fasse échouer tout le
parcours.

### `__main__.py` et `__init__.py`

Permettent `python -m orchestrix`. Ils ne contiennent aucune logique.

---

## 6. Comment les composants s'enchaînent

```
     brief (français ou anglais)
              │
              ▼
      ┌───────────────┐
      │   cli.py      │  ou l'interface (server.py)
      └───────┬───────┘
              ▼
      ┌───────────────┐
      │   agent.py    │ ◄── config.py  (seuils et poids)
      └───┬───┬───┬───┘
          │   │   │
   [LLM]  │   │   │  [LLM]
          ▼   │   ▼
      ┌───────┐│┌──────────┐
      │ llm.py│││ agent.py │  ← fabrication Jira + validation
      └───────┘│└──────────┘
               │
               ▼
        ┌─────────────┐        ┌──────────────┐
        │ sources.py  │───────►│ evidence.py  │
        │ ③ + ④       │ docs   │ ⑤ ⑥ ⑦        │
        └─────────────┘        └──────────────┘
               │                       │
               ▼                       ▼
           Internet               12 passages + preuves
                                       │
                                       ▼
                              ⑧ plan (LLM) puis ⑨ contrôle
                                       │
                                       ▼
                              plan.json + plan.md
```

Résumé des dépendances :

- `agent.py` dépend de **tout le reste** — c'est le chef d'orchestre.
- `sources.py` et `llm.py` sont les deux seuls à parler au monde extérieur
  (Internet et Groq). On peut les remplacer sans toucher au reste.
- `evidence.py` ne dépend que de `config.py` — il est autonome et testable seul.
- `server.py` et `cli.py` dépendent d'`agent.py`, jamais l'inverse. On peut
  supprimer l'interface, l'agent continue de fonctionner en ligne de commande.

---

## 7. Exemple complet, de bout en bout

Prenons le brief :

> « Application de gestion de bibliothèque scolaire avec prêt de livres. »

### Étape ① — le modèle comprend

Il ne recopie pas la phrase. Il en tire : intention « gestion de bibliothèque »,
concepts « catalogue, prêts, adhérents, réservations, relances », utilisateurs
« élèves, bibliothécaires », et deux requêtes : *gestion bibliothèque scolaire*
et *school library management*.

Le programme retire ensuite les noms propres éventuels et les formules creuses.

### Étape ② — la requête est assemblée

Une douzaine de mots du métier, dans l'ordre d'importance : bibliothèque,
catalogue, prêt, adhérent, réservation, relance, gestion documentaire…

### Étape ③ — neuf sources répondent

Une vingtaine de documents arrivent, par exemple :

- GitHub : des logiciels de gestion de bibliothèque (Koha, Calibre…) ;
- Wikipédia : la fiche « gestion documentaire » ;
- iTunes : des applications de lecture ;
- OWASP : les dix risques de sécurité ;
- GitLab, Apache, Software Heritage, SRS : quelques documents de structure ;
- TED : souvent rien (les marchés publics de bibliothèques sont rares).

### Étape ④ — le tri

Un dépôt nommé « library » mais qui est en réalité une **bibliothèque de code
informatique** est écarté, motif « hors sujet ». Une application de gestion de
prêts de matériel est gardée : c'est analogue.

### Étape ⑤ — les douze meilleurs passages

Après découpage et classement, il reste douze passages, par exemple :

> « Importez facilement vos documents » · « Recherchez avec des filtres
> avancés » · « Enregistrez un prêt et sa date de retour » · « Relancez
> automatiquement les retards »

### Étapes ⑥ et ⑦ — les preuves

On en tire des fonctionnalités concrètes : recherche multicritère, catalogue,
prêt et retour, réservation, relance des retards, tableau de bord. Et, côté
OWASP, des exigences de sécurité : contrôle d'accès, injection, authentification.

Après nettoyage et dédoublonnage, il reste environ cinquante énoncés valides.

### Étape ⑧ — le modèle écrit le backlog

Sur un cas réel de ce type, la sortie a été de **7 épics, 22 stories, 108
tâches, 369 points**, avec près de 5 tâches par story.

Un extrait, tel qu'il apparaît dans l'interface :

> **Épic — Gestion des prêts**
> *Le cœur du métier : prêter, rendre, relancer.*
>
> **TF-2.1 · Enregistrer un prêt**
> En tant que bibliothécaire, je veux prêter un exemplaire à un adhérent, afin
> que le suivi soit fiable.
> - ☐ Le prêt est daté et rattaché à un adhérent
> - ☐ Un exemplaire déjà prêté est refusé
>
> | Clé | Tâche | Type | Priorité | Points | Preuve |
> |---|---|---|---|---|---|
> | `TF-8` | Créer le formulaire de prêt | Développement | Haute | 5 | [3] |
> | `TF-9` | Maquetter le parcours de prêt | Conception | Moyenne | 3 | — |
> | `TF-10` | Tester le cas du double prêt | Test | Moyenne | 3 | [3] |
> | `TF-11` | Rédiger la procédure de prêt | Documentation | Basse | 2 | — |

Notez que `TF-9` et `TF-11` n'ont pas de preuve : c'est normal et c'est
volontaire. Une tâche interne à l'équipe n'a pas besoin d'être justifiée par un
document externe. Mieux vaut une case vide qu'une fausse citation.

### Étape ⑨ — le contrôle

Le programme vérifie que « prêt de livres » apparaît bien dans le plan, que les
exigences de sécurité ont produit des tâches de type sécurité, qu'aucune tâche
ne cite une preuve inexistante, et que le plan est intégralement en français.

Sur ce cas réel, le bilan affiché était : **64 % des tâches sourcées**, **67 %
de couverture** des fonctionnalités demandées, **aucun doublon**.

---

## 8. Trois questions fréquentes

**« Où sont les données ? »**
Nulle part : rien n'est stocké, à part un cache temporaire de 30 minutes sur les
documents collectés. Chaque exécution repart de zéro.

**« Est-ce que le plan est le même à chaque fois ? »**
La **structure** oui — clés, types, priorités, estimations, découpage découlent
du contenu et des règles, pas du hasard. La **formulation** varie, car elle est
écrite par le modèle.

**« Que se passe-t-il si Internet tombe ? »**
La collecte revient vide, le plan est produit uniquement à partir du brief, et
un avertissement visible l'indique en haut du backlog. Le projet préfère un plan
signalé comme non ancré à un plan qui ferait semblant d'être sourcé.

---

## 9. Ce qu'il faut retenir en une page

1. Le **modèle** comprend et rédige ; le **programme** cherche, trie, classe,
   numérote et vérifie. Tout ce qui est vérifiable est confié au programme.
2. Le parcours a **neuf étapes** dans un ordre fixe, dont deux appels au modèle.
3. Le filtrage des documents se fait **avant** le traitement coûteux.
4. La recherche est **hybride** : par mots, par proximité de sens, fusion, puis
   reclassement pondéré.
5. La structure Jira — clés, types, priorités, estimations — est **fabriquée par
   le code**, jamais dictée par le modèle.
6. Une preuve qui n'existe pas est **supprimée par le code**, pas corrigée par
   le modèle.
7. Le résultat est un **backlog** épics → stories → tâches, exportable en JSON
   et en Markdown, consultable dans une interface web qui ne demande aucune
   installation supplémentaire.

## Où passe le temps d'une génération

Une génération enchaîne quelques appels à l'API Groq ; chacun coûte selon le
nombre de jetons produits. Trois réglages expliquent l'essentiel :

| Réglage | Valeur | Effet |
|---|---|---|
| `MAX_TOKENS_PLAN` | 16000 | longueur maximale du plan ; c'est le poste principal |
| `PREUVES_TRADUITES_IMMEDIAT` | 12 | citations traduites avant l'affichage ; le reste suit en tâche de fond |
| `TIMEOUT_SOURCE` | 14 s | plafond par source ; les 9 sources sont interrogées en parallèle |

Le temps de réseau des sources est négligeable (moins d'une seconde au total).
Le coût réel est la rédaction du plan : environ 300 jetons par seconde, soit
20 à 40 secondes pour un plan complet. L'interface affiche ce compteur en
direct plutôt qu'un sablier, et le plan s'affiche dès qu'il est écrit.
