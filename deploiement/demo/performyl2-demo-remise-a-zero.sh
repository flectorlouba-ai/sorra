#!/bin/bash
# Remet la DÉMONSTRATION à zéro : sauvegarde, base recréée vide, migrations, données fictives rechargées
# (dates décalées à aujourd'hui), journal vide. À lancer À LA MAIN, en root :
#   /usr/local/bin/performyl2-demo-remise-a-zero.sh
set -euo pipefail
APP=/var/www/performyl2-demo
BASE=performyl2_demo
ROLE=performyl2_demo
grep -q '^YL2_DEMO=1' "$APP/.env" || { echo "Refusé : $APP/.env n'est pas une démonstration (YL2_DEMO=1)."; exit 1; }
echo "== Sauvegarde avant remise à zéro"
/usr/local/bin/performyl2-demo-sauvegarde.sh && ls -1t /var/backups/performyl2-demo | head -1
echo "== Arrêt du service"
systemctl stop performyl2-demo
echo "== Base recréée vide"
runuser -u postgres -- dropdb --if-exists "$BASE"
runuser -u postgres -- createdb -O "$ROLE" "$BASE"
cd "$APP"
lancer() { runuser -u performyl2-demo -- env $(grep -v '^#' .env | xargs) venv/bin/flask --app performyl2 "$@"; }
echo "== Migrations"
lancer db upgrade
echo "== Données fictives"
lancer demo-charger --adresse https://sorra.performyl.com
rm -rf "$APP/instance/rapports"
echo "== Redémarrage"
systemctl start performyl2-demo
sleep 2; curl -s -o /dev/null -w "  https://sorra.performyl.com/auth/connexion -> %{http_code}\n" https://sorra.performyl.com/auth/connexion
