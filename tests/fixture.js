/* Fixture partagée par les tests d'interface : un plan cohérent (77 points). */
const PLAN = { epics: [
 { title:"Socle technique et socle de données", description:"Infrastructure, schéma de données, déploiement continu.", points:18, stories:[
   { cle:"US-1.1", title:"Initialiser le produit et son dépôt", as_a:"développeur", i_want:"un dépôt fonctionnel avec intégration continue", so_that:"livrer sans régression",
     acceptance:["La chaîne d'intégration s'exécute à chaque envoi","Le déploiement de recette est automatique"],
     tasks:[
      { cle:"T-1.1.1", title:"Créer le squelette applicatif", description:"Structure, configuration, journalisation.", type:"dev", priorite:"Haute", charge:5, sources:[1,2] },
      { cle:"T-1.1.2", title:"Configurer la chaîne d'intégration", description:"Tests et analyse statique.", type:"config", priorite:"Moyenne", charge:3, sources:[3] },
      { cle:"T-1.1.3", title:"Écrire les tests de fumée", description:"Démarrage et connexion.", type:"test", priorite:"Basse", charge:2, sources:[] }]},
   { cle:"US-1.2", title:"Modéliser le schéma de données", as_a:"architecte", i_want:"un modèle validé", so_that:"garantir la cohérence",
     acceptance:["Le schéma couvre les lots"], tasks:[
      { cle:"T-1.2.1", title:"Concevoir le modèle physique", description:"Tables et index.", type:"design", priorite:"Haute", charge:5, sources:[1] },
      { cle:"T-1.2.2", title:"Documenter le dictionnaire de données", description:"Champs et règles.", type:"doc", priorite:"Moyenne", charge:3, sources:[2] }]}]},
 { title:"Gestion des stocks et des mouvements", description:"Cœur métier : réception, sortie, transfert.", points:24, stories:[
   { cle:"US-2.1", title:"Suivre les niveaux de stock en temps réel", as_a:"gestionnaire de stock", i_want:"consulter les quantités par emplacement", so_that:"anticiper les ruptures",
     acceptance:["Niveau à jour à moins d'une minute","Mouvements historisés"],
     tasks:[
      { cle:"T-2.1.1", title:"Implémenter le calcul des niveaux", description:"Agrégation des mouvements.", type:"dev", priorite:"Haute", charge:8, sources:[1,4] },
      { cle:"T-2.1.2", title:"Créer l'écran de consultation", description:"Liste filtrable et export.", type:"dev", priorite:"Haute", charge:5, sources:[2] },
      { cle:"T-2.1.3", title:"Tester les cas de stock négatif", description:"Mouvements concurrents.", type:"test", priorite:"Moyenne", charge:3, sources:[] }]},
   { cle:"US-2.2", title:"Déclencher des alertes de rupture", as_a:"responsable achats", i_want:"être alerté sous un seuil", so_that:"commander à temps",
     acceptance:["Seuil paramétrable par article"], tasks:[
      { cle:"T-2.2.1", title:"Implémenter le moteur de seuils", description:"Évaluation périodique.", type:"dev", priorite:"Haute", charge:5, sources:[5] },
      { cle:"T-2.2.2", title:"Sécuriser l'accès aux alertes", description:"Restriction par rôle.", type:"securite", priorite:"Moyenne", charge:3, sources:[3] }]}]},
 { title:"Inventaires et traçabilité des lots", description:"Comptage périodique et conformité.", points:13, stories:[
   { cle:"US-3.1", title:"Réaliser un inventaire périodique", as_a:"gestionnaire de stock", i_want:"saisir les comptages", so_that:"corriger les dérives",
     acceptance:["Reprise après interruption"], tasks:[
      { cle:"T-3.1.1", title:"Implémenter la saisie d'inventaire", description:"Mode hors ligne.", type:"dev", priorite:"Haute", charge:8, sources:[6] },
      { cle:"T-3.1.2", title:"Calculer et afficher les écarts", description:"Comparaison théorique et réel.", type:"dev", priorite:"Moyenne", charge:3, sources:[] }]},
   { cle:"US-3.2", title:"Tracer les lots jusqu'à la réception", as_a:"responsable qualité", i_want:"retrouver l'origine d'un lot", so_that:"répondre à un contrôle",
     acceptance:["Remontée jusqu'au fournisseur"], tasks:[
      { cle:"T-3.2.1", title:"Ajouter les métadonnées de lot", description:"Numéro, date, fournisseur.", type:"dev", priorite:"Haute", charge:2, sources:[1] }]}]},
 { title:"Tableau de bord et pilotage", description:"Indicateurs de rotation.", points:8, stories:[
   { cle:"US-4.1", title:"Visualiser les indicateurs clés", as_a:"directeur des opérations", i_want:"un tableau de bord", so_that:"arbitrer les achats",
     acceptance:["Trente jours glissants"], tasks:[
      { cle:"T-4.1.1", title:"Construire les requêtes d'agrégation", description:"Rotation et valeur.", type:"dev", priorite:"Moyenne", charge:5, sources:[6] },
      { cle:"T-4.1.2", title:"Réaliser les graphiques du tableau de bord", description:"Courbes de rotation.", type:"dev", priorite:"Moyenne", charge:3, sources:[] }]}]},
 { title:"Mise en production et exploitation", description:"Sécurité et documentation.", points:9, stories:[
   { cle:"US-5.1", title:"Exploiter la plateforme sereinement", as_a:"administrateur", i_want:"des sauvegardes et une supervision", so_that:"garantir la disponibilité",
     acceptance:["Restauration testée chaque mois"], tasks:[
      { cle:"T-5.1.1", title:"Mettre en place les sauvegardes", description:"Quotidiennes et chiffrées.", type:"config", priorite:"Haute", charge:3, sources:[2] },
      { cle:"T-5.1.2", title:"Rédiger le guide d'exploitation", description:"Procédures d'incident.", type:"doc", priorite:"Moyenne", charge:3, sources:[] },
      { cle:"T-5.1.3", title:"Vérifier la conformité des accès", description:"Revue des rôles.", type:"securite", priorite:"Moyenne", charge:3, sources:[3] }]}]}]};

const META = { brief:"Gestion de stock pour PME agroalimentaire", date:"2026-11-09 10:12",
  modele:"openai/gpt-oss-120b",
  analyse:{ sujet:"Gestion de stock pour PME agroalimentaire",
    objectif:"Piloter les niveaux de stock, anticiper les ruptures et fiabiliser les inventaires d'un site de production agroalimentaire.",
    domaine:"Agroalimentaire",
    utilisateurs:["gestionnaire de stock","responsable achats","responsable qualité"],
    contraintes:["usage en atelier hors ligne","traçabilité des lots"],
    concepts:["niveau de stock","rotation","seuil d'alerte"],
    fonctionnalites:["suivi temps réel","alertes de rupture","inventaire avec écarts","traçabilité des lots","tableau de bord"] },
  qualite:{ epics:5, stories:8, taches:18, points:77, taux_ancrage:0.84, couverture:0.80 },
  pipeline:{ documents:14, passages:96, passages_retenus:24, fonctions_brutes:11, fonctionnalites:5 },
  sources_collectees:{ GitHub:{n:9}, OpenAlex:{n:3}, Wikipédia:{n:2}, Zenodo:{n:0, erreur:"rien trouvé"} },
  verdicts_projets:[{titre:"Tableur générique", source:"GitHub", score:0.18, motif:"aucune notion de lot", retenu:false},
                    {titre:"Article gestion industrielle", source:"OpenAlex", score:0.24, motif:"hors périmètre", retenu:false}],
  avertissements:["deux tâches de documentation portent des intitulés proches"],
  categories_fonctionnalites:{ Stock:2, Alertes:1, Traçabilité:1, Pilotage:1 } };

const PREUVES = [
 {texte:"Le suivi de stock permet d'anticiper les ruptures.", document:"Référentiel logistique", url:"https://ex.org/1", type:"exigence"},
 {texte:"La traçabilité des lots est exigée.", document:"Guide qualité", url:"https://ex.org/2", type:"exigence"},
 {texte:"Un inventaire compare stock théorique et physique.", document:"Fiche pratique", url:"https://ex.org/3", type:"fonctionnalite"},
 {texte:"Le taux de rotation mesure le renouvellement du stock.", document:"Définition", url:"https://ex.org/4", type:"extrait"},
 {texte:"Une alerte est émise sous le seuil configuré.", document:"Spécification", url:"https://ex.org/5", type:"fonctionnalite"},
 {texte:"Le coût de possession agrège immobilisation et obsolescence.", document:"Analyse", url:"https://ex.org/6", type:"extrait"}];

/* plan dégradé : sert à éprouver le registre des risques */
const PLAN_DEGRADE = JSON.parse(JSON.stringify(PLAN));
PLAN_DEGRADE.epics.forEach((e, i) => {
  e.stories.forEach((s, j) => {
    if(i > 0 || j > 0) s.acceptance = [];
    s.tasks.forEach(t => {
      if(t.type !== "dev") t.type = "dev";
      if(t.charge < 8) t.charge = 8;
      t.sources = [];
    });
  });
});
PLAN_DEGRADE.epics[0].stories[0].tasks[0].sources = [1];

module.exports = {PLAN, META, PREUVES, PLAN_DEGRADE};
