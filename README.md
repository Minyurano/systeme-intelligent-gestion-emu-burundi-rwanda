# UMURAGE

**Plateforme libre de gestion du patrimoine et de l'impact des Églises et des organisations communautaires.**

*Umurage* signifie « héritage » en kirundi : gérer fidèlement aujourd'hui ce que l'on transmettra demain.
Conçue d'abord pour l'Église Méthodiste Unie du Burundi, UMURAGE accueille sur une même installation
autant d'organisations que nécessaire, chacune avec ses données, sa monnaie et sa langue.

> **Données de démonstration.** Les districts, paroisses, projets et partenaires de l'EMU Burundi viennent
> de son rapport institutionnel. Les montants, surfaces, transactions, ventes de référence et mesures de
> capteurs sont **fictifs**, comme l'ensemble de l'organisation « EMU Rwanda » de démonstration.

---

## Démarrer en une commande

Prérequis : **Python 3.11+** et **Node.js 18+**.

**Windows** (PowerShell, dans le dossier `umurage`) :

```powershell
powershell -ExecutionPolicy Bypass -File .\demarrer-windows.ps1
```

**Linux ou macOS** : `sh demarrer.sh`

Le script installe ce qui manque, met à jour la base de données, construit l'interface et ouvre
**http://localhost:8000**. Un seul serveur sert l'interface et l'API.

| Identifiant (mot de passe `umurage2026`) | Rôle |
|---|---|
| `eveque` | Direction : voit et pilote tout le patrimoine |
| `tresorier` | Finances et contrôle des anomalies |
| `surintendant.gitega` | Limité au district de Gitega, valide les déclarations |
| `agent.burunga` | Recense les biens de Burunga, déclare par WhatsApp |
| `admin` | Comptes, rôles, districts, intégrations |
| `admin.rwanda` | Deuxième organisation (en anglais, en RWF) : données totalement séparées |
| `membre.kayero` | **Membre de l'Église** (Esther, Kayero) : espace membre uniquement, aucun outil de gestion |

Vous aviez déjà installé la version 1 ? Vos données sont conservées : la mise à jour les rattache automatiquement
à l'organisation « EMU Burundi ». Pour voir aussi la démonstration complète (organisation Rwanda, déclarations
WhatsApp), lancez une fois `python manage.py seed_demo --reset` dans `backend` : **cela remplace les données
existantes par les données de démonstration**.

---

## Ce que fait UMURAGE

### Recenser
- **Inventaire** : terrains, bâtiments, forages, équipements, véhicules, cheptel. Code unique et **QR code** par bien.
- **Déclarations par WhatsApp** : un pasteur écrit « Nouveau forage à Muyange, bon état, financé par UMCOR »,
  envoie une photo ou un message vocal. UMURAGE comprend le message, reconnaît s'il concerne un **bien existant**
  (« le toit de l'école de Nyabugogo fuit »), et le surintendant valide en un clic. L'auteur reçoit la confirmation
  sur WhatsApp. Commandes : `AIDE`, `ETAT BRG-INF-0001`. Un **simulateur** intégré permet de tout essayer sans compte Meta.
- **Import depuis Excel ou CSV** : colonnes reconnues automatiquement, aperçu ligne par ligne, modèle Excel pré-rempli.
- **Mode hors ligne** : l'application s'installe sur le téléphone, s'ouvre sans réseau avec les dernières données,
  et les biens enregistrés hors ligne sont envoyés au retour de la connexion.

### Comprendre
- **Tableau de bord** : valeur du patrimoine par district, terrains sans titre, biens à risque, objectif santé 2030, ODD.
- **Valorisation par IA explicable** : un modèle par organisation (chaque marché et chaque monnaie est différent),
  avec fourchette et facteurs de l'estimation.
- **Risque et maintenance prédictive**, **détection d'anomalies financières** expliquées, **prévisions** sur six mois.
- **Capteurs IoT** (forages, chaîne du froid) et **assistant** qui répond en citant ses sources.
- **Comparaison intelligente des églises** (nouveau en 3.9) : l'onglet *Analyse intelligente (IA)* de la page
  Comparaison des églises explique le classement par apprentissage automatique, avec des graphiques et des phrases simples.
  Voir plus bas « Nouveautés 3.9 ».

### Rendre des comptes
- **Rapport du patrimoine** imprimable en PDF, pour l'organisation entière ou **par district**.
- **Qualité des données** : score de complétude et **classement des districts**, fiches à compléter en priorité.
- **Export IATI 2.03** des projets : le standard de transparence de l'aide internationale, lu par les bailleurs.
- **Export comptable** des transactions pour l'audit.
- **Portail public** par organisation (`/public/emu-burundi`), sans donnée financière ni titre de propriété.
- **Journal d'audit scellé** (chaîne d'empreintes SHA-256) : toute falsification est détectée.

### Gérer au quotidien
- **Approbations** : cession, acquisition, transfert, travaux et dépenses passent par un circuit (surintendant, trésorier,
  évêque selon le montant). Personne ne valide sa propre demande ; l'exécution met à jour l'inventaire et les finances.
- **Échéancier** : assurances, impôts, titres, contrôles, fins de bail, documents qui expirent ; rappels WhatsApp à J-30, J-7 et en cas de retard.
- **Locations et loyers** : baux, loyers mensuels générés automatiquement, encaissements rattachés au bien, impayés.
- **Maintenance** : ordres de travail, entretien préventif, fournisseurs ; les biens à risque élevé reçoivent une inspection automatique.
- **Comptabilité du patrimoine** : budget comparé au réalisé, registre des immobilisations et amortissements, rapprochement bancaire, clôture d'exercice.
- **Inventaire physique** : campagnes de scan des QR codes sur le terrain, écarts et procès-verbal.
- **Double authentification** pour les comptes sensibles, page de supervision `/api/sante/`, restauration des sauvegardes.

Détails : [docs/ANALYSE.md](docs/ANALYSE.md) (analyse et manques), [docs/MODULES_METIER.md](docs/MODULES_METIER.md), [docs/EXPLOITATION.md](docs/EXPLOITATION.md),
[docs/REPRISE_DONNEES.md](docs/REPRISE_DONNEES.md).

### Passer à l'échelle
- **Multi-organisations** : chaque Église a son espace, sa monnaie (BIF, RWF, KES…), sa langue et son portail.
  Le cloisonnement est vérifié par des tests automatiques.
- **Inscription en libre-service** (`/inscription`) : une nouvelle Église crée son espace sans intervention.
- **Comptes des responsables** gérés par l'administrateur : rôles, district, numéro WhatsApp, désactivation.

### Ouvrir UMURAGE aux fidèles (nouveau en 3.5)
- **Accès des membres** : les administrateurs donnent l'accès à l'espace membre aux fidèles inscrits au registre,
  un par un (depuis le registre ou la page *Accès des membres*) ou pour toute une église locale. Identifiant = numéro de
  membre, mot de passe provisoire à changer à la première connexion, **fiches d'accès imprimables** et envoi par WhatsApp.
  Suspendre, rétablir, nouveau mot de passe, retirer : tout est inscrit au journal d'audit.
- **Demandes d'accès** : un fidèle demande lui-même l'accès (`/demande-acces`) avec son numéro de membre et son
  téléphone ; la demande est marquée « vérifiée » quand ils correspondent à la fiche. Un administrateur décide.
  Le formulaire ne révèle jamais si une personne est inscrite. Option activable dans *Réglages*.
- **Espace membre** (`/membre`, pensé pour le téléphone) : sa fiche et sa carte de membre, ses coordonnées qu'il
  corrige lui-même, son église locale (pasteur, communauté, biens sans valeurs financières, projets publics du district),
  et ses **signalements** (« le toit fuit », avec photo) qui suivent le circuit de validation des déclarations.
- **Sécurité** : la permission par défaut de toute l'API refuse le rôle MEMBRE ; seules l'espace membre, le profil, le mot
  de passe et la double authentification lui sont ouverts. Un membre transféré ou décédé perd automatiquement son accès.
  Tout utilisateur peut maintenant changer son mot de passe (page *Sécurité du compte*).

### Nouveautés 3.6
- **Dîmes et offrandes** : saisie rapide du dimanche, reçus numérotés imprimables, recette créée en comptabilité,
  annulation motivée (jamais de suppression), synthèse mensuelle comparée à l'année précédente. Dans l'espace membre,
  « Mes dons » et une **attestation annuelle** avec QR code, vérifiable par n'importe qui sur `/verifier/CODE`.
- **Mot de passe oublié** en libre-service : code à 6 chiffres par WhatsApp ou par e-mail, 10 minutes, 5 essais.
- **Mineurs** : sous l'âge fixé par l'Église (16 ans par défaut), l'accès demande l'accord d'un parent ou tuteur, enregistré.
- **Sessions plus sûres** : jeton de rafraîchissement en cookie HttpOnly, jeton d'accès de 15 minutes gardé en mémoire,
  rotation et révocation (déconnexion, changement de mot de passe, suspension).
- **Adresse IP réelle derrière un proxy** (`UMURAGE_NUM_PROXIES`) : les limites de tentatives ne se contournent plus
  en falsifiant l'en-tête `X-Forwarded-For` ; contrôle au démarrage et page de diagnostic pour l'administrateur.
- **Écritures simultanées** : le journal d'audit et les numéros (membres, reçus) sont attribués sous verrou ;
  c'est vérifié par un test de concurrence sur PostgreSQL.
- **Interface en français et en anglais**, prête à recevoir d'autres langues.

### Nouveautés 3.9
- **Comparaison des églises par apprentissage automatique** (onglet *Analyse intelligente (IA)*) :
  - **Ce qu'il faut retenir** : 3 à 5 phrases générées automatiquement, avec un niveau de fiabilité.
  - **Carte des églises** (analyse en composantes principales) : chaque église est un point, deux points proches
    se ressemblent ; chaque axe est décrit en clair.
  - **Profils d'églises** (K-moyennes, nombre de groupes choisi par score de silhouette) : nom, forces, points à
    renforcer et graphique « mieux / moins bien que la moyenne » pour chaque profil.
  - **Indice attendu** (régression ridge en validation croisée) : à contexte égal, quelle église gère mieux ou moins
    bien que prévu. Quand le contexte n'explique rien, l'analyse le dit et compare à la moyenne des autres.
  - **Profils atypiques** (réseau de neurones auto-encodeur 8-3-8, validation croisée) : les églises qui ne
    ressemblent à aucune autre, avec la raison (erreur de saisie à vérifier ou situation exceptionnelle).
  - **Églises jumelles** (plus proches voisins) : pour chaque église, une église comparable qui fait mieux, et les
    points précis où elle fait mieux, pour organiser l'entraide.
  - **Fiche d'analyse** d'une église : ce que disent les cinq méthodes à son sujet, en quelques phrases.
  - Nouveaux indicateurs de comparaison : **dîmes et offrandes par membre** et **part des membres inscrits au registre**.
- **Fichiers protégés** : titres fonciers, contrats, photos des membres et vocaux ne sont plus jamais publics.
  L'API remet des **liens signés et temporaires** (4 heures), réservés à la personne autorisée.
- **Production stricte** : refus de démarrer sans domaine déclaré (`DJANGO_ALLOWED_HOSTS`, jamais `*`) ou avec une
  clé secrète faible ; contrôle de santé Docker ; Caddy attend que l'application soit prête.
- **Suivi des erreurs** (Sentry ou GlitchTip, facultatif) et journal technique daté.
- **Intégration continue GitHub** : tests sur PostgreSQL (y compris les tests de concurrence), contrôle de sécurité
  du mode production, tests de l'interface (Vitest), construction de l'image Docker.

---

## Architecture

```
  TERRAIN                         SERVEUR UNIQUE (Django)                       UTILISATEURS
┌────────────────────┐     ┌──────────────────────────────────────────┐     ┌──────────────────────┐
│ WhatsApp (Meta)    │────►│ Webhook → compréhension → déclarations   │     │ Application web      │
│ Téléphone hors     │────►│ API REST + JWT, cloisonnement            │────►│ installable (PWA),   │
│ ligne (PWA)        │     │   organisation → district → rôle         │     │ hors ligne, FR / EN  │
│ Capteurs ESP32     │────►│ Ingestion IoT (clé API)                  │     ├──────────────────────┤
│ Fichiers Excel     │────►│ Import / export IATI / export comptable  │     │ Portail public       │
└────────────────────┘     │ IA : valorisation · risque · anomalies   │     │ par organisation     │
                           │      prévisions · assistant RAG          │     └──────────────────────┘
                           │ PostgreSQL (ou SQLite) · sauvegardes     │
                           │ Journal d'audit chaîné (SHA-256)         │
                           └──────────────────────────────────────────┘
```

```
umurage/
├── demarrer-windows.ps1, demarrer.sh    lancement en une commande
├── Dockerfile, docker-compose.prod.yml  déploiement sur serveur
├── backend/
│   ├── config/        paramètres, routes, service de l'interface
│   ├── core/          organisations, districts, rôles, cloisonnement, journal, inscription, membres, tests
│   ├── patrimoine/    biens, documents, projets, déclarations, WhatsApp, import/export, qualité
│   ├── finances/      transactions, prévisions
│   ├── iot/           capteurs, mesures, alertes
│   └── ia/            valorisation, anomalies, risques, assistant
├── frontend/          React + Vite, PWA (service worker, manifeste), traductions (src/i18n.jsx)
└── docs/esp32/        programme d'un capteur de forage
```

---

## Brancher le vrai WhatsApp

1. Sur **Meta for Developers**, créez une application de type « Business » et ajoutez le produit **WhatsApp**.
2. Déclarez l'adresse du webhook `https://votre-domaine/api/whatsapp/webhook/` et le jeton de vérification de votre choix.
   Abonnez-vous au champ `messages`.
3. Sur le serveur, définissez `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_ID` et `WHATSAPP_VERIFY_TOKEN`.
4. Dans **Paramètres → Membres**, renseignez le numéro de téléphone de chaque agent et surintendant :
   seuls les numéros enregistrés peuvent déclarer.

Messages vocaux : installez `faster-whisper` (`pip install faster-whisper`) pour la transcription automatique,
qui fonctionne en kirundi, français et swahili. Sans lui, le vocal est conservé et écouté par le validateur.

---

## Mise en production

**Avec Docker** (recommandé) : le proxy HTTPS **Caddy est inclus** et le réglage de l'adresse IP réelle
(`UMURAGE_NUM_PROXIES=1`) est déjà fixé.

```bash
cp backend/.env.example .env        # remplir : clé secrète, mot de passe PostgreSQL, UMURAGE_DOMAINE, UMURAGE_EMAIL_TLS
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec app python manage.py createsuperuser
```

1. Faites pointer le nom de domaine vers le serveur, avec les ports 80 et 443 ouverts.
2. Caddy obtient alors seul le certificat HTTPS et le renouvelle.
3. L'application ne publie aucun port : on ne la joint qu'à travers Caddy.
4. Pour vérifier, connectez-vous en administrateur, puis ouvrez **Paramètres → Intégrations → Adresse IP des visiteurs → Vérifier**.

Le service `sauvegarde` fait une sauvegarde complète chaque jour et garde les 30 dernières.
L'image a un **contrôle de santé** (`/api/sante/`) et Caddy ne démarre qu'une fois l'application prête. L'image est
construite par l'intégration continue à chaque envoi sur GitHub ; faites quand même un premier essai complet sur
une machine de test avant le serveur définitif.

**Sans Docker** : PostgreSQL, puis `npm run build`, `python manage.py migrate`, `collectstatic`,
et `gunicorn config.wsgi --bind 127.0.0.1:8000` derrière un proxy HTTPS (le `Caddyfile` fourni convient, en
remplaçant `app:8000` par `127.0.0.1:8000`), avec les variables de `backend/.env.example`, dont `UMURAGE_NUM_PROXIES=1`.

Sécurité en production : HTTPS forcé, cookies sécurisés, HSTS, en-têtes de protection, fichiers téléversés remis
seulement par lien signé et temporaire, connexion limitée à 10 tentatives par minute, inscription limitée à 5 par heure,
refus de démarrer sans clé secrète solide ni domaine déclaré. Suivi des erreurs facultatif (`SENTRY_DSN`).

**Tâches quotidiennes** : `python manage.py executer_taches` (rappels, loyers, entretiens ; voir docs/EXPLOITATION.md).

**Sauvegardes** : `python manage.py sauvegarder --garder 30` (base au format JSON portable et fichiers, dans une archive datée).

---

## Commandes utiles (dans `backend`)

```bash
python manage.py test                         # 113 tests : API, cloisonnement, membres, dîmes, jetons, fichiers, analyse IA…
python manage.py test metier.test_analyse_ml  # 7 tests v3.9 : analyse intelligente de la comparaison des églises
python manage.py test core.test_fichiers      # 13 tests v3.9 : fichiers protégés, réglages de production
python manage.py test metier.test_v36         # 17 tests v3.6 : jetons, mot de passe oublié, mineurs, dîmes
POSTGRES_DB=umurage python manage.py test core.test_concurrence   # écritures simultanées (PostgreSQL uniquement)
python manage.py seed_demo --reset            # recharger toute la démonstration (efface les données)
python manage.py simuler_iot --intervalle 5   # capteurs en direct
python manage.py sauvegarder                  # sauvegarde complète
```

Tests de l'interface : `npm test` dans `frontend`. Tout est relancé sur GitHub à chaque envoi (`.github/workflows/ci.yml`).
Les évolutions sont notées dans [CHANGELOG.md](CHANGELOG.md).

Développement de l'interface avec rechargement automatique : `npm run dev` dans `frontend`
(l'interface est alors sur http://localhost:5173 et relaie l'API vers le port 8000).

---

## Principales routes de l'API

| Route | Description |
|---|---|
| `POST /api/auth/token/` | Connexion (JWT) |
| `GET /api/comparaison/`, `GET /api/comparaison/analyse/` | Comparaison des églises et son analyse par apprentissage automatique |
| `GET /media/...?j=...` | Fichier téléversé, par lien signé et temporaire (ou en-tête Bearer avec contrôle du périmètre) |
| `GET /api/moi/`, `GET/PATCH /api/organisation/` | Utilisateur et organisation |
| `POST /api/inscription/` | Création d'une organisation (public) |
| `/api/membres/`, `/api/districts/` | Comptes des responsables et districts (administrateur) |
| `/api/acces-membres/` + `accorder/`, `reinitialiser/`, `suspendre/`, `reactiver/`, `retirer/`, `accorder-groupe/`, `statistiques/` | Accès des fidèles (administrateur) |
| `/api/demandes-acces/` + `accorder/`, `refuser/` | Demandes d'accès des fidèles (administrateur) |
| `POST /api/acces/demande/`, `GET /api/acces/organisations/` | Demande d'accès (public, 5 par heure) |
| `GET /api/espace-membre/`, `PATCH …/coordonnees/`, `GET/POST …/signalements/` | Espace membre (rôle MEMBRE) |
| `POST /api/moi/mot-de-passe/` | Changer son mot de passe (tout utilisateur) |
| `POST /api/auth/refresh/`, `POST /api/auth/deconnexion/` | Session par cookie HttpOnly (en-tête `X-Umurage`), déconnexion |
| `POST /api/auth/mot-de-passe-oublie/`, `POST /api/auth/reinitialiser/` | Mot de passe oublié (public, 5 par heure) |
| `/api/contributions/` + `annuler/`, `synthese/`, `attestation/` | Dîmes et offrandes (responsables) |
| `GET /api/espace-membre/contributions/`, `POST /api/espace-membre/attestation/` | Mes dons, mon attestation (membre) |
| `GET /api/attestations/verifier/<code>/` | Vérification publique d'une attestation |
| `/api/biens/`, `/api/projets/`, `/api/documents/`, `/api/transactions/` | Données principales |
| `/api/declarations/` + `valider/`, `rejeter/`, `simuler/` | Déclarations du terrain |
| `POST /api/whatsapp/webhook/` | Réception des messages WhatsApp |
| `POST /api/import/biens/`, `GET /api/import/modele/` | Import Excel/CSV et modèle |
| `GET /api/export/iati/`, `GET /api/export/transactions/` | Exports IATI et comptable |
| `GET /api/qualite/` | Score et classement de la qualité des données |
| `GET /api/tableau-de-bord/`, `/api/carte/`, `/api/recherche/` | Pilotage |
| `GET /api/public/?organisation=slug` | Portail public |

---

## Feuille de route

- **Langues** : kirundi, kinyarwanda, swahili et portugais pour l'interface, à rédiger avec des locuteurs natifs.
  Les libellés produits par le serveur (catégories, ODD) sont encore en français.
- **Données réelles** : inventaire d'un district pilote, puis ventes foncières réelles pour la valorisation.
- **Mobile Money** : import automatique des opérations Lumicash et EcoCash.
- **Imagerie satellite** pour le suivi des champs et des chantiers.
- **Registre partagé** entre organisations (blockchain de consortium) pour les titres fonciers et la traçabilité des dons.
- **Reconnaissance comme Bien Public Numérique** (Digital Public Goods Alliance) : le logiciel est déjà sous licence libre.

Licence MIT. Voir `CONTRIBUTING.md` pour contribuer, en particulier aux traductions.
