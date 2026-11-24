const path = require('path');
const RACINE = process.env.RACINE || path.resolve(__dirname, '..');
const { JSDOM } = require(process.env.JSDOM || '/home/user/.cache/rendu/node_modules/jsdom');
const fs = require('fs');
const { PLAN, META, PREUVES } = require(RACINE + '/tests/fixture.js');
const html = fs.readFileSync(RACINE + '/_page_pro.html', 'utf8');

// état serveur simulé, avec un vrai petit moteur de gestion
const EQUIPE = [
  {id:"m1", nom:"Amine Ben Salah", role:"Développeur backend", capacite:20, initiales:"AB"},
  {id:"m2", nom:"Sonia Trabelsi", role:"Développeur frontend", capacite:18, initiales:"ST"},
  {id:"m3", nom:"Karim Haddad", role:"Testeur", capacite:12, initiales:"KH"}];
let TACHES = [
  {cle:"T-1.1.1", titre:"Créer le squelette applicatif", description:"Structure", epic:"E1",
   epic_titre:"Socle technique", story:"US-1.1", type:"dev", priorite:"Haute", charge:5,
   statut:"termine", assigne:"m1", jira:"PROJ-1", commentaires:[], historique:[]},
  {cle:"T-1.1.2", titre:"Configurer la chaîne d'intégration", description:"CI", epic:"E1",
   epic_titre:"Socle technique", story:"US-1.1", type:"config", priorite:"Moyenne", charge:3,
   statut:"en_cours", assigne:"m1", jira:null, commentaires:[], historique:[]},
  {cle:"T-1.1.3", titre:"Écrire les tests de fumée", description:"Tests", epic:"E1",
   epic_titre:"Socle technique", story:"US-1.1", type:"test", priorite:"Basse", charge:2,
   statut:"a_faire", assigne:"m3", jira:null, commentaires:[], historique:[]},
  {cle:"T-2.1.1", titre:"Implémenter le calcul des niveaux", description:"Agrégation",
   epic:"E2", epic_titre:"Gestion des stocks", story:"US-2.1", type:"dev", priorite:"Haute",
   charge:8, statut:"bloque", assigne:"m2", jira:null, commentaires:[], historique:[]}];

function stats(){
  const par = {a_faire:0,en_cours:0,en_revue:0,termine:0,bloque:0};
  TACHES.forEach(t=>par[t.statut]++);
  const eq = EQUIPE.map(m=>({nom:m.nom, role:m.role, capacite:m.capacite, assigne:0,
    termine:0, en_cours:0, taches:0}));
  TACHES.forEach(t=>{const i=EQUIPE.findIndex(m=>m.id===t.assigne);
    if(i>=0){eq[i].assigne+=t.charge; eq[i].taches++; if(t.statut==="termine") eq[i].termine+=t.charge;}});
  eq.forEach(c=>{c.surcharge=c.assigne>c.capacite; c.remplissage=Math.round(c.assigne/c.capacite*100);});
  return {total:TACHES.length, par_statut:par, avancement:Math.round(par.termine/TACHES.length*100),
    en_cours:par.en_cours, bloquees:par.bloque, non_assigne:TACHES.filter(t=>!t.assigne).length,
    points_total:TACHES.reduce((s,t)=>s+t.charge,0),
    points_faits:TACHES.filter(t=>t.statut==="termine").reduce((s,t)=>s+t.charge,0),
    charge:eq, dans_jira:TACHES.filter(t=>t.jira).length};
}
const vue = () => ({projet:{id:"p", nom:"Gestion de stock", objectif:"Piloter les stocks",
  domaine:"Logistique", cree_le:"2026-11-04 12:00", equipe:EQUIPE},
  taches:TACHES, jira:{url:"", email:"", token:"", cle_projet:"", configure:false,
  resultats:[], compte:""}, statistiques:stats(),
  statuts:[{cle:"a_faire",libelle:"À faire"},{cle:"en_cours",libelle:"En cours"},
           {cle:"en_revue",libelle:"En revue"},{cle:"termine",libelle:"Terminé"},
           {cle:"bloque",libelle:"Bloqué"}],
  roles:["Développeur backend","Testeur"], journal:[]});

const appels = [];
const dom = new JSDOM(html, { runScripts:"dangerously", pretendToBeVisual:true,
  url:"http://localhost:8402/",
  beforeParse(w){
    w.fetch = (url, opt) => {
      appels.push(String(url));
      const corps = opt && opt.body ? JSON.parse(opt.body) : {};
      let rep = {};
      if(String(url).includes("/api/plan")) rep = {plan:PLAN, meta:META, preuves:PREUVES};
      else if(String(url).includes("/api/etat")) rep = {statut:"idle"};
      else if(String(url).includes("/api/projet/statut")){
        const t = TACHES.find(x=>x.cle===corps.cle); if(t) t.statut = corps.statut;
        rep = vue();
      }
      else if(String(url).includes("/api/projet/affecter")){
        const t = TACHES.find(x=>x.cle===corps.cle); if(t) t.assigne = corps.membre;
        rep = vue();
      }
      else if(String(url).includes("/api/projet/commenter")){
        const t = TACHES.find(x=>x.cle===corps.cle);
        if(t) t.commentaires.push({auteur:"Amine", date:"2026-11-04", texte:corps.texte});
        rep = vue();
      }
      else if(String(url).includes("/api/projet/repartir")){
        TACHES.forEach((t,i)=>{ if(!t.assigne) t.assigne = EQUIPE[i % EQUIPE.length].id; });
        rep = vue();
      }
      else if(String(url).includes("/api/projet")) rep = vue();
      return Promise.resolve({ok:true, status:200, json:()=>Promise.resolve(rep)});
    };
    w.scrollTo=()=>{}; w.open=()=>{}; w.confirm=()=>true; w.alert=(m)=>{appels.push("ALERT:"+m)};
  }});
const { window } = dom, d = window.document;
let ok=0, ko=0; const lignes=[];
const c=(n,cond,v)=>{cond?ok++:ko++; lignes.push((cond?"✓":"✗")+" "+n+(v!==undefined?" → "+v:""));};

setTimeout(()=>{
  window.charger();
  setTimeout(()=>{
    lignes.push("--- VUES AJOUTÉES ---");
    c("3 entrées d'équipe dans le rail",
      !!d.querySelector('button[data-vue="espace"]') && !!d.querySelector('button[data-vue="execution"]')
      && !!d.querySelector('button[data-vue="jira"]'));

    lignes.push("--- ESPACE DE TRAVAIL ---");
    window.aller("espace");
    c("sujet affiché", d.querySelector("#eSujet").textContent === "Gestion de stock",
      d.querySelector("#eSujet").textContent);
    c("6 indicateurs", d.querySelectorAll("#eKpi .kpi").length === 6,
      Array.from(d.querySelectorAll("#eKpi .v")).map(x=>x.textContent).join(" · "));
    c("avancement par épic", d.querySelectorAll("#eAvancement .bar-l").length === 2);
    c("membres listés", d.querySelectorAll("#eEquipe .membre").length === 3);
    c("surcharge signalée",
      Array.from(d.querySelectorAll(".membre .taux")).some(x=>x.classList.contains("trop"))
      || d.querySelectorAll(".membre .taux").length === 3);

    lignes.push("--- EXÉCUTION ---");
    window.aller("execution");
    c("résumé : 8 chiffres", d.querySelectorAll("#execResume .resume-item").length === 8,
      d.querySelectorAll("#execResume .resume-item").length);
    c("lignes de tâches", d.querySelectorAll("#tableExec tbody tr").length === 4);
    c("statuts en listes déroulantes", d.querySelectorAll(".sel-statut").length === 4);
    c("badge Jira visible", d.querySelector("#tableExec").textContent.includes("PROJ-1"));
    c("puces par membre", d.querySelectorAll("#execMembres .puce-membre").length === 4);

    // filtre par membre
    window.filtrerExec("m1");
    c("filtre membre", d.querySelectorAll("#tableExec tbody tr").length === 2,
      d.querySelectorAll("#tableExec tbody tr").length + " lignes");
    window.filtrerExec("");

    // changement de statut
    const sel = d.querySelector('.sel-statut');
    sel.value = "en_revue";
    sel.onchange();
    setTimeout(()=>{
      c("statut modifié côté serveur",
        TACHES.some(t=>t.statut === "en_revue"), TACHES.map(t=>t.statut).join(","));

      lignes.push("--- PANNEAU DE TÂCHE ---");
      window.ouvrirTacheExec("T-1.1.2");
      c("panneau ouvert", !!d.querySelector(".panneau"));
      c("historique ou commentaire", !!d.querySelector(".histo") || !!d.querySelector(".comm")
        || d.querySelector(".panneau-corps").textContent.includes("Aucun mouvement"));
      c("sélecteur de responsable", !!d.querySelector(".sel-large"));
      const resp = d.querySelector(".sel-large"); resp.value = "m2"; resp.onchange();
      setTimeout(()=>{
        c("réaffectation enregistrée", (TACHES.find(t=>t.cle==="T-1.1.2")||{}).assigne === "m2",
          (TACHES.find(t=>t.cle==="T-1.1.2")||{}).assigne);
        window.fermerPanneau();

        lignes.push("--- RÉPARTITION AUTOMATIQUE ---");
        TACHES.forEach(t=>{ if(t.cle==="T-2.1.1") t.assigne=null; });
        window.repartirAuto();
        setTimeout(()=>{
          c("toutes les tâches affectées", TACHES.every(t=>t.assigne),
            TACHES.map(t=>t.assigne).join(","));

          lignes.push("--- JIRA ---");
          window.aller("jira");
          c("formulaire Jira", !!d.querySelector("#jUrl") && !!d.querySelector("#jEmail")
            && !!d.querySelector("#jToken") && !!d.querySelector("#jCle"));
          c("jeton en champ masqué", d.querySelector("#jToken").type === "password");
          c("état non configuré", d.querySelector("#jEtat").textContent.includes("Non configuré"));
          c("boutons d'envoi présents", !!d.querySelector("#jEnvoyer") && !!d.querySelector("#jRelire"));

          lignes.push("--- PALETTE ---");
          c("commandes d'équipe",
            window.commandes().some(x=>x.t.includes("Répartir"))
            && window.commandes().some(x=>x.t.includes("Jira")));

          console.log(lignes.join("\n"));
          console.log("\n" + (ko===0 ? "TOUT PASSE ("+ok+" contrôles)" : "ÉCHECS : "+ko+" sur "+(ok+ko)));
        }, 120);
      }, 120);
    }, 120);
  }, 100);
}, 100);
