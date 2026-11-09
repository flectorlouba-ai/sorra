/* SORRA — lot 19 : scan d'un lot par l'opérateur et comptage à la réception.
 *
 * Caméra : lecteur intégré au navigateur (BarcodeDetector, Chrome Android) ; sinon jsQR, copié dans
 * static/vendor (aucun CDN), chargé seulement s'il le faut. La caméra n'est ouverte qu'en HTTPS.
 * Avec du réseau, le lot lu ouvre son résultat (vert, orange, rouge) ; sans réseau, la réception est gardée
 * sur le téléphone (hors_ligne.js) et vérifiée par le serveur à l'arrivée.
 * Comptage : cases vides au départ ; l'écart avec l'annoncé s'affiche dès que les chiffres sont tapés, et
 * la raison devient obligatoire.
 */
(function () {
  'use strict';

  // ── Comptage : écart avec l'annoncé, raison obligatoire ─────────────
  var chiffres = document.querySelector('.op-chiffres');
  function entier(id) {
    var v = (document.getElementById(id) || {}).value;
    return v === undefined || v === '' || !/^\d+$/.test(v.trim()) ? null : parseInt(v, 10);
  }
  function majEcart() {
    if (!chiffres) return;
    var annonce = chiffres.getAttribute('data-annonce'), seuil = parseFloat(chiffres.getAttribute('data-seuil') || '2');
    var vivants = entier('vivants'), morts = entier('morts');
    var bloc = document.getElementById('op-ecart'), motifs = document.getElementById('op-motifs');
    var aExpliquer = false;
    if (annonce !== '' && vivants !== null && morts !== null) {
      annonce = parseInt(annonce, 10);
      var ecart = annonce - vivants - morts, pct = annonce ? morts / annonce * 100 : 0;
      document.getElementById('ec-annonce').textContent = annonce.toLocaleString('fr-FR');
      document.getElementById('ec-vivants').textContent = vivants.toLocaleString('fr-FR');
      document.getElementById('ec-morts').textContent = morts + ' (' + pct.toLocaleString('fr-FR', {maximumFractionDigits: 1}) + ' %)';
      var phrases = [];
      if (ecart > 0) phrases.push('Il manque ' + ecart + ' poulet' + (ecart > 1 ? 's' : ''));
      if (ecart < 0) phrases.push(-ecart + ' poulet' + (ecart < -1 ? 's' : '') + ' en trop');
      if (pct > seuil) phrases.push('morts au-delà de ' + seuil.toLocaleString('fr-FR') + ' %');
      aExpliquer = phrases.length > 0;
      document.getElementById('ec-texte').textContent = aExpliquer ? '⚠ ' + phrases.join(', ') + ' : touchez la raison (obligatoire).' : '✓ Conforme à l\'annoncé';
      bloc.hidden = false;
      bloc.classList.toggle('ecart', aExpliquer);
    } else if (bloc) {
      bloc.hidden = true;
    }
    if (motifs) {
      var sansAnnonce = chiffres.getAttribute('data-annonce') === '';
      motifs.hidden = !(aExpliquer || (sansAnnonce && document.querySelector('input[name=motif_ecart]:checked')));
      if (sansAnnonce && vivants !== null && morts !== null) motifs.hidden = false;   // sans réseau : facultatif
      var radios = motifs.querySelectorAll('input[name=motif_ecart]');
      radios.forEach(function (r) { r.required = aExpliquer; });
      var choisi = motifs.querySelector('input[name=motif_ecart]:checked');
      var autre = document.getElementById('op-explication');
      autre.hidden = !(choisi && choisi.value === 'Autre');
      document.getElementById('explication').required = !autre.hidden && aExpliquer;
    }
  }
  if (chiffres) {
    ['vivants', 'morts'].forEach(function (id) { document.getElementById(id).addEventListener('input', majEcart); });
    document.querySelectorAll('input[name=motif_ecart]').forEach(function (r) { r.addEventListener('change', majEcart); });
    majEcart();
  }

  // ── Scanner ─────────────────────────────────────────────────────────
  var zone = document.getElementById('op-scanner');
  if (!zone) return;
  var video = document.getElementById('op-video'), message = document.getElementById('op-camera-message');
  var attendus = {};
  try { attendus = JSON.parse(document.getElementById('op-attendus').textContent) || {}; } catch (e) {}
  var fini = false, flux = null;

  function codeLu(texte) {
    var m = /\/q\/([A-Za-z0-9_-]{8,40})\/?(?:[?#].*)?$/.exec((texte || '').trim());
    return m ? m[1] : (texte || '').trim();
  }
  function reseau() {
    if (!navigator.onLine) return Promise.resolve(false);
    var fait = false;
    return Promise.race([
      fetch('/hors-ligne/ping', {cache: 'no-store', credentials: 'same-origin'})
        .then(function (r) { fait = true; return r.ok; }, function () { fait = true; return false; }),
      new Promise(function (ok) { setTimeout(function () { if (!fait) ok(false); }, 4000); })
    ]);
  }
  function arreter() {
    fini = true;
    if (flux) flux.getTracks().forEach(function (t) { t.stop(); });
  }
  function sansReseau(code, numero) {
    var form = document.getElementById('op-form-hors-ligne');
    document.getElementById('hl-code').value = code || '';
    document.getElementById('hl-numero').value = numero || '';
    var connu = code ? attendus[code] : null;
    if (!connu && numero) {
      Object.keys(attendus).forEach(function (k) { if (attendus[k].numero.toUpperCase() === numero.toUpperCase()) connu = attendus[k]; });
    }
    var titre = document.getElementById('hl-lot');
    if (connu) {
      titre.textContent = 'Lot ' + connu.numero + ' · ' + connu.nombre.toLocaleString('fr-FR') + ' poulets annoncés · ' + connu.ferme;
      chiffres.setAttribute('data-annonce', connu.nombre);
      form.setAttribute('data-hors-ligne', 'Réception du lot ' + connu.numero);
    } else {
      titre.textContent = numero ? 'Lot ' + numero : 'Lot lu (inconnu sur ce téléphone : il sera vérifié à l\'arrivée)';
      chiffres.setAttribute('data-annonce', '');
    }
    document.getElementById('op-camera').hidden = true;
    document.getElementById('op-form-numero').hidden = true;
    form.hidden = false;
    majEcart();
    document.getElementById('vivants').focus();
  }
  function lu(texte) {
    if (fini) return;
    var code = codeLu(texte);
    if (!code) return;
    arreter();
    if (navigator.vibrate) { try { navigator.vibrate(80); } catch (e) {} }
    message.textContent = 'QR lu ✓';
    reseau().then(function (ok) {
      if (ok) { location.href = '/operateur/lot?code=' + encodeURIComponent(code); return; }
      sansReseau(code, null);
    });
  }

  document.getElementById('op-form-numero').addEventListener('submit', function (ev) {
    var numero = document.getElementById('numero').value.trim();
    if (!numero) return;
    ev.preventDefault();
    reseau().then(function (ok) {
      if (ok) { location.href = '/operateur/lot?numero=' + encodeURIComponent(numero); return; }
      arreter();
      sansReseau(null, numero);
    });
  });

  function chargerJsQR() {
    if (window.jsQR) return Promise.resolve(window.jsQR);
    var source = document.querySelector('script[data-jsqr]');
    return new Promise(function (ok, ko) {
      var s = document.createElement('script');
      s.src = source.getAttribute('data-jsqr');
      s.onload = function () { ok(window.jsQR); };
      s.onerror = ko;
      document.head.appendChild(s);
    });
  }
  function boucle(lire) {
    function image() {
      if (fini) return;
      lire().then(function (texte) { if (texte) lu(texte); else requestAnimationFrame(image); },
                  function () { requestAnimationFrame(image); });
    }
    requestAnimationFrame(image);
  }

  if (!window.isSecureContext || !navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    message.textContent = 'Caméra indisponible ici : tapez le numéro du lot.';
    return;
  }
  navigator.mediaDevices.getUserMedia({video: {facingMode: 'environment'}, audio: false}).then(function (f) {
    flux = f;
    video.srcObject = f;
    return video.play();
  }).then(function () {
    message.textContent = 'Visez le QR code';
    if ('BarcodeDetector' in window) {
      var detecteur = new window.BarcodeDetector({formats: ['qr_code']});
      boucle(function () {
        return detecteur.detect(video).then(function (codes) { return codes.length ? codes[0].rawValue : null; });
      });
      return;
    }
    return chargerJsQR().then(function (jsQR) {
      var toile = document.createElement('canvas'), ctx = toile.getContext('2d', {willReadFrequently: true});
      boucle(function () {
        var l = video.videoWidth, h = video.videoHeight;
        if (!l || !h) return Promise.resolve(null);
        toile.width = l; toile.height = h;
        ctx.drawImage(video, 0, 0, l, h);
        var r = jsQR(ctx.getImageData(0, 0, l, h).data, l, h, {inversionAttempts: 'dontInvert'});
        return Promise.resolve(r ? r.data : null);
      });
    });
  }).catch(function () {
    message.textContent = 'Caméra refusée ou absente : tapez le numéro du lot.';
  });
})();
