/* SORRA — espace éleveur « illustré doux » (lot 8). Sans bibliothèque.
 * - Plusieurs bâtiments : un toucher sur une pastille (ou une ligne « À faire ») affiche sa bande.
 * - Compteurs : le chiffre rebondit, petite vibration si le téléphone le permet.
 * - « Bien reçu ! » : se ferme seul après ~2 s, sauf s'il reste une bande à saisir.
 * - Saisie gardée sans réseau : même écran, « ◷ Sera envoyé dès que le réseau revient ».
 */
(function () {
  'use strict';
  var calme = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // ── Bâtiments ─────────────────────────────────────────────────────────
  function choisir(cible, defiler) {
    var bloc = document.getElementById(cible);
    if (!bloc) return false;
    var espace = bloc.closest('.espace-ferme');
    if (!espace || !espace.classList.contains('plusieurs')) return false;
    espace.classList.add('choisi');
    espace.querySelectorAll('.bloc-bat').forEach(function (b) { b.classList.toggle('active', b === bloc); });
    espace.querySelectorAll('.pastille-bat').forEach(function (p) {
      p.classList.toggle('active', p.getAttribute('data-cible') === cible);
    });
    try { history.replaceState(null, '', '#' + cible); } catch (e) {}
    if (defiler) {
      var nav = espace.querySelector('.pastilles-bat') || bloc;
      nav.scrollIntoView({behavior: calme ? 'auto' : 'smooth', block: 'start'});
    }
    return true;
  }
  document.querySelectorAll('.espace-ferme.plusieurs').forEach(function (espace) {
    var voulu = location.hash ? location.hash.slice(1) : '';
    var premier = espace.querySelector('.bloc-bat');
    if (!(voulu && espace.querySelector('[id="' + voulu + '"]') && choisir(voulu, false)) && premier) {
      choisir(premier.id, false);
    }
  });
  document.addEventListener('click', function (ev) {
    var lien = ev.target.closest('[data-cible]');
    if (!lien || lien.classList.contains('bloc-bat')) return;
    if (choisir(lien.getAttribute('data-cible'), true)) {
      ev.preventDefault();
      fermerBienRecu();
    }
  });

  // ── Compteurs : rebond et vibration ───────────────────────────────────
  document.addEventListener('click', function (ev) {
    var bouton = ev.target.closest('.compteur-plus, .compteur-moins');
    if (!bouton) return;
    var champ = bouton.closest('.compteur').querySelector('.compteur-valeur');
    if (champ && !calme) {
      champ.classList.remove('rebond');
      void champ.offsetWidth;   // relance l'animation
      champ.classList.add('rebond');
    }
    try { if (navigator.vibrate) navigator.vibrate(12); } catch (e) {}
  });

  // ── « Bien reçu ! » ───────────────────────────────────────────────────
  function fermerBienRecu() {
    var ecran = document.getElementById('bien-recu');
    if (!ecran) return;
    ecran.classList.add('ferme');
    setTimeout(function () { if (ecran.parentNode) ecran.parentNode.removeChild(ecran); }, 300);
  }
  function brancherBienRecu(ecran) {
    ecran.addEventListener('click', function (ev) {
      if (ev.target === ecran || ev.target.closest('.bien-recu-fermer')) fermerBienRecu();
    });
    if (ecran.getAttribute('data-fermer-auto') === '1') setTimeout(fermerBienRecu, 2200);
  }
  var ecran = document.getElementById('bien-recu');
  if (ecran) brancherBienRecu(ecran);

  // Saisie gardée sur le téléphone (hors_ligne.js) : même écran, sans réseau
  try {
    var garde = sessionStorage.getItem('performyl2-garde');
    if (garde) {
      sessionStorage.removeItem('performyl2-garde');
      var feu = JSON.parse(garde).feu || 'gris';
      var joie = feu === 'vert';
      var modele = document.getElementById('modele-poulet-' + (joie ? 'vert' : feu));
      var div = document.createElement('div');
      div.className = 'bien-recu ' + (joie ? 'joie' : 'sobre');
      div.id = 'bien-recu';
      div.setAttribute('role', 'status');
      div.setAttribute('data-fermer-auto', '1');
      div.innerHTML = '<div class="bien-recu-carte">' + (modele ? modele.innerHTML : '') +
        '<div class="bien-recu-titre">' + (joie ? 'Bien reçu !' : 'Gardé ✓') + '</div>' +
        '<div class="bien-recu-sous">◷ En attente — envoi automatique dès que le réseau revient.</div></div>';
      document.body.appendChild(div);
      brancherBienRecu(div);
    }
  } catch (e) {}
})();
