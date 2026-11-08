/* Gros compteurs « − valeur + » (saisie d'une main sur téléphone). */
document.querySelectorAll('.compteur').forEach(function (c) {
  var champ = c.querySelector('.compteur-valeur');
  var pas = parseFloat(champ.step) || 1;
  function borne(v) {
    var min = champ.min === '' ? -Infinity : parseFloat(champ.min);
    var max = champ.max === '' ? Infinity : parseFloat(champ.max);
    return Math.min(max, Math.max(min, v));
  }
  function changer(delta) {
    var v = parseFloat(String(champ.value).replace(',', '.')) || 0;
    champ.value = borne(Math.round((v + delta) * 100) / 100);
    champ.dispatchEvent(new Event('input', {bubbles: true}));
  }
  c.querySelector('.compteur-moins').addEventListener('click', function () { changer(-pas); });
  c.querySelector('.compteur-plus').addEventListener('click', function () { changer(pas); });
});
