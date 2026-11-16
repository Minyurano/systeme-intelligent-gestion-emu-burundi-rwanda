# Journal des versions

Évolutions notables d'UMURAGE. La version est affichée en bas du menu de l'application et sur `/api/sante/`.
Le détail des versions 3.5 à 3.8 (espace membre, dîmes, sessions, proxy) est dans `docs/ANALYSE.md`.

## [3.9.2] — 2026-11-15

### Sécurité
- **Comptes de démonstration masqués en production.** La page de connexion affichait toujours les identifiants de
  test et le mot de passe `umurage2026`. Ils n'apparaissent plus qu'en mode démonstration (`UMURAGE_DEMO`, actif par
  défaut seulement quand `DJANGO_DEBUG=1`). `/api/sante/` indique ce mode (`"demo": true/false`).

### Nouveau
- **Démonstration en ligne** : `Dockerfile.demo` (base de démonstration préparée à la construction) et `render.yaml`
  pour publier une démonstration permanente sur Render. Le nom public fourni par Render est accepté automatiquement.

### Corrigé
- **Langue** : les rôles et descriptions des comptes de démonstration sont traduits (ils restaient en français dans
  l'interface anglaise).
- **Notifications** : au-delà de 9, la pastille affiche « 9+ » et ne déborde plus sur l'icône.
- **Couleurs** : le rouge n'est plus utilisé pour un district ou une catégorie ; il reste réservé aux alertes.
- **Dépôt** : `.venv/`, les archives (`.rar`, `.zip`) et les dossiers d'éditeur sont exclus par `.gitignore`.

## [3.9.1] — 2026-10-17

### Corrigé
- **Capteurs** : une organisation sans capteur voyait « Tous les capteurs sont dans leurs seuils normaux », ce qui
  laissait croire à une surveillance active. La page explique maintenant qu'aucun capteur n'est connecté et comment
  en brancher un (programme ESP32 fourni). Avec des capteurs, le message indique leur nombre.

## [3.9.0] — 2026-10-17

Fusion de la branche 3.8 (fonctions) et des corrections de sécurité et d'exploitation, plus l'analyse intelligente
de la comparaison des églises.

### Nouveau : comparaison des églises par apprentissage automatique
Onglet **Analyse intelligente (IA)** de la page Comparaison des églises (`GET /api/comparaison/analyse/`) :
- **Ce qu'il faut retenir** : phrases générées automatiquement, avec niveau de fiabilité selon le nombre d'entités.
- **Carte des églises** — analyse en composantes principales : un point par église, axes décrits en clair,
  noms placés sans chevauchement (les autres au survol), clic pour ouvrir la fiche.
- **Profils d'églises** — K-moyennes ; nombre de profils choisi par score de silhouette (le plus détaillé parmi les
  découpages presque aussi bons) ; nom, forces, points à renforcer et graphique en barres divergentes par profil.
- **Indice attendu** — régression ridge sur le contexte (taille, patrimoine, bénéficiaires), validation croisée
  « une église laissée de côté ». Si le contexte n'explique rien (R² < 0,15), l'analyse le dit et compare
  honnêtement à la moyenne des autres.
- **Profils atypiques** — réseau de neurones auto-encodeur (8-3-8), chaque église reconstruite par des réseaux
  entraînés sans elle (sinon une église hors norme serait apprise par cœur et jamais signalée).
- **Églises jumelles** — plus proches voisins par le contexte ; pour chaque église, un modèle comparable qui fait
  au moins 5 points de mieux, et les indicateurs précis où il fait mieux.
- **Fiche d'analyse** d'une église : ce que disent les cinq méthodes à son sujet.
- Nouveaux indicateurs : dîmes et offrandes par membre, part des membres inscrits au registre.
- Les indicateurs trop incomplets, constants ou presque identiques partout sont écartés, et la page dit pourquoi.

### Sécurité
- **Fichiers téléversés protégés.** Jusqu'à la 3.8, `/media/...` était servi à n'importe qui en production : un titre
  foncier ou la photo d'un fidèle s'ouvrait sans connexion. L'API remet maintenant des **liens signés et temporaires**
  (4 heures, `FICHIERS_LIEN_MINUTES`), liés au compte qui les a reçus et invalidés s'il est désactivé. Sans signature,
  l'en-tête Bearer reste accepté avec contrôle du périmètre (organisation, district, rôle). Les fichiers HTML, SVG, etc.
  sont toujours téléchargés, jamais affichés.
- **Production stricte** : refus de démarrer sans `DJANGO_ALLOWED_HOSTS` explicite (jamais `*`) ou avec une clé secrète
  de moins de 32 caractères. `manage.py check --deploy` ne signale plus rien. Docker Compose transmet le domaine de
  Caddy à Django.

### Exploitation
- Contrôle de santé de l'image Docker (`/api/sante/`, joignable en HTTP interne) ; Caddy attend que l'application soit prête.
- Suivi des erreurs facultatif avec Sentry ou GlitchTip (`SENTRY_DSN`), sans données personnelles.
- Journal technique daté ; erreurs 500 et alertes de sécurité toujours journalisées ; fichier tournant (`LOG_FICHIER`).
- Version visible dans l'interface, `/api/moi/` et `/api/sante/`.

### Qualité
- **Intégration continue GitHub Actions** : tests serveur sur PostgreSQL (les tests de concurrence y tournent enfin),
  contrôle des migrations, contrôle de sécurité du mode production, tests et construction de l'interface, image Docker.
- **20 nouveaux tests serveur** : liens signés, falsification, expiration, compte désactivé, périmètre, réglages de
  production, et analyse intelligente (dont une structure connue à l'avance que les méthodes doivent retrouver).
- **Premiers tests de l'interface** (Vitest, `npm test`) : formats, fiche d'analyse, placement des noms sur la carte.

### Mise à jour depuis la 3.8
1. `pip install -r requirements.txt` puis `python manage.py migrate` (aucune nouvelle table).
2. `npm ci` puis `npm run build` dans `frontend`.
3. En production, vérifier `DJANGO_ALLOWED_HOSTS` (ou `UMURAGE_DOMAINE` avec Docker) et une clé secrète d'au moins 32 caractères.

## [3.8] et précédentes
Voir `docs/ANALYSE.md` : espace membre (3.5), dîmes, mot de passe oublié, mineurs, sessions (3.6), adresse IP réelle
derrière un proxy (3.7), Caddy inclus (3.8).
