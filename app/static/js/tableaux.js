/* SORRA — tableaux de la version ordinateur (lot R, docs/regles_lots.md) :
 *  - tri par clic sur l'en-tête de colonne ;
 *  - pagination au-delà de 50 lignes ;
 *  - « 🖨️ Imprimer » : aperçu A4 paysage (en-tête SORRA, titre, filtres, date, nom), window.print ; journalisé ;
 *  - « ⬇️ Excel » : .xlsx des lignes affichées (déjà filtrées par le périmètre), toutes colonnes, construit par le
 *    serveur (/bureau/exports/tableau.xlsx) et journalisé.
 * Aucune bibliothèque externe. */
(function () {
  'use strict';
  var corps = document.body;
  if (!corps.classList.contains('bureau')) return;
  var PAGE = 50, csrf = (document.querySelector('meta[name=csrf-token]') || {}).content || '';

  function texte(td) { return (td.textContent || '').replace(/\s+/g, ' ').trim(); }
  function nombre(t) {
    var n = parseFloat(t.replace(/ |\s/g, '').replace(/[^0-9,.\-]/g, '').replace(',', '.'));
    return isNaN(n) ? null : n;
  }
  function lignes(table) { return Array.prototype.filter.call(table.tBodies[0] ? table.tBodies[0].rows : [], function (r) { return !r.classList.contains('table-vide') && !r.querySelector('td.table-vide'); }); }

  function paginer(table, zone) {
    var rows = lignes(table), n = rows.length;
    var ancienne = zone.querySelector('.pagination-tableau');
    if (ancienne) ancienne.remove();
    if (n <= PAGE) { rows.forEach(function (r) { r.hidden = false; }); return; }
    var pages = Math.ceil(n / PAGE), courante = +(table.dataset.page || 1);
    rows.forEach(function (r, i) { r.hidden = Math.floor(i / PAGE) + 1 !== courante; });
    var nav = document.createElement('div');
    nav.className = 'pagination-tableau';
    nav.appendChild(document.createTextNode(n + ' lignes · page '));
    for (var p = 1; p <= pages; p++) {
      var b = document.createElement('button');
      b.type = 'button'; b.textContent = p; if (p === courante) b.className = 'on';
      b.addEventListener('click', (function (p) { return function () { table.dataset.page = p; paginer(table, zone); }; })(p));
      nav.appendChild(b);
    }
    zone.appendChild(nav);
  }

  function trier(table, idx, th, zone) {
    var asc = !th.classList.contains('tri-asc');
    Array.prototype.forEach.call(table.tHead.rows[0].cells, function (c) { c.classList.remove('tri-asc', 'tri-desc'); });
    th.classList.add(asc ? 'tri-asc' : 'tri-desc');
    var rows = lignes(table), tbody = table.tBodies[0];
    rows.sort(function (a, b) {
      var ta = texte(a.cells[idx] || {}), tb = texte(b.cells[idx] || {});
      var na = nombre(ta), nb = nombre(tb), r;
      if (na !== null && nb !== null && /^[\d\s.,%\-]+$/.test(ta) && /^[\d\s.,%\-]+$/.test(tb)) r = na - nb;
      else r = ta.localeCompare(tb, 'fr', {numeric: true, sensitivity: 'base'});
      return asc ? r : -r;
    });
    rows.forEach(function (r) { tbody.appendChild(r); });
    table.dataset.page = 1;
    paginer(table, zone);
  }

  function entete(table) {
    return Array.prototype.map.call(table.tHead ? table.tHead.rows[0].cells : [], function (c) { return texte(c).replace(/ [↕↑↓]$/, ''); });
  }
  function donnees(table) {
    return lignes(table).map(function (r) { return Array.prototype.map.call(r.cells, texte); });
  }
  function titrePage() {
    var t = document.querySelector('.zone-titre h1, .page-title');
    return t ? texte(t) : document.title;
  }
  function filtresActifs() {
    var f = [];
    document.querySelectorAll('.filters-bar select, .filters-bar input').forEach(function (e) {
      if (!e.value) return;
      var lib = e.tagName === 'SELECT' ? e.options[e.selectedIndex].text : e.value;
      f.push(lib);
    });
    return f.join(' · ') || 'aucun filtre';
  }

  function imprimer(wrap, table) {
    var ancien = document.querySelector('.en-tete-impression');
    if (ancien) ancien.remove();
    var h = document.createElement('div');
    h.className = 'en-tete-impression';
    var qui = document.querySelector('.zone-titre .qui b');
    h.innerHTML = '<b>🐔 SORRA</b> — ' + titrePage() + '<br>Filtres : ' + filtresActifs() + ' · Imprimé le ' +
      new Date().toLocaleString('fr-FR') + (qui ? ' par ' + texte(qui) : '');
    var zone = document.querySelector('.droite-zone') || corps;
    zone.insertBefore(h, zone.firstChild);
    document.querySelectorAll('.table-wrap').forEach(function (w) { w.classList.toggle('a-imprimer', w === wrap); });
    lignes(table).forEach(function (r) { r.hidden = false; });
    corps.classList.add('impression-tableau');
    fetch('/bureau/exports/impression', {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf},
      body: JSON.stringify({titre: titrePage(), lignes: lignes(table).length})}).catch(function () {});
    window.print();
    corps.classList.remove('impression-tableau');
    paginer(table, wrap);
  }

  function excel(table) {
    var form = document.createElement('form');
    form.method = 'POST'; form.action = '/bureau/exports/tableau.xlsx'; form.style.display = 'none';
    function champ(n, v) { var i = document.createElement('input'); i.type = 'hidden'; i.name = n; i.value = v; form.appendChild(i); }
    champ('csrf_token', csrf);
    champ('titre', titrePage());
    champ('filtres', filtresActifs());
    champ('donnees', JSON.stringify({colonnes: entete(table), lignes: donnees(table)}));
    document.body.appendChild(form); form.submit(); form.remove();
  }

  document.querySelectorAll('.table-wrap').forEach(function (wrap) {
    var table = wrap.querySelector('table');
    if (!table || !table.tHead || wrap.querySelector('.outils-tableau')) return;
    var outils = document.createElement('div');
    outils.className = 'outils-tableau';
    outils.innerHTML = '<span>' + lignes(table).length + ' ligne(s)</span>' +
      '<button type="button" class="pr2" data-imprimer>🖨️ Imprimer</button>' +
      '<button type="button" class="xl" data-excel>⬇️ Excel</button>';
    wrap.insertBefore(outils, wrap.firstChild);
    outils.querySelector('[data-imprimer]').addEventListener('click', function () { imprimer(wrap, table); });
    outils.querySelector('[data-excel]').addEventListener('click', function () { excel(table); });
    Array.prototype.forEach.call(table.tHead.rows[0].cells, function (th, i) {
      if (!texte(th)) return;
      th.classList.add('triable');
      th.addEventListener('click', function (e) { if (e.target.closest('a, button')) return; trier(table, i, th, wrap); });
    });
    paginer(table, wrap);
  });
})();
