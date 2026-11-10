"""Lot T — génère une paire de clés VAPID (Web Push) et affiche les deux lignes à coller dans le .env du serveur.
Usage : venv/bin/python deploiement/outils/cles_vapid.py
Les clés ne vont JAMAIS dans git : seulement dans le .env."""
import base64

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid

v = Vapid()
v.generate_keys()
privee = v.private_key.private_numbers().private_value.to_bytes(32, 'big')
publique = v.public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
print('SORRA_VAPID_PRIVEE=' + base64.urlsafe_b64encode(privee).rstrip(b'=').decode())
print('SORRA_VAPID_PUBLIQUE=' + base64.urlsafe_b64encode(publique).rstrip(b'=').decode())
print('SORRA_VAPID_CONTACT=mailto:contact@performyl.com')
