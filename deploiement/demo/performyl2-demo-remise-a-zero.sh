#!/bin/bash
# Remet la DÉMONSTRATION à zéro : sauvegarde vérifiée, base recréée vide, migrations, jeu de données complet (lot J :
# 150 élevages, 12 mois, daté par rapport à aujourd'hui), journal neuf (chaîne d'intégrité valide). À lancer À LA MAIN,
# en root :
#   /usr/local/bin/performyl2-demo-remise-a-zero.sh            → jeu complet (flask demo-jeu-complet)
#   /usr/local/bin/performyl2-demo-remise-a-zero.sh --ancien   → ancien petit jeu (deploiement/demo/donnees_demo.json)
# Ne touche QUE la base performyl2_demo et le service performyl2-demo.
set -euo pipefail
APP=/var/www/performyl2-demo
BASE=performyl2_demo
ROLE=performyl2_demo
DOSSIER=/var/backups/performyl2-demo
grep -q '^YL2_DEMO=1' "$APP/.env" || { echo "Refusé : $APP/.env n'est pas une démonstration (YL2_DEMO=1)."; exit 1; }
grep -q "/${BASE}\$\|/${BASE}?" <(grep '^DATABASE_URL=' "$APP/.env") || { echo "Refusé : DATABASE_URL ne désigne pas la base ${BASE}."; exit 1; }

echo "== Sauvegarde complète avant remise à zéro (vérifiée avec pg_restore -l)"
mkdir -p "$DOSSIER"; chmod 700 "$DOSSIER"
FICHIER="$DOSSIER/avant_remise_a_zero_$(date +%Y%m%d_%H%M%S).dump"
runuser -u postgres -- pg_dump --format=custom "$BASE" > "$FICHIER"
chmod 600 "$FICHIER"
N=$(pg_restore -l "$FICHIER" | grep -c 'TABLE DATA' || true)
[ "$N" -gt 0 ] || { echo "Refusé : la sauvegarde $FICHIER est illisible ou vide."; exit 1; }
echo "  $FICHIER ($(du -h "$FICHIER" | cut -f1), $N tables)"

echo "== Arrêt du service"
systemctl stop performyl2-demo
echo "== Base recréée vide"
runuser -u postgres -- dropdb --if-exists "$BASE"
runuser -u postgres -- createdb -O "$ROLE" "$BASE"
cd "$APP"
lancer() { runuser -u performyl2-demo -- env $(grep -v '^#' .env | xargs) venv/bin/flask --app performyl2 "$@"; }
echo "== Migrations"
lancer db upgrade
rm -rf "$APP/instance/rapports" "$APP/instance/televersements/sante"/demo_*.png
if [ "${1:-}" = "--ancien" ]; then
    echo "== Données fictives (ancien jeu)"
    lancer demo-charger --adresse https://sorra.performyl.com
else
    echo "== Jeu de données complet (lot J)"
    lancer demo-jeu-complet --adresse https://sorra.performyl.com
fi
echo "== Redémarrage"
systemctl start performyl2-demo
sleep 3; curl -s -o /dev/null -w "  https://sorra.performyl.com/auth/connexion -> %{http_code}\n" https://sorra.performyl.com/auth/connexion
