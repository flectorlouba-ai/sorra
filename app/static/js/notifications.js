/* Lot T — notifications Web Push, côté téléphone.
 * 1. Écran « 🔔 Mes notifications » : bouton « Être prévenu sur ce téléphone » / « Ne plus être prévenu ».
 * 2. Carte « 🔔 Être prévenu quand il faut saisir ? » après la première saisie réussie (écran « Bien reçu ! »),
 *    jamais au premier lancement ; « Plus tard » la cache pour 7 jours.
 * Sans clé VAPID sur le serveur, rien n'est proposé. */
(function () {
  'use strict';
  if (!('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window)) return;

  var jeton = (document.querySelector('meta[name="csrf-token"]') || {}).content || '';
  var chargement = null;

  function jetonFormulaire() {
    if (jeton) return Promise.resolve(jeton);
    return fetch('/hors-ligne/jeton', {credentials: 'same-origin', cache: 'no-store'})
      .then(function (r) { return r.json(); }).then(function (d) { jeton = d.jeton || ''; return jeton; });
  }

  function clePublique() {
    if (!chargement) {
      chargement = fetch('/notifications/cle-publique', {credentials: 'same-origin', cache: 'no-store'})
        .then(function (r) { return r.ok ? r.json() : {cle: null}; }).then(function (d) { return d.cle || null; })
        .catch(function () { return null; });
    }
    return chargement;
  }

  function versOctets(base64) {
    var s = (base64 + '='.repeat((4 - base64.length % 4) % 4)).replace(/-/g, '+').replace(/_/g, '/');
    var brut = atob(s), octets = new Uint8Array(brut.length);
    for (var i = 0; i < brut.length; i++) octets[i] = brut.charCodeAt(i);
    return octets;
  }

  function envoyer(url, corps) {
    return jetonFormulaire().then(function (t) {
      return fetch(url, {method: 'POST', credentials: 'same-origin',
        headers: {'Content-Type': 'application/json', 'X-CSRFToken': t}, body: JSON.stringify(corps)});
    });
  }

  function abonnementActuel() {
    return navigator.serviceWorker.ready.then(function (reg) { return reg.pushManager.getSubscription(); });
  }

  function activer() {
    return clePublique().then(function (cle) {
      if (!cle) throw new Error('sans_cle');
      return Notification.requestPermission().then(function (perm) {
        if (perm !== 'granted') throw new Error('refuse');
        return navigator.serviceWorker.ready;
      }).then(function (reg) {
        return reg.pushManager.getSubscription().then(function (s) {
          return s || reg.pushManager.subscribe({userVisibleOnly: true, applicationServerKey: versOctets(cle)});
        });
      }).then(function (s) {
        return envoyer('/notifications/abonner', {abonnement: s.toJSON(), appareil: navigator.platform || ''})
          .then(function (r) { if (!r.ok) throw new Error('serveur'); return s; });
      });
    });
  }

  function couper() {
    return abonnementActuel().then(function (s) {
      if (!s) return;
      return envoyer('/notifications/desabonner', {abonnement: s.toJSON()}).then(function () { return s.unsubscribe(); });
    });
  }

  window.sorraNotifications = {activer: activer, couper: couper};

  // ── Écran « Mes notifications » ──
  var zone = document.querySelector('[data-etat-notifications]');
  if (zone) {
    var bActiver = zone.querySelector('[data-notif-activer]'), bCouper = zone.querySelector('[data-notif-couper]');
    var refuse = zone.querySelector('[data-notif-refuse]');
    function rafraichir() {
      clePublique().then(function (cle) {
        if (!cle) return;
        if (Notification.permission === 'denied') { refuse.hidden = false; return; }
        abonnementActuel().then(function (s) {
          bActiver.hidden = !!s;
          bCouper.hidden = !s;
        });
      });
    }
    bActiver.addEventListener('click', function () {
      bActiver.disabled = true;
      activer().then(function () { bActiver.disabled = false; rafraichir(); })
        .catch(function () { bActiver.disabled = false; rafraichir(); });
    });
    bCouper.addEventListener('click', function () {
      bCouper.disabled = true;
      couper().then(function () { bCouper.disabled = false; rafraichir(); });
    });
    rafraichir();
  }

  // ── Carte après la première saisie réussie ──
  var bienRecu = document.getElementById('bien-recu');
  if (bienRecu && Notification.permission === 'default') {
    var plusTard = 0;
    try { plusTard = parseInt(localStorage.getItem('sorra-notif-plus-tard') || '0', 10); } catch (e) {}
    if (Date.now() - plusTard < 7 * 86400000) return;
    clePublique().then(function (cle) {
      if (!cle) return;
      abonnementActuel().then(function (s) {
        if (s) return;
        var carte = document.createElement('div');
        carte.className = 'carte carte-notif';
        carte.setAttribute('data-carte-notifications', '1');
        carte.innerHTML = '<div class="carte-titre">🔔 Être prévenu quand il faut saisir ?</div>' +
          '<div class="carte-sous">Un rappel le soir si rien n\'est noté, et les alertes importantes.</div>' +
          '<button type="button" class="btn-gros btn-vert mt-2" data-notif-oui>Oui, me prévenir</button>' +
          '<button type="button" class="btn-gros-secondaire mt-2" data-notif-plus-tard>Plus tard</button>';
        // Dans la page (sous l'écran « Bien reçu ! », qui se ferme seul), en tête de « Ma bande aujourd'hui »
        var zone = document.querySelector('.ma-ferme-zone') || bienRecu.parentNode;
        zone.insertBefore(carte, bienRecu.nextSibling);
        carte.querySelector('[data-notif-oui]').addEventListener('click', function () {
          activer().then(function () { carte.innerHTML = '<div class="carte-titre">✓ Vous serez prévenu</div>'; })
            .catch(function () { carte.remove(); });
        });
        carte.querySelector('[data-notif-plus-tard]').addEventListener('click', function () {
          try { localStorage.setItem('sorra-notif-plus-tard', String(Date.now())); } catch (e) {}
          carte.remove();
        });
      });
    });
  }
})();
