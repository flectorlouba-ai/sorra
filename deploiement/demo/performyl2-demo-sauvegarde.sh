#!/bin/bash
# Sauvegarde de nuit de la base de la DÉMONSTRATION (/etc/cron.d/performyl2-demo).
# /var/backups/performyl2-demo/performyl2_demo_AAAAMMJJ_HHMMSS.dump, conservés 14 jours.
set -o pipefail
BASE="performyl2_demo"
DOSSIER="/var/backups/performyl2-demo"
LOG="/var/log/performyl2-demo/sauvegarde.log"
FICHIER="${DOSSIER}/performyl2_demo_$(date +%Y%m%d_%H%M%S).dump"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "${LOG}"; }
mkdir -p "${DOSSIER}"; chmod 700 "${DOSSIER}"
if runuser -u postgres -- pg_dump --format=custom "${BASE}" > "${FICHIER}.partiel" && [ -s "${FICHIER}.partiel" ]; then
    mv "${FICHIER}.partiel" "${FICHIER}"; chmod 600 "${FICHIER}"
    log "OK — ${FICHIER} ($(du -h "${FICHIER}" | cut -f1))"
else
    rm -f "${FICHIER}.partiel"; log "ERREUR — la sauvegarde a échoué"; exit 1
fi
find "${DOSSIER}" -name 'performyl2_demo_*.dump' -mtime +13 -delete
