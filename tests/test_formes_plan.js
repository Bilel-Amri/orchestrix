const path = require('path');
const RACINE = process.env.RACINE || path.resolve(__dirname, '..');
/* Le plan reçu contient toutes les formes dégradées que le modèle peut produire. */
const { JSDOM } = require(process.env.JSDOM || '/home/user/.cache/rendu/node_modules/jsdom');
const fs = require('fs');
const f = require(RACINE + '/tests/fixture.js');
const html = fs.readFileSync(RACINE + '/_page_pro.html', 'utf8');

const formes = {
  "phrases au lieu de listes": m => { m.analyse.utilisateurs = "les gestionnaires de stock, les responsables achats";
                                      m.analyse.fonctionnalites = "suivi temps réel; alertes de rupture";
                                      m.analyse.contraintes = "traçabilité des lots et usage hors ligne"; },
  "chaîne vide":               m => { m.analyse.utilisateurs = ""; m.analyse.concepts = null; },
  "objet au lieu de liste":    m => { m.analyse.utilisateurs = {a:"gestionnaire", b:"acheteur"};
                                      m.analyse.fonctionnalites = {1:"alerte"}; },
  "nombres dans les listes":   m => { m.analyse.concepts = [1, 2, 3]; },
  "avertissements en texte":   m => { m.avertissements = "un seul avertissement"; },
  "tout absent":               m => { delete m.analyse.utilisateurs; delete m.analyse.fonctionnalites;
                                      delete m.analyse.contraintes; delete m.analyse.concepts;
                                      delete m.avertissements; delete m.qualite; },
};

let ok = 0, ko = 0;
for(const [nom, degrade] of Object.entries(formes)){
  const META = JSON.parse(JSON.stringify(f.META));
  degrade(META);
  let erreurs = [];
  const dom = new JSDOM(html, { runScripts:"dangerously", pretendToBeVisual:true,
    url:"http://localhost:8402/",
    beforeParse(w){
      w.fetch = u => Promise.resolve({ok:true, json:()=>Promise.resolve(
        String(u).includes('/api/plan') ? {plan:f.PLAN, meta:META, preuves:f.PREUVES}
        : String(u).includes('/api/reglages') ? {cle_presente:true, source:"fichier local", modele:"test"}
        : String(u).includes('/api/projet') ? {projet:null,taches:[],jira:{configure:false,resultats:[],token:''},statistiques:{},statuts:[],roles:[],journal:[]}
        : {statut:"idle"})});
      w.scrollTo=()=>{}; w.open=()=>{}; w.confirm=()=>true;
    }});
  const w = dom.window;
  w.addEventListener("error", e => erreurs.push(e.message));
  const originalError = w.console.error;
  w.console.error = (...a) => { erreurs.push(a.map(String).join(" ")); };
  setTimeout(() => {
    w.charger();
    setTimeout(() => {
      const d = w.document;
      const affiche = !d.querySelector('#vue-plan').classList.contains('cache');
      const sujet = d.querySelector('#sujetProjet').textContent;
      const kpi = d.querySelectorAll('#kpis .kpi').length;
      const alerteAffichage = d.querySelector('#zoneAvert .alerte.erreur');
      const bon = affiche && sujet.length > 3 && kpi === 7 && !alerteAffichage && erreurs.length === 0;
      bon ? ok++ : ko++;
      console.log((bon ? "✓" : "✗"), nom,
        "→ vue:" + (affiche ? "ok" : "KO"), "kpi:" + kpi,
        alerteAffichage ? "· panne signalée" : "",
        erreurs.length ? "· erreurs: " + erreurs.slice(0,2).join(" | ") : "");
      if(nom === "tout absent"){
        console.log("   contenu cadrage :", d.querySelector('#propsCadrage').textContent.trim().slice(0,60) || "(vide)");
      }
      w.close();
    }, 220);
  }, 120);
}
setTimeout(() => {
  console.log("\n" + (ko === 0 ? "TOUT PASSE (" + ok + " formes)" : "ÉCHECS : " + ko));
}, 3000);
