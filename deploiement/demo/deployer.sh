#!/bin/bash
# SORRA — déploiement de la DÉMONSTRATION (https://sorra.performyl.com), à lancer depuis le poste (Git Bash) :
#   bash deploiement/demo/deployer.sh
# Conditions : branche main, rien à valider, main déjà poussé sur GitHub (origin/main = main).
# Envoie le code de main (git archive, sans .env ni base) dans un dossier d'attente sur le serveur, puis lance
# deploiement/demo/deployer_serveur.sh, qui fait tout le reste (sauvegarde, migrations, service, contrôles,
# retour arrière automatique). Voir docs/exploitation.md, « Déployer la démonstration ».
# Accès : clé SSH du poste (VPS_SSH_KEY, par défaut ~/.ssh/perform_yl_ed25519) ; aucun mot de passe ici.
set -euo pipefail
HOTE=${VPS_HOTE:-root@187.124.217.218}
CLE=${VPS_SSH_KEY:-$HOME/.ssh/perform_yl_ed25519}
SSH=(ssh -i "$CLE" -o BatchMode=yes "$HOTE")
cd "$(git rev-parse --show-toplevel)"

[ "$(git branch --show-current)" = main ] || { echo "Déploiement refusé : se placer sur main."; exit 1; }
[ -z "$(git status --porcelain)" ] || { echo "Déploiement refusé : des modifications ne sont pas validées."; exit 1; }
git fetch -q origin main
[ "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)" ] || { echo "Déploiement refusé : main n'est pas poussé sur GitHub."; exit 1; }

VERSION="$(date +%Y-%m-%d)-$(git rev-parse --short HEAD)"
ETIQUETTE="demo-$(date +%Y%m%d-%H%M)"
ATTENTE="/root/sorra-deploiement/$VERSION"
ARCHIVE=$(mktemp)
git archive --format=tar.gz -o "$ARCHIVE" HEAD
echo "== Envoi de main ($VERSION) vers le serveur"
"${SSH[@]}" "rm -rf '$ATTENTE' && mkdir -p '$ATTENTE'"
"${SSH[@]}" "tar -xzf - -C '$ATTENTE'" < "$ARCHIVE"
rm -f "$ARCHIVE"
# La partie serveur tourne détachée (setsid nohup) avec son journal : une coupure du réseau entre le poste et le
# serveur ne l'interrompt pas (incident du 09/11/2026). Le poste lit ensuite le journal jusqu'à la fin.
JOURNAL="/root/sorra-deploiement/journaux/$VERSION.log"
"${SSH[@]}" "mkdir -p /root/sorra-deploiement/journaux && setsid nohup bash '$ATTENTE/deploiement/demo/deployer_serveur.sh' '$ATTENTE' '$VERSION' > '$JOURNAL' 2>&1 < /dev/null & echo \$! > '$JOURNAL.pid'"
set +e
LUS=0
while true; do
  sleep 10
  ETAT=$("${SSH[@]}" -o ConnectTimeout=15 "tail -n +$((LUS + 1)) '$JOURNAL'; echo '@@'; wc -l < '$JOURNAL'; kill -0 \$(cat '$JOURNAL.pid') 2>/dev/null && echo encours || echo fini" 2>/dev/null) || { echo '  (réseau coupé : le déploiement continue sur le serveur, nouvel essai…)'; continue; }
  printf '%s\n' "${ETAT%%@@*}" | sed '/^$/d'
  LUS=$(printf '%s\n' "${ETAT##*@@}" | sed -n '2p')
  printf '%s\n' "$ETAT" | tail -n 1 | grep -q fini && break
done
"${SSH[@]}" "grep -q '^== Déployé : ' '$JOURNAL'"
CODE=$?
set -e
"${SSH[@]}" "rm -rf '$ATTENTE'; ls -1dt /root/sorra-deploiement/2* 2>/dev/null | tail -n +4 | xargs -r rm -rf" || true
if [ $CODE = 0 ]; then
  git tag -a "$ETIQUETTE" -m "Démonstration déployée : $VERSION" && git push -q origin "$ETIQUETTE"
  echo "== Déployé sur la démo : oui — version $VERSION (étiquette $ETIQUETTE)"
else
  echo "== Déployé sur la démo : NON — retour arrière fait par le serveur (voir ci-dessus)"
fi
exit $CODE
