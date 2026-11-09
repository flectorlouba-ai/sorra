# SORRA — Correctif : affichage cassé après une mise à jour (cache du mode hors ligne)

**État :** corrigé, commit dédié. **Aucun déploiement.**

**Tests :** **276 tests réussis** et 1 réservé à PostgreSQL, dont 5 nouveaux dans `tests/test_mise_a_jour.py`.

## Ce qui se passait

Après le lot 9, l'accueil de l'éleveur s'affichait sans style : poulet géant en pleine largeur, tuiles réduites à une suite de liens.

**La cause :** le service worker du lot 8 gardait `eleveur.css` en « cache d'abord », toujours à la même adresse.

À la première ouverture après la mise à jour, c'est encore l'ancien service worker qui contrôle la page :
1. il sert l'ancienne feuille de style, qui ne connaît pas les tuiles ;
2. le nouveau service worker s'installe ensuite en arrière-plan, mais la page reste cassée tant qu'on ne la recharge pas à la main.

J'ai reproduit le problème à l'identique (capture A ci-dessous).

## Ce qui est corrigé

1. **Version automatique.**
   - La version de l'application est l'empreinte de tous les fichiers statiques et gabarits (`app/utils/statiques.py`). Elle change toute seule à chaque mise à jour, sans y penser.
   - Le service worker (`app/templates/sw.js`, servi par `/sw.js`) porte cette version. Les caches s'appellent `performyl2-statiques-<version>` et `performyl2-pages-<version>`.
   - Le navigateur relit `/sw.js` à chaque page, jamais depuis son cache (`no-store`, `updateViaCache: 'none'`, `update()`).
2. **Prise de main immédiate, puis rechargement.**
   - Le nouveau service worker prend la main tout de suite (`skipWaiting`, `clients.claim`).
   - Il **supprime tous les anciens caches** de l'application.
   - La page se **recharge une seule fois**, proprement (événement `controllerchange`). Ce rechargement n'a lieu que lors d'une mise à jour, jamais à la première visite.
3. **Fichiers appelés avec leur empreinte.**
   - Toutes les adresses de fichiers statiques sont versionnées : `eleveur.css?v=3f2a…`, `hors_ligne.js?v=…`, icônes, manifeste.
   - C'est automatique, par `url_for` : aucune adresse n'est à modifier à la main.
   - Un fichier modifié a une nouvelle adresse, qu'aucun ancien cache ne connaît.
4. **Stratégies de cache.**

   | Fichiers | Stratégie |
   |---|---|
   | Pages HTML, CSS, JS | **réseau d'abord**, la copie gardée seulement sans réseau |
   | Polices et images | cache d'abord : elles ne changent pas, ou changent d'adresse |

5. **Sécurité d'affichage.** Tous les SVG du poulet (logo, mascotte, poussin) ont maintenant `width` et `height` dans le HTML. Même sans feuille de style, ils ne s'affichent jamais en géant.

## Vérification du scénario réel (`docs/captures/correctif_cache/scenario_maj.py`)

Le même navigateur reste ouvert pendant toute l'opération :
1. l'éleveur utilise la **version du lot 8**, et le service worker en garde les fichiers ;
2. le serveur est **mis à jour** ;
3. l'éleveur rouvre l'accueil **sans rien faire d'autre**.

| Scénario | Premier affichage après la mise à jour | 5 s plus tard | Caches |
|---|---|---|---|
| **A** : lot 8 → lot 9 d'avant le correctif | poulet de **332 px**, tuiles en liens : **votre bug** | toujours cassé | l'ancien `v3` reste |
| **B** : lot 8 → version corrigée | **poulet de 44 px, tuiles en grille** | correct ; la page s'est rechargée une fois toute seule | anciens supprimés, seulement `…-45b83ed0e390` |

Captures :
- `docs/captures/correctif_cache/A_avant_correctif_page_sans_style.png` ;
- `docs/captures/correctif_cache/B_apres_correctif_premier_affichage.png`.

## Vider le cache sur votre poste (une seule fois, si besoin)

Avec cette version, ce ne devrait plus être nécessaire : à la prochaine ouverture, votre navigateur prend la nouvelle version tout seul et recharge la page une fois. Si l'affichage vous semble encore ancien :

**Chrome ou Edge, sur ordinateur :**
1. Ouvrez `http://127.0.0.1:5020`, puis appuyez sur **F12** (outils de développement).
2. Onglet **Application**, rubrique **Stockage**, bouton **« Effacer les données du site »**.
3. Fermez les outils, puis rechargez la page (**Ctrl + F5**).

Plus rapide, pour un simple contrôle : **Ctrl + Maj + N** (fenêtre privée). Elle ne garde aucun cache.

**Sur téléphone Android (Chrome) :**
1. Ouvrez Chrome, touchez **⋮**, puis **Paramètres**.
2. Allez dans **Paramètres des sites**, puis **Toutes les données des sites**.
3. Cherchez l'adresse de SORRA et touchez **Effacer et réinitialiser**.

Ces données sont seulement le stockage de la page sur le téléphone. Les saisies **en attente d'envoi** y sont aussi : effacez seulement quand le bandeau « ◷ » n'affiche rien en attente.

## Tests ajoutés (`tests/test_mise_a_jour.py`)

- La version et l'empreinte d'un fichier changent quand son contenu change.
- Le **nom des caches change avec la version**, et le service worker supprime les anciens caches (`skipWaiting`, `clients.claim`, `caches.delete`).
- `/sw.js` n'est jamais gardé par le navigateur ; ses fichiers sont versionnés ; CSS et JS sont en réseau d'abord ; seules les polices et images sont en cache d'abord.
- **Toutes les adresses `/static/…`** des pages de l'éleveur, et de la connexion, ont leur `?v=`.
- Tous les SVG du poulet ont `width` et `height`.
