# Lot L — comptes de démonstration en un clic

- Sous « Se connecter », encadré « 🎓 Comptes de démonstration », en deux groupes (Pilotage, Terrain) : un clic remplit
  l'identifiant **et** le mot de passe, sans se connecter.
- Les comptes sont **lus en base** (comptes actifs) : rien d'inventé, un compte archivé disparaît.
- **Sécurité** : l'encadré n'existe que si `YL2_DEMO=1` et `SORRA_DEMO_COMPTES=1` sont dans le `.env` du serveur ;
  sinon aucun identifiant ni mot de passe dans la page (test). Protections de la démo inchangées (test).
- La version du service worker change automatiquement avec la page de connexion.
- Tests : `tests/test_lotL.py` (5) ; captures `docs/captures/lotL/`.

## À faire sur le serveur (une seule fois)
Ajouter `SORRA_DEMO_COMPTES=1` au `.env` de la démo, puis redémarrer le service (je n'ai pas le droit d'écrire un
fichier sur le serveur) :

```
ssh -i ~/.ssh/perform_yl_ed25519 root@187.124.217.218
echo "SORRA_DEMO_COMPTES=1" >> /var/www/performyl2-demo/.env
systemctl restart performyl2-demo
```

Déployé sur la démo : oui — version 2026-11-10-046d42b (encadré visible après la ligne ci-dessus).

## À tester
- **Téléphone et ordinateur**, page de connexion : l'encadré, un clic sur « agent.est », puis « Se connecter ».
