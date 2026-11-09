#!/bin/bash
# SORRA — déploiement de la DÉMONSTRATION (https://sorra.performyl.com), partie serveur.
# Lancé par deploiement/demo/deployer.sh (poste) depuis le code extrait dans un dossier d'attente :
#   bash <attente>/deploiement/demo/deployer_serveur.sh <attente> <version>
# Toujours, dans l'ordre :
#   a) codes HTTP des autres applications ;  b) sauvegarde horodatée de la base de démo et du code ;
#   c) mise à jour du code ;  d) migrations sur une base temporaire (copie de la démo), puis sur la démo ;
#      rechargement des données fictives si le lot les a modifiées ;
#   e) redémarrage du SEUL service performyl2-demo (nginx n'est jamais touché) ;
#   f) contrôles : site, connexion d'un compte par profil, cache du service worker, journaux ;
#   g) autres applications : mêmes codes qu'en a). Toute erreur après b) : retour arrière automatique.
# Aucun secret n'est affiché : le .env reste sur le serveur, il n'est ni copié ni lu ici.
set -uo pipefail
set -E
ATTENTE=${1:?dossier du code à déployer}
VERSION=${2:?version}
APP=/var/www/performyl2-demo
SERVICE=performyl2-demo
SITE=https://sorra.performyl.com
BASE=performyl2_demo
ESSAI=performyl2_demo_essai
MDP_DEMO='Demo-yl2-2026'          # mot de passe PUBLIC des comptes fictifs (bandeau de la démo)
HORO=$(date +%Y%m%d_%H%M%S)
SAUVE=/var/backups/performyl2-demo/deploiement-$HORO
DEBUT=$(date '+%Y-%m-%d %H:%M:%S')
LIGNES_LOG=$(wc -l < /var/log/performyl2-demo/error.log 2>/dev/null || echo 0)
ETAPE=depart
CODE_CHANGE=0

titre() { printf '\n== %s\n' "$*"; }
echec() { echo "ÉCHEC ($ETAPE) : $*"; retour_arriere; exit 1; }
lancer() { runuser -u performyl2-demo -- env HOME=/tmp $(grep -v '^#' "$APP/.env" | xargs) "$@"; }

# ── a) Autres applications ─────────────────────────────────────────────
AUTRES="http://127.0.0.1:5010/ http://127.0.0.1:5011/ http://127.0.0.1:5020/ https://performyl.com/ https://www.performyl.com/ http://performyl.com/ https://recette.performyl.com/"
code_http() { curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$1"; }
releve() { for u in $AUTRES; do printf '%s=%s ' "$u" "$(code_http "$u")"; done; }
comparer() {
  # Un écart est revérifié 3 fois (5 s) avant d'être retenu : une lenteur passagère n'est pas une panne.
  local ecarts=""
  for u in $AUTRES; do
    local avant ok=0 n
    avant=$(printf '%s\n' $AVANT_CODES | grep -F "$u=" | cut -d= -f2-)
    for n in 1 2 3; do [ "$(code_http "$u")" = "$avant" ] && { ok=1; break; }; sleep 5; done
    [ $ok = 1 ] || ecarts="$ecarts $u(avant $avant, après $(code_http "$u"))"
  done
  echo "$ecarts"
}

# ── Retour arrière : code, base, service ───────────────────────────────
retour_arriere() {
  [ "$ETAPE" = depart ] || [ "$ETAPE" = a ] || [ "$ETAPE" = b ] && { echo "Rien à défaire (avant la mise à jour)."; return; }
  echo "== RETOUR ARRIÈRE vers l'état sauvegardé dans $SAUVE"
  systemctl stop "$SERVICE" || true
  if [ -f "$SAUVE/code.tgz" ]; then
    local tmp; tmp=$(mktemp -d)
    tar -xzf "$SAUVE/code.tgz" -C "$tmp"
    rsync -a --delete --exclude venv --exclude .env --exclude instance "$tmp/" "$APP/"
    rm -rf "$tmp"; chown -R performyl2-demo:performyl2-demo "$APP"
    runuser -u performyl2-demo -- env HOME=/tmp PIP_NO_CACHE_DIR=1 "$APP/venv/bin/pip" install -q -r "$APP/requirements.txt" || true
  fi
  if [ -f "$SAUVE/base.dump" ]; then
    runuser -u postgres -- dropdb --if-exists "$BASE"
    runuser -u postgres -- createdb -O performyl2_demo "$BASE"
    runuser -u postgres -- psql -q -c "REVOKE ALL ON DATABASE $BASE FROM PUBLIC"
    runuser -u postgres -- pg_restore --no-owner --role=performyl2_demo -d "$BASE" < "$SAUVE/base.dump" \
      && echo "  base restaurée"
  fi
  systemctl start "$SERVICE"; sleep 3
  echo "  service : $(systemctl is-active $SERVICE) ; site : $(code_http $SITE/auth/connexion)"
  echo "  autres applications : $(releve)"
}

# ── a) ─────────────────────────────────────────────────────────────────
ETAPE=a
titre "a) Codes HTTP des autres applications (avant)"
AVANT_CODES=$(releve)
echo "  $AVANT_CODES"
AVANT_SW=$(curl -s --max-time 10 "$SITE/sw.js" | grep -o "VERSION = '[^']*'" || true)

# ── b) ─────────────────────────────────────────────────────────────────
ETAPE=b
titre "b) Sauvegarde : $SAUVE"
mkdir -p "$SAUVE"; chmod 700 "$SAUVE"
runuser -u postgres -- pg_dump -Fc "$BASE" > "$SAUVE/base.dump" || { echo "pg_dump impossible : arrêt, rien n'est changé."; exit 1; }
tar --exclude=./venv --exclude=./.env --exclude='*/__pycache__' -czf "$SAUVE/code.tgz" -C "$APP" . \
  || { echo "copie du code impossible : arrêt, rien n'est changé."; exit 1; }
runuser -u postgres -- pg_restore -l < "$SAUVE/base.dump" > /dev/null || { echo "dump illisible : arrêt."; exit 1; }
echo "  base : $(du -h "$SAUVE/base.dump" | cut -f1) (relu), code : $(du -h "$SAUVE/code.tgz" | cut -f1)"
trap 'echec "erreur inattendue ligne $LINENO"' ERR
set -e

# ── c) ─────────────────────────────────────────────────────────────────
ETAPE=c
titre "c) Mise à jour du code ($VERSION)"
somme() { [ -f "$1" ] && sha256sum "$1" | cut -d' ' -f1 || echo absent; }
DONNEES_AVANT=$(somme "$APP/deploiement/demo/donnees_demo.json")
REQ_AVANT=$(somme "$APP/requirements.txt")
STATIQUES_AVANT=$(cd "$APP" && find app/static app/templates -type f | sort | xargs sha256sum | sha256sum | cut -d' ' -f1)
systemctl stop "$SERVICE"
rsync -a --delete --exclude venv --exclude .env --exclude instance --exclude __pycache__ "$ATTENTE/" "$APP/"
echo "$VERSION" > "$APP/VERSION"
chown -R performyl2-demo:performyl2-demo "$APP"
CODE_CHANGE=1
if [ "$(somme "$APP/requirements.txt")" != "$REQ_AVANT" ]; then
  echo "  bibliothèques modifiées : installation"
  runuser -u performyl2-demo -- env HOME=/tmp PIP_NO_CACHE_DIR=1 "$APP/venv/bin/pip" install -q -r "$APP/requirements.txt"
fi
STATIQUES_APRES=$(cd "$APP" && find app/static app/templates -type f | sort | xargs sha256sum | sha256sum | cut -d' ' -f1)
# Scripts d'exploitation de la démo (jamais nginx)
install -m 755 "$APP/deploiement/demo/performyl2-demo-sauvegarde.sh" /usr/local/bin/
install -m 755 "$APP/deploiement/demo/performyl2-demo-remise-a-zero.sh" /usr/local/bin/
install -m 644 "$APP/deploiement/demo/performyl2-demo.cron" /etc/cron.d/performyl2-demo

# ── d) ─────────────────────────────────────────────────────────────────
ETAPE=d
titre "d) Migrations : d'abord sur une copie temporaire de la base de démo"
runuser -u postgres -- dropdb --if-exists "$ESSAI"
runuser -u postgres -- createdb -O performyl2_demo "$ESSAI"
runuser -u postgres -- pg_restore --no-owner --role=performyl2_demo -d "$ESSAI" < "$SAUVE/base.dump"
URL_ESSAI=$(grep '^DATABASE_URL=' "$APP/.env" | cut -d= -f2- | sed "s#/$BASE\$#/$ESSAI#")
cd "$APP"
runuser -u performyl2-demo -- env HOME=/tmp $(grep -v '^#' .env | grep -v '^DATABASE_URL=' | xargs) DATABASE_URL="$URL_ESSAI" \
  venv/bin/flask --app performyl2 db upgrade 2>&1 | tail -1
runuser -u performyl2-demo -- env HOME=/tmp $(grep -v '^#' .env | grep -v '^DATABASE_URL=' | xargs) DATABASE_URL="$URL_ESSAI" \
  venv/bin/flask --app performyl2 db check 2>&1 | tail -1
runuser -u postgres -- dropdb "$ESSAI"
echo "  copie temporaire : migrations OK, supprimée"
titre "d) Migrations sur la base de démo"
lancer venv/bin/flask --app performyl2 db upgrade 2>&1 | tail -1
echo "  version de la base : $(lancer venv/bin/flask --app performyl2 db current 2>/dev/null | tail -1)"
if [ "$(somme "$APP/deploiement/demo/donnees_demo.json")" != "$DONNEES_AVANT" ]; then
  echo "  données fictives modifiées par ce lot : base recréée et rechargée (dates du jour, journal vide)"
  runuser -u postgres -- dropdb "$BASE"
  runuser -u postgres -- createdb -O performyl2_demo "$BASE"
  runuser -u postgres -- psql -q -c "REVOKE ALL ON DATABASE $BASE FROM PUBLIC"
  lancer venv/bin/flask --app performyl2 db upgrade 2>&1 | tail -1
  lancer venv/bin/flask --app performyl2 demo-charger --adresse "$SITE" 2>&1 | tail -1
  rm -rf "$APP/instance/rapports"
else
  echo "  données fictives inchangées : base gardée telle quelle"
fi

# ── e) ─────────────────────────────────────────────────────────────────
ETAPE=e
titre "e) Redémarrage du service $SERVICE (et de lui seul)"
systemctl start "$SERVICE"
for i in $(seq 1 20); do [ "$(code_http http://127.0.0.1:8008/auth/connexion)" = 200 ] && break; sleep 1; done
echo "  service : $(systemctl is-active $SERVICE)"

# ── f) ─────────────────────────────────────────────────────────────────
ETAPE=f
titre "f) Contrôles"
[ "$(code_http $SITE/auth/connexion)" = 200 ] || echec "$SITE ne répond pas"
PAGE=$(curl -s "$SITE/auth/connexion" || true)
grep -q 'DÉMONSTRATION — données fictives' <<< "$PAGE" || echec "bandeau de démonstration absent"
echo "  $SITE : 200, bandeau présent"
# Connexion d'un compte par profil (limite de débit nginx : 10 par minute, rafale de 5 → une requête toutes les 6,5 s)
COMPTES="admin:ADMIN dge:DGE agent.est:AGENT veto:VETO eleveur:ELEVEUR auditeur:AUDITEUR bceg:BCEG abattoir.owendo:OPERATEUR"
sleep 13
for paire in $COMPTES; do
  ident=${paire%%:*}; profil=${paire#*:}
  jarre=$(mktemp)
  PAGE=$(curl -s -c "$jarre" -b "$jarre" "$SITE/auth/connexion" || true)
  jeton=$(grep -o 'name="csrf_token" value="[^"]*"' <<< "$PAGE" | sed -n '1s/.*value="//;1s/"$//p' || true)
  sleep 6.5
  cible=$(curl -s -o /dev/null -w '%{http_code} %{redirect_url}' -c "$jarre" -b "$jarre" -e "$SITE/auth/connexion" \
          --data-urlencode "csrf_token=$jeton" --data-urlencode "identifiant=$ident" --data-urlencode "mot_de_passe=$MDP_DEMO" \
          "$SITE/auth/connexion")
  accueil=$(curl -s -L -o /dev/null -w '%{http_code}' -b "$jarre" -c "$jarre" "$SITE/")
  rm -f "$jarre"
  case "$cible" in 302*) [ "$accueil" = 200 ] && echo "  connexion $ident ($profil) : OK" || echec "connexion $ident : accueil $accueil" ;;
                   *) echec "connexion $ident ($profil) refusée : $cible" ;; esac
  sleep 6.5
done
APRES_SW=$(curl -s --max-time 10 "$SITE/sw.js" | grep -o "VERSION = '[^']*'" || true)
CACHE=$(curl -sI "$SITE/sw.js" | grep -i '^cache-control' | tr -d '\r' | cut -d' ' -f2- || true)
if [ "$STATIQUES_APRES" != "$STATIQUES_AVANT" ]; then
  [ "$APRES_SW" != "$AVANT_SW" ] && [ -n "$APRES_SW" ] || echec "service worker : version du cache inchangée ($APRES_SW)"
  echo "  service worker : $AVANT_SW → $APRES_SW (sw.js : $CACHE)"
else
  echo "  service worker : $APRES_SW, inchangé (aucun fichier statique ni gabarit modifié) (sw.js : $CACHE)"
fi
ERREURS=$(journalctl -u "$SERVICE" --since "$DEBUT" -p err --no-pager -q | wc -l || true)
TRACES=$(tail -n +$((LIGNES_LOG + 1)) /var/log/performyl2-demo/error.log 2>/dev/null | grep -ciE 'traceback|exception|\[error\]' || true)
[ "$ERREURS" = 0 ] && [ "${TRACES:-0}" = 0 ] || echec "journaux : $ERREURS erreur(s) systemd, ${TRACES:-0} trace(s) dans error.log"
echo "  journaux : aucune erreur depuis $DEBUT"

# ── g) ─────────────────────────────────────────────────────────────────
ETAPE=g
titre "g) Autres applications (après)"
ECARTS=$(comparer)
[ -z "$ECARTS" ] || echec "autres applications changées :$ECARTS"
echo "  mêmes codes qu'avant : $(releve)"
trap - ERR
titre "Déployé : $VERSION (sauvegarde : $SAUVE)"
