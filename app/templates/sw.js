/* SORRA — service worker (voir docs/hors_ligne.md). Gabarit : la version et les adresses
 * des fichiers sont écrites par le serveur (app/routes/hors_ligne.py, app/utils/statiques.py).
 *
 * Mises à jour automatiques chez l'éleveur :
 * - la VERSION est l'empreinte de l'application : ce fichier change à chaque mise à jour,
 *   le navigateur installe aussitôt le nouveau service worker ;
 * - il prend la main tout de suite (skipWaiting, clients.claim) et SUPPRIME les anciens caches ;
 * - la page se recharge proprement une fois (hors_ligne.js, « controllerchange ») ;
 * - les fichiers CSS et JS sont appelés avec leur empreinte (?v=…) : jamais d'ancien fichier.
 *
 * Stratégies :
 * - pages, CSS, JS : réseau d'abord, cache seulement sans réseau ;
 * - polices et images : cache d'abord (elles ne changent pas, ou changent d'adresse).
 * Les envois (POST) ne passent jamais par ici : hors_ligne.js s'en occupe. */
var VERSION = '{{ version }}';
var PREFIXE = 'performyl2-';
var STATIQUES = PREFIXE + 'statiques-' + VERSION;
var PAGES = PREFIXE + 'pages-' + VERSION;
var A_GARDER = {{ a_garder|tojson }};
var JAMAIS = /^\/(q\/|hors-ligne\/|auth\/|sw\.js)/;
var CACHE_D_ABORD = /\.(woff2?|ttf|png|jpe?g|webp|gif|svg|ico)$/i;
var SANS_RESEAU = '<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">' +
  '<meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Pas de réseau — SORRA</title>' +
  '<link href="{{ url_for('static', filename='css/perform.css') }}" rel="stylesheet"></head><body><div class="page-body">' +
  '<div class="flash-item warning">Pas de réseau : cette page n\'est pas gardée sur le téléphone.</div>' +
  '<a class="btn-gros" href="/">Retour à l\'accueil</a></div></body></html>';

function garder(cache, url) {
  // « reload » : jamais une copie du cache HTTP du navigateur
  return fetch(new Request(url, {cache: 'reload'})).then(function (rep) {
    if (rep.ok) return cache.put(url, rep);
  }).catch(function () {});
}

self.addEventListener('install', function (e) {
  e.waitUntil(caches.open(STATIQUES)
    .then(function (c) { return Promise.all(A_GARDER.map(function (u) { return garder(c, u); })); })
    .then(function () { return caches.open(PAGES); })
    .then(function (c) { return garder(c, '/'); })
    .then(function () { return self.skipWaiting(); }));
});

self.addEventListener('activate', function (e) {
  // Tous les anciens caches de l'application disparaissent (statiques et pages)
  e.waitUntil(caches.keys().then(function (noms) {
    return Promise.all(noms.filter(function (n) {
      return n.indexOf(PREFIXE) === 0 && n !== STATIQUES && n !== PAGES;
    }).map(function (n) { return caches.delete(n); }));
  }).then(function () { return self.clients.claim(); }));
});

function delai(promesse, ms) {
  return new Promise(function (ok, ko) {
    var t = setTimeout(function () { ko(new Error('délai')); }, ms);
    promesse.then(function (r) { clearTimeout(t); ok(r); }, function (err) { clearTimeout(t); ko(err); });
  });
}

function reseauDAbord(req, cacheNom, accepter) {
  return delai(fetch(req), 8000).then(function (rep) {
    if (rep.ok && accepter(rep)) {
      var copie = rep.clone();
      caches.open(cacheNom).then(function (c) {
        // Page obtenue par redirection (/aller/peser → la pesée de la bande) : une copie « propre »,
        // sinon le navigateur refuse de l'afficher sans réseau (lot 13)
        if (!copie.redirected) return c.put(req, copie);
        return copie.blob().then(function (corps) {
          return c.put(req, new Response(corps, {status: copie.status, statusText: copie.statusText, headers: copie.headers}));
        });
      });
    }
    return rep;
  });
}

self.addEventListener('fetch', function (e) {
  var req = e.request, url = new URL(req.url);
  if (req.method !== 'GET' || url.origin !== self.location.origin || JAMAIS.test(url.pathname)) return;

  if (url.pathname.indexOf('/static/') === 0) {
    if (CACHE_D_ABORD.test(url.pathname)) {
      e.respondWith(caches.match(req, {ignoreVary: true}).then(function (garde) {
        return garde || fetch(req).then(function (rep) {
          if (rep.ok) { var copie = rep.clone(); caches.open(STATIQUES).then(function (c) { c.put(req, copie); }); }
          return rep;
        });
      }));
      return;
    }
    // CSS, JS : réseau d'abord ; sans réseau, la copie gardée (même version, sinon la dernière)
    e.respondWith(reseauDAbord(req, STATIQUES, function () { return true; }).catch(function () {
      return caches.match(req, {ignoreVary: true}).then(function (garde) {
        return garde || caches.match(req, {ignoreVary: true, ignoreSearch: true});
      }).then(function (garde) { return garde || Response.error(); });
    }));
    return;
  }

  e.respondWith(reseauDAbord(req, PAGES, function (rep) {
    var html = (rep.headers.get('Content-Type') || '').indexOf('text/html') === 0;
    var connexion = rep.redirected && new URL(rep.url).pathname.indexOf('/auth/') === 0;
    return html && !connexion;
  }).catch(function () {
    return caches.match(req, {ignoreVary: true}).then(function (garde) {
      if (garde) return garde;
      if (req.mode === 'navigate') {
        return new Response(SANS_RESEAU, {headers: {'Content-Type': 'text/html; charset=utf-8'}});
      }
      return Response.error();
    });
  }));
});
