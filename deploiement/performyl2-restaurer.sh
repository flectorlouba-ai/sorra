#!/bin/bash
# Restauration d'une sauvegarde PERFORM YL.2.
#
#   performyl2-restaurer.sh <fichier.dump> <base_cible>
#
# - base_cible différente de « performyl2 » (ex. performyl2_essai) : crée cette base et y
#   restaure la sauvegarde. Sans risque pour la production : sert aux essais
#   et à consulter d'anciennes données.
# - base_cible = « performyl2 » : RESTAURATION DE LA PRODUCTION. Le service est
#   arrêté, la base actuelle est conservée sous le nom performyl2_avant_restauration_<date>
#   (rien n'est effacé), la sauvegarde est restaurée, puis le service redémarre.
set -euo pipefail

FICHIER="${1:-}"
CIBLE="${2:-}"
if [ -z "${FICHIER}" ] || [ -z "${CIBLE}" ] || [ ! -s "${FICHIER}" ]; then
    echo "Usage : $0 <fichier.dump> <base_cible>"
    echo "Sauvegardes disponibles :"; ls -1t /var/backups/performyl2/performyl2_*.dump 2>/dev/null | head -14
    exit 1
fi

psql_pg() { runuser -u postgres -- psql -v ON_ERROR_STOP=1 -Atq "$@"; }
existe() { [ "$(psql_pg -c "SELECT 1 FROM pg_database WHERE datname='$1'")" = "1" ]; }

if [ "${CIBLE}" = "performyl2" ]; then
    read -r -p "Restaurer la PRODUCTION à partir de $(basename "${FICHIER}") ? Tapez OUI : " REPONSE
    [ "${REPONSE}" = "OUI" ] || { echo "Abandon."; exit 1; }
    ANCIENNE="performyl2_avant_restauration_$(date +%Y%m%d_%H%M%S)"
    echo "1/5 Arrêt du service performyl2"; systemctl stop performyl2
    echo "2/5 Base actuelle conservée sous le nom ${ANCIENNE}"
    psql_pg -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='performyl2'" >/dev/null
    psql_pg -c "ALTER DATABASE performyl2 RENAME TO ${ANCIENNE}"
else
    if existe "${CIBLE}"; then
        echo "La base ${CIBLE} existe déjà : choisissez un autre nom, ou supprimez-la d'abord"
        echo "(runuser -u postgres -- dropdb ${CIBLE})."
        exit 1
    fi
fi

echo "3/5 Création de la base ${CIBLE}"
runuser -u postgres -- createdb -O performyl2 "${CIBLE}"
echo "4/5 Restauration de $(basename "${FICHIER}")"
runuser -u postgres -- pg_restore --no-owner --role=performyl2 --exit-on-error -d "${CIBLE}" < "${FICHIER}"

if [ "${CIBLE}" = "performyl2" ]; then
    echo "5/5 Redémarrage du service performyl2"; systemctl start performyl2
    echo "Terminé. L'ancienne base reste disponible sous le nom ${ANCIENNE}."
else
    echo "5/5 Terminé : sauvegarde restaurée dans la base ${CIBLE} (la production n'a pas été touchée)."
fi
