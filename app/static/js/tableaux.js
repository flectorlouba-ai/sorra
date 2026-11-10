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
  function lignes(table) { return Array.prototype.filter.call(table.tBodies[0] ? table.tBodies[0].rows : [], function (r) { return !r.classList.contains('table-vide') && !r.querySelector('td.table-vide') && r.getAttribute('data-filtre-cache') !== '1'; }); }

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


  // ── Lot K : filtres « Toutes / Province / Période / Recherche » du tableau conforme ──
  function filtres(wrap, table) {
    var barre = wrap.querySelector('.filtres-conformes');
    if (!barre) return;
    var rows = Array.prototype.filter.call(table.tBodies[0] ? table.tBodies[0].rows : [], function (r) { return !r.querySelector('td.table-vide'); });
    var nb = wrap.querySelector('[data-nb-lignes]');
    function appliquer() {
      var tous = (barre.querySelector('[data-filtre=tous]') || {}).value || '';
      var prov = (barre.querySelector('[data-filtre=province]') || {}).value || '';
      var per = parseInt((barre.querySelector('[data-filtre=periode]') || {}).value || '0', 10);
      var q = ((barre.querySelector('[data-filtre=recherche]') || {}).value || '').toLowerCase().trim();
      var alerteSeule = !!(barre.querySelector('[data-filtre=alerte]') || {}).checked;
      var limite = per ? Date.now() - per * 86400000 : 0, visibles = 0;
      rows.forEach(function (r) {
        var archivee = r.classList.contains('tr-archivee');
        var ok = tous === 'archives' ? archivee : !archivee;
        if (ok && alerteSeule && !r.classList.contains('tr-alerte')) ok = false;
        if (ok && prov && (r.getAttribute('data-province') || '') !== prov) ok = false;
        if (ok && limite) { var d = r.getAttribute('data-date'); ok = !!d && new Date(d).getTime() >= limite; }
        if (ok && q && texte(r).toLowerCase().indexOf(q) < 0) ok = false;
        r.setAttribute('data-filtre-cache', ok ? '' : '1');
        if (!ok) r.hidden = true;
        if (ok) visibles++;
      });
      if (nb) nb.textContent = visibles + ' ligne(s)';
      table.dataset.page = 1;
      paginer(table, wrap);
    }
    barre.querySelectorAll('select, input').forEach(function (e) { e.addEventListener('input', appliquer); e.addEventListener('change', appliquer); });
    var bf = barre.querySelector('[data-filtrer]'), br = barre.querySelector('[data-reinitialiser]');
    if (bf) bf.addEventListener('click', appliquer);
    if (br) br.addEventListener('click', function () {
      barre.querySelectorAll('select').forEach(function (s) { s.value = ''; });
      barre.querySelectorAll('input[type=search]').forEach(function (i) { i.value = ''; });
      barre.querySelectorAll('input[type=checkbox]').forEach(function (c) { c.checked = false; });
      appliquer();
    });
    appliquer();
  }

  // ── Lot V : habillage PERFORM YL.1 des cellules — nombres à droite, codes en chasse fixe, badges, lignes teintées, total ──
  var RE_NOMBRE = /^[-+]?\d{1,3}(?:[   ]?\d{3})*(?:[.,]\d+)?(?: ?(?:%|FCFA|t|kg|h|j|€))?$/;
  var RE_CODE = /^[A-Z]{2,5}-\d{2,}[A-Z0-9-]*$|^B\d{1,2}$|^(?:BD|LOT|CMD|LIV|ACT|SIG|RAP)-?\d+/;
  function habiller(table) {
    if (table.hasAttribute('data-habille')) return;
    table.setAttribute('data-habille', '1');
    var tete = entete(table);
    Array.prototype.forEach.call(table.tBodies[0] ? table.tBodies[0].rows : [], function (r) {
      if (r.querySelector('td.table-vide')) return;
      var premier = texte(r.cells[0] || {});
      if (/^total/i.test(premier)) r.classList.add('tr-total');
      Array.prototype.forEach.call(r.cells, function (td, i) {
        var t = texte(td), col = (tete[i] || '').toLowerCase();
        if (td.children.length === 0) {
          if (t === '⚠️' || (col === 'alerte' && t && t !== '—')) { td.innerHTML = '<span class="badge badge-danger">ALERTE</span>'; r.classList.add('tr-alerte'); }
          else if (/^hors programme$/i.test(t)) td.innerHTML = '<span class="badge badge-off">HORS PROGRAMME</span>';
          else if (/^(à surveiller|attention|surveiller)$/i.test(t)) { td.innerHTML = '<span class="badge badge-warn">SURVEILLER</span>'; r.classList.add('tr-surveiller'); }
          else if (/^(en alerte|alerte)$/i.test(t)) { td.innerHTML = '<span class="badge badge-danger">ALERTE</span>'; r.classList.add('tr-alerte'); }
          else if (/^-?\d+(?:[.,]\d+)? ?%$/.test(t)) {
            var v = nombre(t), ton = col.indexOf('mortalit') >= 0 ? (v >= 10 ? 'rouge' : v >= 5 ? 'orange' : 'vert') : (v >= 80 ? 'vert' : v >= 50 ? 'orange' : 'rouge');
            td.innerHTML = '<span class="badge-pct ' + ton + '">' + t + '</span>'; td.classList.add('td-nombre');
          }
          else if (RE_NOMBRE.test(t) && t !== '—') td.classList.add('td-nombre');
          else if (RE_CODE.test(t)) td.classList.add('td-code');
        } else {
          if (td.querySelector('.badge-danger')) r.classList.add('tr-alerte');
          else if (td.querySelector('.badge-warn')) r.classList.add('tr-surveiller');
          if (td.querySelector('a') && RE_CODE.test(t)) td.classList.add('td-code');
        }
        if (/^(nom|ferme|élevage|elevage|intitulé|intitule|titre|article)$/.test(col) && t && t !== '—') {
          td.classList.add('td-nom');
          if (td.children.length === 0 && r.hasAttribute('data-lien')) td.innerHTML = '<a class="lien-nom" href="' + r.getAttribute('data-lien') + '">' + td.innerHTML + '</a>';
        }
      });
    });
  }

  // ── Lot V : Excel / Imprimer du tableau unique de la page remontent dans l'en-tête de page ──
  function remonterOutils() {
    var zone = document.querySelector('[data-outils-page]');
    var outils = document.querySelectorAll('.table-wrap .outils-tableau');
    if (!zone || outils.length !== 1) return;
    var o = outils[0], ex = o.querySelector('[data-excel]'), im = o.querySelector('[data-imprimer]');
    if (im) zone.appendChild(im);
    if (ex) zone.appendChild(ex);
  }

  // ── Lot K : clic sur une ligne = fiche préremplie (un seul <template> par tableau) ──
  function remplir(form, donnees) {
    form.querySelectorAll('[data-champ]').forEach(function (el) {
      var v = donnees.valeurs ? donnees.valeurs[el.getAttribute('data-champ')] : undefined;
      if (v === undefined || v === null) v = '';
      if (el.tagName === 'OUTPUT') el.textContent = v === '' ? '—' : v;
      else if (el.tagName === 'SELECT') {
        el.value = v;
        if (el.value !== String(v)) { Array.prototype.some.call(el.options, function (o) { if (o.text === String(v)) { el.value = o.value; return true; } return false; }); }
      } else el.value = v;
    });
    if (donnees.action) form.setAttribute('action', donnees.action);
    var droits = donnees.droits || [];
    form.querySelectorAll('[data-bouton]').forEach(function (b) { b.hidden = droits.indexOf(b.getAttribute('data-bouton')) < 0; });
    var ls = form.querySelector('[data-lecture-seule]');
    if (droits.indexOf('modifier') < 0) {
      form.querySelectorAll('input:not([type=hidden]), select, textarea').forEach(function (i) { i.disabled = true; });
      if (ls) ls.hidden = false;
    }
    var pied = form.querySelector('[data-pied]');
    if (pied) pied.textContent = donnees.pied || '';
  }
  function ouvrirFicheLigne(tr) {
    var modele = document.getElementById(tr.getAttribute('data-fiche-modele')), f = document.getElementById('fen-fiche');
    if (!modele || !f) return;
    var donnees = {};
    try { donnees = JSON.parse(tr.getAttribute('data-ligne') || '{}'); } catch (e) {}
    if (!donnees.valeurs && tr.getAttribute('data-lien')) { location.href = tr.getAttribute('data-lien'); return; }
    var zone = f.querySelector('.fen-fiche-contenu');
    zone.innerHTML = '';
    zone.appendChild(modele.content.cloneNode(true));
    var form = zone.querySelector('form');
    if (form) remplir(form, donnees);
    document.getElementById('fen-fiche-titre').textContent = (donnees.titre || modele.getAttribute('data-titre') || '');
    var sous = document.getElementById('fen-fiche-sous');                 // lot V : sous-titre = la fonction du cahier
    if (sous) sous.textContent = donnees.titre ? (modele.getAttribute('data-titre') || '') : (modele.getAttribute('data-sous') || '');
    window.ouvrir('fen-fiche');
  }
  document.addEventListener('click', function (e) {
    if (e.target.closest('a, button, input, select, label')) return;
    var tr = e.target.closest('tr[data-fiche-modele]');
    if (tr) { ouvrirFicheLigne(tr); return; }
  });
  // Le bouton « ＋ … » de la zone titre ouvre la fenêtre de création du tableau de la page, vide (champs saisis seuls)
  var creation = document.querySelector('template[id^="creation-"]'), bp = document.querySelector('[data-bouton-creation]');
  if (bp && bp.hasAttribute('data-ouvrir-creation')) {
    var quoi = bp.getAttribute('data-ouvrir-creation');
    bp.addEventListener('click', function (e) {
      if (quoi === 'creation') {
        if (!creation) return;
        e.preventDefault();
        var f = document.getElementById('fen-fiche'), zone = f.querySelector('.fen-fiche-contenu');
        zone.innerHTML = '';
        zone.appendChild(creation.content.cloneNode(true));
        document.getElementById('fen-fiche-titre').textContent = creation.getAttribute('data-titre') || '';
        window.ouvrir('fen-fiche');
      } else if (document.getElementById(quoi)) { e.preventDefault(); if (quoi === 'fen-entree' && window.ouvrirEntree) window.ouvrirEntree(); else if (quoi === 'fen-user' && window.ouvrirCreation) window.ouvrirCreation(); else window.ouvrir(quoi); }
    });
    if (location.hash === '#ouvrir') { setTimeout(function () { bp.click(); }, 50); }
  }

  document.querySelectorAll('.table-wrap').forEach(function (wrap) {
    var table = wrap.querySelector('table');
    if (!table || !table.tHead) return;
    var outils = wrap.querySelector('.outils-tableau');
    if (!outils) {
      outils = document.createElement('div');
      outils.className = 'outils-tableau';
      outils.innerHTML = '<span>' + lignes(table).length + ' ligne(s)</span>' +
        '<button type="button" class="pr2 bs" data-imprimer>Imprimer</button>' +
        '<button type="button" class="xl bs" data-excel>Excel</button>';
      wrap.insertBefore(outils, wrap.firstChild);
    } else if (outils.hasAttribute('data-branche')) { return; }
    outils.setAttribute('data-branche', '1');
    outils.querySelector('[data-imprimer]').addEventListener('click', function () { imprimer(wrap, table); });
    outils.querySelector('[data-excel]').addEventListener('click', function () { excel(table); });
    habiller(table);
    filtres(wrap, table);
    Array.prototype.forEach.call(table.tHead.rows[0].cells, function (th, i) {
      if (!texte(th)) return;
      th.classList.add('triable');
      th.addEventListener('click', function (e) { if (e.target.closest('a, button')) return; trier(table, i, th, wrap); });
    });
    paginer(table, wrap);
  });
  remonterOutils();
})();
