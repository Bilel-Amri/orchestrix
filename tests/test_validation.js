const path = require('path');
const RACINE = process.env.RACINE || path.resolve(__dirname, '..');
const { JSDOM } = require(process.env.JSDOM || '/home/user/.cache/rendu/node_modules/jsdom');
const fs = require('fs');
const f = require(RACINE + '/tests/fixture.js');
const html = fs.readFileSync(RACINE + '/_page_pro.html', 'utf8');

let VALID = {statut:"aucune", motif:"", date:"", auteur:"", historique:[]};
let EQUIPE = [{id:"m1", nom:"Amine", role:"Développeur backend", capacite:20, initiales:"AB"},
              {id:"m2", nom:"Karim", role:"Testeur", capacite:15, initiales:"KH"}];
let TACHES = [{cle:"T1", titre:"Faire", description:"d", epic:"E1", epic_titre:"Socle",
  story:"US-1", type:"dev", priorite:"Haute", charge:5, statut:"a_faire", assigne:null,
  jira:null, commentaires:[], historique:[]}];
const appels = [];
function vue(){
  return {projet:{id:"p", nom:"Test", objectif:"o", domaine:"d", cree_le:"2026-11-04", equipe:EQUIPE},
    validation:VALID, taches:TACHES,
    jira:{configure:false, resultats:[], token:""},
    statistiques:{total:TACHES.length, par_statut:{a_faire:1,en_cours:0,en_revue:0,termine:0,bloque:0},
      avancement:0, en_cours:0, bloquees:0, non_assigne:TACHES.filter(t=>!t.assigne).length,
      points_total:5, points_faits:0,
      charge:EQUIPE.map(m=>({nom:m.nom,role:m.role,capacite:m.capacite,assigne:0,
        termine:0,en_cours:0,taches:0,surcharge:false,remplissage:0})), dans_jira:0},
    statuts:[{cle:"a_faire",libelle:"À faire"}],
    roles:["Développeur backend","Testeur"], journal:[]};
}
const dom = new JSDOM(html, { runScripts:"dangerously", pretendToBeVisual:true,
  url:"http://localhost:8402/",
  beforeParse(w){
    w.fetch = (url, opt) => {
      const u = String(url), corps = opt && opt.body ? JSON.parse(opt.body) : {};
      appels.push(u + (opt && opt.body ? " " + opt.body : ""));
      if(u.includes("/api/plan")) return Promise.resolve({ok:true, json:()=>Promise.resolve(
        {plan:f.PLAN, meta:f.META, preuves:f.PREUVES})});
      if(u.includes("/api/etat")) return Promise.resolve({ok:true, json:()=>Promise.resolve({statut:"idle"})});
      if(u.includes("/api/reglages")) return Promise.resolve({ok:true, json:()=>Promise.resolve(
        {cle_presente:true, source:"fichier local", modele:"m"})});
      if(u.includes("/api/projet/soumettre")){ VALID = Object.assign({}, VALID,
        {statut:"en_attente", historique:[{statut:"en_attente"}]}); }
      if(u.includes("/api/projet/approuver")){ VALID = Object.assign({}, VALID,
        {statut:"approuve", date:"2026-11-04 12:00", auteur:"chef"}); }
      if(u.includes("/api/projet/rejeter")){ VALID = Object.assign({}, VALID,
        {statut:"rejete", motif:corps.motif, date:"2026-11-04 12:01"}); }
      if(u.includes("/api/generer")){ appels.push("GENERER motif=" + (corps.motif || "")); }
      return Promise.resolve({ok:true, status:200, json:()=>Promise.resolve(vue())});
    };
    w.scrollTo=()=>{}; w.open=()=>{}; w.confirm=()=>true;
    w.alert = m => appels.push("ALERT:" + m);
  }});
const w = dom.window, d = w.document;
let ok=0, ko=0; const L=[];
const c=(n,cond,v)=>{cond?ok++:ko++; L.push((cond?"✓":"✗")+" "+n+(v!==undefined?" → "+v:""));};

setTimeout(()=>{
  w.charger();
  setTimeout(()=>{
    L.push("--- BANDEAU DE VALIDATION ---");
    c("bandeau présent", !!d.querySelector(".bandeau-validation"));
    c("statut non soumis", d.querySelector(".bandeau-validation").textContent.includes("Non soumis"));
    c("bouton soumettre", d.querySelector(".bandeau-validation").textContent.includes("Soumettre"));

    L.push("--- SOUMISSION ---");
    w.soumettrePlan();
    setTimeout(()=>{
      c("passé en attente", d.querySelector(".bandeau-validation").textContent.includes("En attente"));
      c("bouton approuver visible", d.querySelector(".bandeau-validation").textContent.includes("Approuver le plan"));

      L.push("--- APPROBATION ---");
      w.approuverDirect();
      setTimeout(()=>{
        c("approuvé", d.querySelector(".bandeau-validation").textContent.includes("Plan approuvé"));
        c("lien vers exécution", d.querySelector(".bandeau-validation").textContent.includes("exécution"));

        L.push("--- REJET ---");
        VALID = {statut:"en_attente", motif:"", date:"", auteur:"", historique:[]};
        w.rendreValidation();
        w.basculerMotif();
        c("zone de motif ouverte", !d.querySelector("#zoneMotif").classList.contains("cache"));
        d.querySelector("#motifRejet").value = "court";
        w.rejeterPlan();
        setTimeout(()=>{
          c("motif trop court refusé", appels.some(a=>a.startsWith("ALERT:Expliquez")),
            appels.filter(a=>a.startsWith("ALERT")).length + " alerte(s)");
          w.basculerMotif();
          d.querySelector("#motifRejet").value = "il manque la partie facturation et les rôles";
          w.rejeterPlan();
          setTimeout(()=>{
            c("rejet envoyé", appels.some(a=>a.includes("/api/projet/rejeter")
              && a.includes("facturation")));
            c("régénération demandée avec le motif",
              appels.some(a=>a.startsWith("GENERER motif=il manque la partie facturation")));

            L.push("--- LIENS ENTRE PAGES ---");
            c("liens croisés présents", d.querySelectorAll(".lien-page").length >= 6,
              d.querySelectorAll(".lien-page").length + " liens");
            w.aller("planification");
            const avant = Array.from(d.querySelectorAll("section[id^='vue-']"))
              .filter(x=>!x.classList.contains("cache")).map(x=>x.id).join(",");
            d.querySelector("#vue-plan .lien-page").onclick &&
              d.querySelector("#vue-plan .lien-page").onclick();
            c("changement de page via lien", avant === "vue-planification");

            L.push("--- MODE PRÉSENTATION ---");
            w.basculerPresentation();
            c("mode présentation actif", d.body.classList.contains("presentation"));
            c("libellé du bouton", d.querySelector("#btnPresentation").textContent.trim(),
              d.querySelector("#btnPresentation").textContent.trim());
            w.basculerPresentation();
            c("retour au mode normal", !d.body.classList.contains("presentation"));

            L.push("--- AFFECTATION JUSTIFIÉE ---");
            c("commande palette d'affectation",
              w.commandes().some(x=>x.t.includes("Répartir")));

            clearInterval(w.MINUTEUR);
            console.log(L.join("\n"));
            console.log("\n" + (ko===0 ? "TOUT PASSE ("+ok+" contrôles)" : "ÉCHECS : "+ko+" sur "+(ok+ko)));
          }, 150);
        }, 150);
      }, 150);
    }, 150);
  }, 200);
  setTimeout(() => process.exit(0), 12000);
}, 150);
