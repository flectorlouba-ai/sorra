/* SORRA — fenêtres (lot A1, docs/ergonomie.md section K).
 *
 * Un seul composant par style : .modal-overlay > .modal-box. En terrain (body.theme-terrain), c'est une feuille qui
 * monte du bas, avec une poignée (glisser vers le bas pour fermer) et ✕ ; en bureau, une fenêtre au centre.
 *  - ouvrir(id) / fermer(id) : comme avant (onclick des écrans de bureau) ;
 *  - [data-ouvrir="id"] ouvre, [data-fermer] ferme la fenêtre qui le contient ;
 *  - .modal-overlay[data-ouverte] : ouverte d'office (formulaire d'ajout d'un écran) ;
 *  - [data-retour-fermer] : ✕ ramène à cette adresse (écran sans liste derrière) ;
 *  - [data-fiche="id"] : copie le <template id> (fiche préremplie) dans #fen-fiche et l'ouvre ;
 *  - [data-confirmer] : montre la confirmation « Oui, archiver » du formulaire.
 * Tout est déjà dans la page : rien ne demande le réseau.
 */
(function () {
  'use strict';
  var terrain = document.body.classList.contains('theme-terrain');

  function boite(id) { return document.getElementById(id); }
  function ouvertes() { return document.querySelectorAll('.modal-overlay:not([hidden])'); }

  window.ouvrir = function (id) {
    var f = boite(id);
    if (!f) return;
    f.hidden = false;
    document.body.classList.add('fenetre-ouverte');
  };
  window.fermer = function (id) {
    var f = boite(id);
    if (!f) return;
    var retour = f.getAttribute('data-retour-fermer');
    if (retour) { location.href = retour; return; }
    f.hidden = true;
    var boiteF = f.querySelector('.modal-box');
    if (boiteF) boiteF.style.transform = '';
    if (!ouvertes().length) document.body.classList.remove('fenetre-ouverte');
  };

  function ouvrirFiche(id) {
    var modele = boite(id), f = boite('fen-fiche');
    if (!modele || !f) return;
    var zone = f.querySelector('.fen-fiche-contenu');
    zone.innerHTML = '';
    zone.appendChild(modele.content.cloneNode(true));
    boite('fen-fiche-titre').textContent = modele.getAttribute('data-titre') || '';
    window.ouvrir('fen-fiche');
  }

  document.addEventListener('click', function (e) {
    var cible = e.target;
    var o = cible.closest('[data-ouvrir]');
    if (o) { e.preventDefault(); window.ouvrir(o.getAttribute('data-ouvrir')); return; }
    var fe = cible.closest('[data-fermer]');
    if (fe) { e.preventDefault(); var f = fe.closest('.modal-overlay'); if (f) window.fermer(f.id); return; }
    var fi = cible.closest('[data-fiche]');
    if (fi) { e.preventDefault(); ouvrirFiche(fi.getAttribute('data-fiche')); return; }
    var c = cible.closest('[data-confirmer]');
    if (c) {
      e.preventDefault();
      var z = c.closest('form').querySelector('.fiche-confirmer');
      if (z) { z.hidden = !z.hidden; if (!z.hidden) z.scrollIntoView({block: 'nearest'}); }
      return;
    }
    // Feuille du terrain : toucher le fond grisé la referme
    if (terrain && cible.classList && cible.classList.contains('modal-overlay')) window.fermer(cible.id);
  });

  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    Array.prototype.forEach.call(ouvertes(), function (m) { window.fermer(m.id); });
  });

  // Glisser la feuille vers le bas (poignée ou bandeau du titre) pour la fermer
  if (terrain) {
    var depart = null, feuille = null;
    document.addEventListener('touchstart', function (e) {
      var prise = e.target.closest('.fenetre-poignee, .modal-head');
      if (!prise || e.target.closest('button')) return;
      feuille = prise.closest('.modal-box');
      depart = e.touches[0].clientY;
    }, {passive: true});
    document.addEventListener('touchmove', function (e) {
      if (depart === null || !feuille) return;
      var dy = Math.max(0, e.touches[0].clientY - depart);
      feuille.style.transform = 'translateY(' + dy + 'px)';
    }, {passive: true});
    document.addEventListener('touchend', function (e) {
      if (depart === null || !feuille) return;
      var dy = e.changedTouches[0].clientY - depart, f = feuille.closest('.modal-overlay');
      feuille.style.transform = '';
      depart = null; feuille = null;
      if (dy > 80 && f) window.fermer(f.id);
    });
  }

  // Fenêtre de bureau d'un élément archivable (_macros.pied_archivable) : 'nouveau', 'actif' ou 'archive'
  window.etatFenetre = function (id, mode) {
    var f = boite(id);
    if (!f) return;
    Array.prototype.forEach.call(f.querySelectorAll('[data-si]'), function (b) {
      b.hidden = b.getAttribute('data-si').split(' ').indexOf(mode) < 0;
      if (!b.hasAttribute('data-libelle-actif')) return;
      if (!b.hasAttribute('data-libelle')) b.setAttribute('data-libelle', b.textContent);
      b.textContent = mode === 'actif' ? b.getAttribute('data-libelle-actif') : b.getAttribute('data-libelle');
    });
    Array.prototype.forEach.call(f.querySelectorAll('input, select, textarea'), function (c) {
      if (c.type !== 'hidden') c.disabled = mode === 'archive';
    });
  };

  Array.prototype.forEach.call(document.querySelectorAll('.modal-overlay[data-ouverte]'), function (f) {
    window.ouvrir(f.id);
  });
})();
