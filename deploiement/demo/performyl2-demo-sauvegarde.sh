#!/bin/bash
# Sauvegarde de nuit de la base de la DÉMONSTRATION (/etc/cron.d/performyl2-demo).
# /var/backups/performyl2-demo/performyl2_demo_AAAAMMJJ_HHMMSS.dump, conservés 14 jours.
# Lot S : si /etc/sorra/sauvegarde.pub existe (clé publique GPG), la sauvegarde est CHIFFRÉE (.gpg) avec cette clé et la
# copie en clair n'est pas gardée ; si /etc/sorra/sauvegarde.conf définit DISTANT (ex. user@hote:/dossier), le .gpg est
# copié hors du serveur (scp). La clé privée reste chez le propriétaire, jamais sur le serveur.
set -o pipefail
BASE="performyl2_demo"
DOSSIER="/var/backups/performyl2-demo"
LOG="/var/log/performyl2-demo/sauvegarde.log"
CLE_PUBLIQUE="/etc/sorra/sauvegarde.pub"
CONF="/etc/sorra/sauvegarde.conf"
FICHIER="${DOSSIER}/performyl2_demo_$(date +%Y%m%d_%H%M%S).dump"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "${LOG}"; }
mkdir -p "${DOSSIER}"; chmod 700 "${DOSSIER}"
if runuser -u postgres -- pg_dump --format=custom "${BASE}" > "${FICHIER}.partiel" && [ -s "${FICHIER}.partiel" ]; then
    mv "${FICHIER}.partiel" "${FICHIER}"; chmod 600 "${FICHIER}"
    log "OK — ${FICHIER} ($(du -h "${FICHIER}" | cut -f1))"
else
    rm -f "${FICHIER}.partiel"; log "ERREUR — la sauvegarde a échoué"; exit 1
fi
if [ -r "${CLE_PUBLIQUE}" ] && command -v gpg >/dev/null; then
    if gpg --batch --yes --trust-model always --recipient-file "${CLE_PUBLIQUE}" --output "${FICHIER}.gpg" --encrypt "${FICHIER}"; then
        chmod 600 "${FICHIER}.gpg"; rm -f "${FICHIER}"; FICHIER="${FICHIER}.gpg"
        log "CHIFFRÉE — ${FICHIER}"
    else
        log "ERREUR — chiffrement impossible : la copie en clair reste sur le serveur"
    fi
else
    log "NON CHIFFRÉE — clé publique absente (${CLE_PUBLIQUE})"
fi
if [ -r "${CONF}" ]; then
    # shellcheck disable=SC1090
    . "${CONF}"
    if [ -n "${DISTANT}" ]; then
        if scp -q -o BatchMode=yes -o ConnectTimeout=20 "${FICHIER}" "${DISTANT}/"; then log "COPIÉE HORS SERVEUR — ${DISTANT}"; else log "ERREUR — copie hors serveur impossible (${DISTANT})"; fi
    fi
fi
find "${DOSSIER}" \( -name 'performyl2_demo_*.dump' -o -name 'performyl2_demo_*.dump.gpg' \) -mtime +13 -delete
