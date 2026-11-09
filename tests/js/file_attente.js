/* Exécute le vrai static/js/hors_ligne.js dans Node, avec un téléphone simulé (base IndexedDB en mémoire,
 * réseau simulé), et dit ce qui reste sur le téléphone après l'envoi d'une inscription faite sans réseau.
 * Usage : node file_attente.js <chemin de hors_ligne.js> <réponse du serveur : ok|deja|refuse|connexion|coupure>
 * Sortie (JSON) : {envoye: bool, mot_de_passe_envoye: bool, reste: [entrées encore sur le téléphone]} */
'use strict';
const fs = require('fs');
const vm = require('vm');
const [chemin, scenario] = process.argv.slice(2);

const magasin = new Map();
const MDP = 'k7mq2wpa9x';
magasin.set('a1', {
  id: 'a1', utilisateur: 'agent.est', url: '/fermes/EST-003/eleveurs/nouveau', libelle: 'Nouvel éleveur · Ferme Nzé',
  horodatage: new Date().toISOString(),
  entrees: [['nom', 'Ndong'], ['prenom', 'Rose'], ['telephone', '066112233'], ['identifiant', 'rose.ndong'],
            ['provisoire', MDP]]
});

const indexedDB = {
  open() {
    const r = {};
    setTimeout(() => {
      r.result = {
        transaction() {
          const t = {};
          const store = {
            getAll() { return {result: [...magasin.values()].map((e) => JSON.parse(JSON.stringify(e)))}; },
            put(v) { magasin.set(v.id, JSON.parse(JSON.stringify(v))); },
            delete(id) { magasin.delete(id); },
          };
          t.objectStore = () => store;
          setTimeout(() => t.oncomplete && t.oncomplete(), 0);
          return t;
        },
      };
      r.onsuccess && r.onsuccess();
    }, 0);
    return r;
  },
};

class FormData {
  constructor() { this.champs = []; }
  append(n, v) { this.champs.push([n, v]); }
}

let envoye = false, motDePasseEnvoye = false;
function fetch(url, opts) {
  if (url === '/hors-ligne/jeton') return Promise.resolve({ok: true, json: () => Promise.resolve({etat: 'ok', jeton: 'j'})});
  if (opts && opts.method === 'POST') {
    if (scenario === 'coupure') return Promise.reject(new Error('réseau'));
    envoye = true;
    motDePasseEnvoye = opts.body.champs.some(([n, v]) => n === 'provisoire' && v === MDP);
    return Promise.resolve({json: () => Promise.resolve({etat: scenario, message: 'x'})});
  }
  return Promise.resolve({ok: false, json: () => Promise.resolve({})});
}

const element = () => ({className: '', hidden: true, innerHTML: '', textContent: '', setAttribute() {}, remove() {}});
const corps = {
  getAttribute: (k) => (k === 'data-utilisateur' ? 'agent.est' : null), hasAttribute: () => false,
  classList: {contains: () => false}, insertBefore() {}, firstChild: null,
};
const contexte = {
  document: {body: corps, querySelector: () => null, createElement: element, addEventListener() {}},
  navigator: {onLine: true, serviceWorker: {controller: null, addEventListener() {},
                                            register: () => Promise.resolve({update: () => Promise.resolve()})}},
  location: {pathname: '/fermes/EST-003', href: ''},
  indexedDB, fetch, FormData, File: class {}, console, Promise, JSON, Date, encodeURIComponent,
  crypto: {randomUUID: () => 'u'}, localStorage: {getItem: () => 'tel', setItem() {}},
  sessionStorage: {getItem: () => null, setItem() {}},
  setTimeout, setInterval: () => 0,
};
contexte.window = Object.assign(contexte, {isSecureContext: true, addEventListener() {}});
vm.runInNewContext(fs.readFileSync(chemin, 'utf-8'), contexte);
setTimeout(() => {
  process.stdout.write(JSON.stringify({envoye, mot_de_passe_envoye: motDePasseEnvoye, reste: [...magasin.values()]}));
}, 300);
