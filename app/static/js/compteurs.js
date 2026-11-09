/* Gros compteurs « − valeur + » (saisie d'une main sur téléphone).
   Lot 12 : un champ data-vide démarre à « — » (rien de noté) ; « − » à 0 revient à « — » ;
   les cases rapides (data-mettre : « Aucun mort », « Pas d'aliment donné », « Comme hier »)
   donnent une valeur explicite ; « Envoyer » est refusé tant qu'une case est à « — ». */
var MESSAGES_VIDE = {
  morts: 'Touchez « Aucun mort » s\'il n\'y a pas eu de mort.',
  aliment: 'Touchez « Pas d\'aliment donné » si vous n\'avez pas donné d\'aliment.'
};
document.querySelectorAll('.compteur').forEach(function (c) {
  var champ = c.querySelector('.compteur-valeur');
  if (!champ) return;
  var pas = parseFloat(champ.step) || 1;
  var vide = champ.hasAttribute('data-vide');
  function borne(v) {
    var min = champ.min === '' ? -Infinity : parseFloat(champ.min);
    var max = champ.max === '' ? Infinity : parseFloat(champ.max);
    return Math.min(max, Math.max(min, v));
  }
  function marquer() {
    c.querySelectorAll('.case-rapide').forEach(function (b) {
      b.classList.toggle('choisie', champ.value !== '' && parseFloat(b.dataset.mettre) === parseFloat(champ.value) &&
        (!b.dataset.aliment || (c.closest('form').querySelector('input[name=aliment_choisi]:checked, input[name=aliment_choisi][type=hidden]') || {}).value === b.dataset.aliment));
    });
  }
  function changer(delta) {
    var brut = String(champ.value).replace(',', '.');
    if (vide && brut === '') {
      if (delta < 0) return;
      champ.value = borne(pas);                       // le premier « + » met 1
    } else {
      var v = parseFloat(brut) || 0;
      champ.value = (vide && delta < 0 && v <= 0) ? '' : borne(Math.round((v + delta) * 100) / 100);
    }
    champ.dispatchEvent(new Event('input', {bubbles: true}));
  }
  var moins = c.querySelector('.compteur-moins'), plus = c.querySelector('.compteur-plus');
  if (moins) moins.addEventListener('click', function () { changer(-pas); });
  if (plus) plus.addEventListener('click', function () { changer(pas); });
  c.querySelectorAll('.case-rapide').forEach(function (b) {
    b.addEventListener('click', function () {
      if (b.dataset.aliment) {                          // « Comme hier » : le même aliment qu'hier
        var r = c.closest('form').querySelector('input[name=aliment_choisi][value="' + b.dataset.aliment + '"]');
        if (r) r.checked = true;
      }
      champ.value = b.dataset.mettre;
      champ.dispatchEvent(new Event('input', {bubbles: true}));
    });
  });
  champ.addEventListener('input', function () {
    marquer();
    var f = champ.closest('form'), m = f && f.querySelector('.message-vide');
    if (m) m.hidden = true;
  });
  marquer();
});

// Avant tout envoi (y compris sans réseau) : une case à « — » n'est jamais envoyée comme un zéro
window.addEventListener('submit', function (ev) {
  var form = ev.target;
  if (!form.querySelectorAll) return;
  var manquant = Array.prototype.find.call(form.querySelectorAll('[data-vide]'), function (ch) {
    return String(ch.value).trim() === '';
  });
  if (!manquant) return;
  ev.preventDefault();
  ev.stopImmediatePropagation();
  var m = form.querySelector('.message-vide');
  if (m) {
    m.textContent = MESSAGES_VIDE[manquant.dataset.vide] || 'Complétez la saisie.';
    m.hidden = false;
    m.scrollIntoView({block: 'center'});
  }
}, true);
