/* SORRA — service worker (voir docs/hors_ligne.md).
 * Fichiers de style et scripts : gardés sur le téléphone.
 * Pages : réseau d'abord ; sans réseau, la dernière version vue sur ce téléphone.
 * Les envois (POST) ne passent jamais par ici : hors_ligne.js s'en occupe. */
var VERSION = 'v3';   // v3 : espace éleveur « illustré doux » (lot 8)
var STATIQUES = 'performyl2-statiques-' + VERSION;
var PAGES = 'performyl2-pages';
var A_GARDER = [
  '/static/css/perform.css',
  '/static/css/eleveur.css',
  '/static/js/eleveur.js',
  '/static/polices/nunito-latin-400-normal.woff2',
  '/static/polices/nunito-latin-600-normal.woff2',
  '/static/polices/nunito-latin-700-normal.woff2',
  '/static/polices/nunito-latin-800-normal.woff2',
  '/static/polices/polices.css',
  '/static/vendor/bootstrap-5.3.3/css/bootstrap.min.css',
  '/static/vendor/bootstrap-icons-1.11.3/bootstrap-icons.min.css',
  '/static/vendor/bootstrap-5.3.3/js/bootstrap.bundle.min.js',
  '/static/js/compteurs.js',
  '/static/js/hors_ligne.js',
  '/static/vendor/bootstrap-icons-1.11.3/fonts/bootstrap-icons.woff2?dd67030699838ea613ee6dbda90effa6',
  '/static/polices/space-grotesk-latin-400-normal.woff2',
  '/static/polices/space-grotesk-latin-500-normal.woff2',
  '/static/polices/space-grotesk-latin-600-normal.woff2',
  '/static/polices/space-grotesk-latin-700-normal.woff2',
  '/static/polices/jetbrains-mono-latin-700-normal.woff2',
  '/static/icones/icone-192.png',
  '/static/manifest.webmanifest'
];
var JAMAIS = /^\/(q\/|hors-ligne\/|auth\/|sw\.js)/;
var SANS_RESEAU = '<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">' +
  '<meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Pas de réseau — SORRA</title>' +
  '<link href="/static/css/perform.css" rel="stylesheet"></head><body><div class="page-body">' +
  '<div class="flash-item warning">Pas de réseau : cette page n\'est pas gardée sur le téléphone.</div>' +
  '<a class="btn-gros" href="/">Retour à l\'accueil</a></div></body></html>';

self.addEventListener('install', function (e) {
  e.waitUntil(caches.open(STATIQUES).then(function (c) { return c.addAll(A_GARDER); })
    .then(function () { return caches.open(PAGES); })
    .then(function (c) { return c.add('/'); })
    .catch(function () {})
    .then(function () { return self.skipWaiting(); }));
});

self.addEventListener('activate', function (e) {
  e.waitUntil(caches.keys().then(function (noms) {
    return Promise.all(noms.filter(function (n) { return n.indexOf('performyl2-statiques-') === 0 && n !== STATIQUES; })
      .map(function (n) { return caches.delete(n); }));
  }).then(function () { return self.clients.claim(); }));
});

function delai(promesse, ms) {
  return new Promise(function (ok, ko) {
    var t = setTimeout(function () { ko(new Error('délai')); }, ms);
    promesse.then(function (r) { clearTimeout(t); ok(r); }, function (err) { clearTimeout(t); ko(err); });
  });
}

self.addEventListener('fetch', function (e) {
  var req = e.request, url = new URL(req.url);
  if (req.method !== 'GET' || url.origin !== self.location.origin || JAMAIS.test(url.pathname)) return;

  if (url.pathname.indexOf('/static/') === 0) {
    e.respondWith(caches.match(req, {ignoreVary: true}).then(function (garde) {
      return garde || fetch(req).then(function (rep) {
        if (rep.ok) { var copie = rep.clone(); caches.open(STATIQUES).then(function (c) { c.put(req, copie); }); }
        return rep;
      });
    }));
    return;
  }

  e.respondWith(delai(fetch(req), 8000).then(function (rep) {
    var html = (rep.headers.get('Content-Type') || '').indexOf('text/html') === 0;
    var connexion = rep.redirected && new URL(rep.url).pathname.indexOf('/auth/') === 0;
    if (rep.ok && html && !connexion) {
      var copie = rep.clone();
      caches.open(PAGES).then(function (c) { c.put(req, copie); });
    }
    return rep;
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
