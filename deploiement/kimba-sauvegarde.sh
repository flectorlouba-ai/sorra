#!/bin/bash
# Sauvegarde quotidienne de la base KIMBA (lancée par /etc/cron.d/kimba-sauvegarde).
# Fichiers : /var/backups/kimba/kimba_AAAAMMJJ_HHMMSS.dump (format pg_dump « custom »,
# compressé), conservés 14 jours. Journal : /var/log/kimba/sauvegarde.log
set -o pipefail

BASE="kimba"
DOSSIER="/var/backups/kimba"
CONSERVATION_JOURS=14
LOG="/var/log/kimba/sauvegarde.log"
FICHIER="${DOSSIER}/kimba_$(date +%Y%m%d_%H%M%S).dump"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "${LOG}"; }

mkdir -p "${DOSSIER}"
chmod 700 "${DOSSIER}"
log "Début de la sauvegarde"

if runuser -u postgres -- pg_dump --format=custom "${BASE}" > "${FICHIER}.partiel" \
   && [ -s "${FICHIER}.partiel" ]; then
    mv "${FICHIER}.partiel" "${FICHIER}"
    chmod 600 "${FICHIER}"
    log "OK — ${FICHIER} ($(du -h "${FICHIER}" | cut -f1))"
else
    rm -f "${FICHIER}.partiel"
    log "ERREUR — la sauvegarde a échoué"
    exit 1
fi

# Conservation : on garde les sauvegardes des 14 derniers jours
find "${DOSSIER}" -name 'kimba_*.dump' -mtime +$((CONSERVATION_JOURS - 1)) -delete
log "Sauvegardes conservées : $(find "${DOSSIER}" -name 'kimba_*.dump' | wc -l)"
