"""Condition de la relecture sur R-1b : le mot de passe provisoire d'un nouvel éleveur, gardé sur le téléphone
de l'agent pendant que le réseau manque, est EFFACÉ du téléphone dès que l'inscription est envoyée au serveur.
On exécute le vrai static/js/hors_ligne.js dans Node (téléphone simulé : tests/js/file_attente.js)."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
NODE = shutil.which('node')
pytestmark = pytest.mark.skipif(NODE is None, reason='Node absent : test du script du téléphone ignoré')


def telephone(reponse_du_serveur):
    sortie = subprocess.run([NODE, str(RACINE / 'tests' / 'js' / 'file_attente.js'),
                             str(RACINE / 'app' / 'static' / 'js' / 'hors_ligne.js'), reponse_du_serveur],
                            capture_output=True, text=True, timeout=60, encoding='utf-8')
    assert sortie.returncode == 0, sortie.stderr
    return json.loads(sortie.stdout)


@pytest.mark.parametrize('reponse', ['ok', 'deja', 'refuse'])
def test_mot_de_passe_efface_des_que_l_inscription_est_envoyee(reponse):
    r = telephone(reponse)
    assert r['envoye'] and r['mot_de_passe_envoye']          # il est bien parti au serveur…
    assert r['reste'] == []                                  # …et il n'est plus sur le téléphone


@pytest.mark.parametrize('reponse', ['coupure', 'connexion'])
def test_garde_tant_que_l_inscription_n_est_pas_arrivee(reponse):
    """Réseau coupé ou reconnexion demandée : rien n'est enregistré au serveur, la saisie reste à envoyer."""
    r = telephone(reponse)
    assert len(r['reste']) == 1 and ['provisoire', 'k7mq2wpa9x'] in r['reste'][0]['entrees']
