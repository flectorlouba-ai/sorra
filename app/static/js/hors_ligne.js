/* SORRA — saisies sans réseau (voir docs/hors_ligne.md).
 *
 * Actif seulement en HTTPS ou sur l'ordinateur lui-même (le navigateur l'exige) ;
 * ailleurs le site marche comme avant, sans rien garder sur le téléphone.
 *
 * Un formulaire marqué data-hors-ligne="libellé" :
 *  - avec du réseau : il part normalement ;
 *  - sans réseau : la saisie est gardée sur le téléphone (◷), puis envoyée dès le
 *    retour du réseau (✓), avec un identifiant unique qui empêche tout doublon.
 */
(function () {
  'use strict';
  var corps = document.body;
  var utilisateur = corps && corps.getAttribute('data-utilisateur');
  if (!utilisateur || !window.isSecureContext || !('serviceWorker' in navigator) || !window.indexedDB) return;

  navigator.serviceWorker.register('/sw.js', {scope: '/'}).catch(function () {});

  // ── Rangement sur le téléphone (IndexedDB) ──────────────────────────
  var BASE = 'performyl2', MAGASIN = 'attente';
  function ouvrir() {
    return new Promise(function (ok, ko) {
      var r = indexedDB.open(BASE, 1);
      r.onupgradeneeded = function () { r.result.createObjectStore(MAGASIN, {keyPath: 'id'}); };
      r.onsuccess = function () { ok(r.result); };
      r.onerror = function () { ko(r.error); };
    });
  }
  function operation(mode, faire) {
    return ouvrir().then(function (bd) {
      return new Promise(function (ok, ko) {
        var t = bd.transaction(MAGASIN, mode), resultat;
        resultat = faire(t.objectStore(MAGASIN));
        t.oncomplete = function () { ok(resultat && resultat.result !== undefined ? resultat.result : resultat); };
        t.onerror = function () { ko(t.error); };
      });
    });
  }
  function toutes() {
    return operation('readonly', function (m) { return m.getAll(); }).then(function (liste) {
      return (liste || []).filter(function (e) { return e.utilisateur === utilisateur; })
        .sort(function (a, b) { return a.horodatage < b.horodatage ? -1 : 1; });
    });
  }
  function garder(envoi) { return operation('readwrite', function (m) { m.put(envoi); }); }
  function retirer(id) { return operation('readwrite', function (m) { m['delete'](id); }); }

  function appareil() {
    try {
      var a = localStorage.getItem('performyl2-appareil');
      if (!a) { a = crypto.randomUUID(); localStorage.setItem('performyl2-appareil', a); }
      return a;
    } catch (e) { return ''; }
  }

  // ── Bandeau ◷ / ✓ ───────────────────────────────────────────────────
  var bandeau = document.createElement('div');
  bandeau.className = 'bandeau-envoi';
  bandeau.hidden = true;
  var zone = document.querySelector('.page-body') || document.querySelector('.content') || corps;
  zone.insertBefore(bandeau, zone.firstChild);

  function afficher(liste, message) {
    var lignes = '';
    liste.forEach(function (e) {
      lignes += '<li><span class="coche-attente" title="En attente de réseau">◷</span> ' + texte(e.libelle) + '</li>';
    });
    if (liste.length) {
      bandeau.className = 'bandeau-envoi attente';
      bandeau.innerHTML = '<strong>◷ ' + liste.length + ' saisie' + (liste.length > 1 ? 's' : '') +
        ' gardée' + (liste.length > 1 ? 's' : '') + ' sur le téléphone</strong>' +
        '<span class="bandeau-sous">' + (navigator.onLine ? 'Envoi en cours…' : 'Envoi dès le retour du réseau.') + '</span>' +
        '<ul>' + lignes + '</ul>' + (message ? '<div class="bandeau-sous">' + texte(message) + '</div>' : '');
      bandeau.hidden = false;
    } else if (message) {
      bandeau.className = 'bandeau-envoi fait';
      bandeau.innerHTML = texte(message);
      bandeau.hidden = false;
      setTimeout(function () { bandeau.hidden = true; }, 8000);
    } else {
      bandeau.hidden = true;
    }
  }
  function texte(t) { var d = document.createElement('div'); d.textContent = t || ''; return d.innerHTML; }

  // ── Interception des formulaires marqués ────────────────────────────
  function reseauJoignable() {
    if (!navigator.onLine) return Promise.resolve(false);
    var fini = false;
    return Promise.race([
      fetch('/hors-ligne/ping', {cache: 'no-store', credentials: 'same-origin'})
        .then(function (r) { fini = true; return r.ok; }, function () { fini = true; return false; }),
      new Promise(function (ok) { setTimeout(function () { if (!fini) ok(false); }, 5000); })
    ]);
  }

  function aujourdhui() {
    var d = new Date(), m = d.getMonth() + 1, j = d.getDate();
    return d.getFullYear() + '-' + (m < 10 ? '0' : '') + m + '-' + (j < 10 ? '0' : '') + j;
  }

  document.addEventListener('submit', function (ev) {
    var form = ev.target;
    if (!form.hasAttribute || !form.hasAttribute('data-hors-ligne')) return;
    if (form.getAttribute('data-envoi-direct') === '1') { form.removeAttribute('data-envoi-direct'); return; }
    ev.preventDefault();
    var bouton = ev.submitter || null;
    if (bouton) bouton.disabled = true;
    reseauJoignable().then(function (joignable) {
      if (bouton) bouton.disabled = false;
      if (joignable) {
        form.setAttribute('data-envoi-direct', '1');
        if (form.requestSubmit) { form.requestSubmit(bouton || undefined); } else { form.submit(); }
        return;
      }
      var donnees = new FormData(form), entrees = [];
      if (bouton && bouton.name) donnees.append(bouton.name, bouton.value);
      donnees.forEach(function (valeur, nom) {
        if (nom === 'csrf_token') return;
        if (valeur instanceof File) {
          if (valeur.size) entrees.push([nom, valeur, valeur.name]);
        } else { entrees.push([nom, valeur]); }
      });
      if (!donnees.has('jour')) entrees.push(['jour', aujourdhui()]);
      return garder({
        id: crypto.randomUUID(), utilisateur: utilisateur, url: form.action,
        libelle: form.getAttribute('data-hors-ligne'), horodatage: new Date().toISOString(), entrees: entrees
      }).then(function () { location.href = '/'; });   // l'accueil affiche ◷
    });
  }, true);

  // ── Envoi après coup ────────────────────────────────────────────────
  var enCours = false;
  function envoyer() {
    if (enCours) return Promise.resolve();
    enCours = true;
    var envoyees = 0, refus = [], arret = null;
    return toutes().then(function (liste) {
      if (!liste.length || !navigator.onLine) { enCours = false; afficher(liste); return; }
      afficher(liste);
      return fetch('/hors-ligne/jeton', {cache: 'no-store', credentials: 'same-origin'})
        .then(function (r) { return r.ok ? r.json() : {etat: 'connexion'}; })
        .then(function (j) {
          if (j.etat !== 'ok') { arret = 'Reconnectez-vous pour envoyer les saisies gardées.'; return; }
          return liste.reduce(function (suite, e) {
            return suite.then(function () {
              if (arret) return;
              var fd = new FormData();
              e.entrees.forEach(function (x) { if (x.length === 3) fd.append(x[0], x[1], x[2]); else fd.append(x[0], x[1]); });
              fd.append('csrf_token', j.jeton);
              return fetch(e.url, {
                method: 'POST', body: fd, credentials: 'same-origin', cache: 'no-store',
                headers: {'X-Hors-Ligne-Id': e.id, 'X-Hors-Ligne-Horodatage': e.horodatage,
                          'X-Hors-Ligne-Libelle': encodeURIComponent(e.libelle || ''), 'X-Appareil': appareil(),
                          'Accept': 'application/json'}
              }).then(function (r) { return r.json(); }).then(function (rep) {
                if (rep.etat === 'connexion') { arret = 'Reconnectez-vous pour envoyer les saisies gardées.'; return; }
                if (rep.etat === 'refuse') refus.push(e.libelle + ' : ' + rep.message);
                else envoyees += 1;
                return retirer(e.id);
              }, function () { arret = 'Réseau coupé : nouvel essai bientôt.'; });
            });
          }, Promise.resolve());
        }, function () { arret = 'Réseau coupé : nouvel essai bientôt.'; });
    }).then(function () {
      return toutes().then(function (reste) {
        enCours = false;
        var message = arret || '';
        if (!arret && envoyees) message = '✓ Envoyé : ' + envoyees + ' saisie' + (envoyees > 1 ? 's' : '') + ' gardée' + (envoyees > 1 ? 's' : '') + ' sur le téléphone.';
        if (refus.length) message += (message ? ' ' : '') + 'Non acceptée' + (refus.length > 1 ? 's' : '') + ' : ' + refus.join(' ; ') + ' (votre agent est prévenu).';
        afficher(reste, message);
      });
    }, function () { enCours = false; });
  }

  // Page affichée sans réseau : les anciens messages ne valent plus
  if (!navigator.onLine) {
    var anciens = document.querySelector('.flash-zone');
    if (anciens) anciens.remove();
  }

  // Pages utiles sans réseau : gardées par le service worker pendant qu'il y a du réseau
  if (navigator.onLine && /^\/$/.test(location.pathname)) {
    var vues = {};
    document.querySelectorAll('a[href]').forEach(function (a) {
      var u = new URL(a.href, location.href);
      if (u.origin === location.origin && /^\/(bandes\/[^/]+\/(pesee|sortie)|sante\/declarer|livraisons\/[^/]+\/recu-moins)$/.test(u.pathname)) {
        vues[u.pathname + u.search] = true;
      }
    });
    setTimeout(function () {
      Object.keys(vues).forEach(function (u) { fetch(u, {credentials: 'same-origin'}).catch(function () {}); });
    }, 1500);
  }

  window.addEventListener('online', function () { envoyer(); });
  window.addEventListener('offline', function () { toutes().then(function (l) { afficher(l); }); });
  setInterval(function () { if (navigator.onLine) envoyer(); }, 30000);
  envoyer();
})();
