# UMURAGE : analyse du système et manques (versions 3.5 à 3.8)

Cette analyse porte sur la version 3.4 reçue : 9 400 lignes, 6 applications Django, 29 pages React et 54 tests.
Elle dit ce que la version 3.5 corrige et ce qu'il reste à faire, par ordre de priorité.

## 1. État des lieux

UMURAGE 3.4 est déjà complet côté **gestion du patrimoine** :

- inventaire et QR codes ;
- déclarations par WhatsApp ;
- valorisation par IA, risques et anomalies ;
- approbations, échéancier, baux, maintenance et comptabilité ;
- multi-organisations ;
- journal d'audit chaîné ;
- portail public ;
- registre officiel des membres.

Le grand manque était ailleurs. Le système servait seulement **le personnel** (administrateur, évêque, trésorier,
surintendant, agent). Les **fidèles**, qui sont pourtant inscrits au registre, n'avaient aucune place dans le système.

## 2. Ce que la version 3.5 corrige

| # | Manque constaté dans la 3.4 | Correction en 3.5 |
|---|---|---|
| 1 | Aucun rôle pour un simple membre de l'Église | Nouveau rôle `MEMBRE`, relié à une fiche du registre (`MembreEglise.compte`) |
| 2 | **Faille latente** : la permission par défaut était `IsAuthenticated`, et la lecture était ouverte à tout compte connecté. Un nouveau rôle aurait donc pu lire les finances, le journal, le tableau de bord, etc. | Nouvelle permission par défaut `EstPersonnel` : refus par défaut pour le rôle `MEMBRE`. Seules les adresses de l'espace membre lui sont ouvertes explicitement. Un test vérifie 28 adresses |
| 3 | Les administrateurs ne pouvaient pas ouvrir l'accès à un fidèle | Page **Accès des membres**, avec trois façons de faire : accès individuel, accès groupé (sélection ou église locale entière), et bouton dans le registre. On peut aussi suspendre, rétablir, réinitialiser ou retirer un accès |
| 4 | Aucun moyen pour un fidèle de demander l'accès | Formulaire public `/demande-acces`. La demande est « vérifiée » quand le numéro et le téléphone concordent. La réponse est la même dans tous les cas, donc personne ne peut savoir qui est inscrit au registre. Limité à 5 demandes par heure, et désactivable par l'administrateur |
| 5 | Pas de changement de mot de passe en libre-service | `POST /api/moi/mot-de-passe/` pour tout utilisateur, et changement **obligatoire** à la première connexion |
| 6 | Les mots de passe provisoires auraient fini dans les journaux du serveur (la fonction `whatsapp.envoyer` écrit le message quand l'API n'est pas branchée) | Les identifiants ne passent par WhatsApp que si l'API est configurée |
| 7 | Un membre transféré ou décédé aurait gardé son accès | Synchronisation automatique de la fiche vers le compte (désactivation, changement de district) |
| 8 | Une déclaration n'était pas reliée au compte de son auteur | Champ `Declaration.auteur`, grâce auquel un membre suit ses signalements |
| 9 | `trouver_profil` (WhatsApp) parcourait **tous** les comptes à chaque message, ce qui devenait trop lent avec des milliers de fidèles | Pré-filtre en base sur les derniers chiffres du numéro |
| 10 | L'identifiant était sensible à la casse | `git-2026-00012` ouvre le compte `GIT-2026-00012` |
| 11 | Risque créé par le nouveau lien fiche-compte : le registre aurait pu relier une fiche au compte d'un responsable | Champ `compte` en lecture seule dans l'API du registre (vérifié par un test) |

**Ce que voit un membre** : sa fiche et sa carte de membre imprimable, et ses coordonnées (téléphone, adresse,
profession, situation familiale), qu'il corrige lui-même avec trace au journal d'audit. Il voit aussi son église
locale (pasteur, surintendant, chiffres de la communauté), ses biens (nom, état, photo, **sans aucune valeur
financière ni statut juridique**) et les projets publics du district. Enfin, il peut faire des signalements avec photo.

**Ce qu'il ne voit jamais** : les finances, les valeurs, les titres, les autres membres, le journal, les tableaux
de bord ou l'IA. C'est garanti côté serveur.

## 3. Manques restants, par priorité

### Priorité haute (sécurité, fiabilité) : traitée en 3.6

| # | Manque | Ce que fait la 3.6 | Preuve |
|---|---|---|---|
| 1 | Mot de passe oublié | Code à 6 chiffres envoyé par WhatsApp et/ou e-mail. Seule son empreinte (HMAC) est gardée. Il expire après 10 minutes et 5 essais. La réponse est la même que le compte existe ou non. La limite est de 5 demandes par heure. Toutes les sessions sont fermées après le changement | 4 tests |
| 2 | Course sur le journal d'audit | Table `Verrou` : un compteur que chaque écriture modifie. PostgreSQL verrouille la ligne jusqu'à la fin de la transaction, SQLite verrouille la base. Les écritures du journal passent donc une par une | Test réel sur PostgreSQL : 12 fils × 6 écritures. **Sans le verrou, la chaîne casse dès la 2ᵉ entrée ; avec lui, elle reste intacte** |
| 3 | Course sur le numéro de membre | Même verrou, avec un compteur par préfixe district-année. Il démarre au plus grand numéro existant | Même test : **sans verrou, erreur d'unicité ; avec lui, 72 numéros continus de 1 à 72** |
| 4 | Jetons dans `localStorage` | Le jeton de rafraîchissement est dans un cookie `HttpOnly`, `SameSite=Strict`, limité à `/api/auth/` et réservé aux requêtes portant l'en-tête `X-Umurage`. Le jeton d'accès dure 15 minutes et reste **en mémoire seulement**. Il y a rotation et liste noire : un jeton volé puis réutilisé est refusé. Une déconnexion côté serveur existe. Les sessions sont révoquées au changement de mot de passe, à une suspension ou à un retrait. Le cache hors ligne de l'API est vidé à la déconnexion, car un téléphone peut être partagé | 5 tests, et un contrôle dans le navigateur : aucun jeton dans le stockage, et la session survit au rechargement |
| 5 | Règle des mineurs | `Organisation.age_minimum_acces` (16 ans par défaut, réglable de 10 à 21 ans). En dessous, il faut l'accord d'un parent ou tuteur : nom, lien et confirmation, enregistrés sur la fiche et au journal. La date de naissance est obligatoire pour ouvrir un accès. Un accès groupé met de côté les cas non conformes, avec leur raison | 3 tests |
| 6 | Limitation derrière un proxy | **Fait en 3.7.** `UMURAGE_NUM_PROXIES` règle le nombre de proxys de confiance. La valeur par défaut, 0, ignore l'en-tête. Le port de l'application est lié à 127.0.0.1 dans Docker. Un contrôle au démarrage (`umurage.W001`) et une page de diagnostic pour l'administrateur vérifient le réglage. Deux faits trouvés en le faisant : (a) DRF utilisait tel quel l'en-tête `X-Forwarded-For` envoyé par le client, donc **12 demandes sur 12 passaient** en changeant d'adresse inventée ; (b) les limites « mot de passe oublié » et « rafraîchissement » de la 3.6 n'étaient pas actives, car une classe de limitation était mal choisie. Les deux sont corrigés : après correction, le blocage arrive à la 6ᵉ demande | 4 tests |

### Dîmes et offrandes : traité en 3.6

Ce qui existe maintenant :

- **Saisie rapide** pour le dimanche : un membre ou une quête anonyme, la nature, le montant et le mode. La référence est obligatoire pour le Mobile Money.
- **Reçu numéroté** sous verrou (`SIGLE-ANNÉE-NNNNNN`), imprimable au format A6.
- **Comptabilité** : chaque contribution crée une recette « Dîmes et offrandes » dans les transactions.
- **Annulation** réservée au trésorier et à l'administrateur, avec un motif. Elle est interdite si l'exercice est clôturé, et elle retire la recette de la comptabilité. Le reçu reste visible, barré.
- **Synthèse** : par mois, comparée à la même période de l'année précédente, par nature et par église locale.
- **Espace membre, onglet « Mes dons »** : total, mois par mois, détail par nature, reçus imprimables et **attestation annuelle**. L'attestation est provisoire pendant l'année en cours, et définitive pour une année terminée.
- **Attestation au format A4**, avec un **QR code de vérification publique** (`/verifier/CODE`). La page publique montre seulement l'organisation, le nom abrégé, l'année et le total. Elle signale une attestation « dépassée » si les dons ont changé depuis son émission.
- **Cloisonnement** : un surintendant ou un agent ne voit que son district ; un fidèle, seulement ses propres dons.

C'est couvert par 5 tests, dont la cohérence des totaux.

### Priorité moyenne (vie de l'Église, ce qui rendrait le système indispensable)

7. ~~Contributions des membres~~ : **fait en 3.6** (voir plus haut). Il reste à faire l'import automatique des
   relevés Lumicash et EcoCash, et les promesses de dons (*pledges*) pour les campagnes de construction.
8. **Registres sacramentels.** Il faudrait des actes de baptême, de confirmation, de mariage et de décès, numérotés
   et imprimables. Il faudrait aussi des **transferts entre paroisses** avec leur historique : aujourd'hui, « Transféré »
   n'est qu'un statut, sans destination.
9. **Familles et ménages** : liens entre conjoints et entre parents et enfants, et carte familiale.
10. **Communication** : annonces de la paroisse dans l'espace membre, et messages WhatsApp groupés par église ou par
    ministère (chorale, jeunesse…).
11. **Retour au membre** : prévenir l'auteur d'un signalement (par WhatsApp ou dans l'espace) quand il est validé
    ou rejeté.
12. **Ministères et groupes** : membres, responsables et présences.
13. **Administration déléguée** : aujourd'hui, seul le rôle ADMIN donne les accès (constante `GESTIONNAIRES_ACCES`
    dans `metier/acces.py`). Pour des milliers de fidèles, on pourrait autoriser les surintendants à le faire dans leur
    district.

### Priorité normale (qualité technique)

14. **Intégration continue.** Aucun pipeline n'existe. La suite complète prend environ 8 minutes, parce que
    `seed_demo` est rechargé pour chaque classe de tests. Il faudrait une fixture partagée et GitHub Actions.
15. **Interface** : pas de tests (Vitest, Playwright), pas de TypeScript. Les nouvelles pages sont en français :
    leurs textes restent à passer dans `i18n.jsx`.
16. **Espace membre hors ligne** : le service worker ne met pas encore en cache `/api/espace-membre/`.
17. **Docker** : le README précise que le Dockerfile n'a pas été testé.

## 4. Fichiers modifiés et ajoutés en 3.5

- Backend :
  - `core/securite.py` (`EstPersonnel`, `EstMembre`) ;
  - `core/models.py` (rôle `MEMBRE`, `doit_changer_mdp`, `demandes_acces_ouvertes`) ;
  - `core/views.py` (`moi`, `changer_mot_de_passe`) ;
  - `core/deuxfacteurs.py` ;
  - **`metier/acces.py`** (nouveau) ;
  - `metier/models.py` (`compte`, `DemandeAcces`) ;
  - `patrimoine/models.py` et `patrimoine/whatsapp.py` ;
  - `config/urls.py` et `config/settings.py` ;
  - migrations `core/0004`, `metier/0003` et `patrimoine/0007` ;
  - **`metier/test_acces.py`** (16 tests).
- Frontend :
  - **`pages/AccesMembres.jsx`**, **`pages/EspaceMembre.jsx`** et **`pages/DemandeAcces.jsx`** ;
  - `components/MotDePasse.jsx`, `components/IdentifiantsAcces.jsx` et `components/CarteMembre.jsx` (extrait du registre) ;
  - routes protégées par espace dans `main.jsx` ;
  - `Registre`, `Parametres`, `Securite`, `Connexion`, `Layout` et `navigation`.

Mise à jour d'une installation existante : `python manage.py migrate`. Rien n'est effacé : les fiches existantes
restent simplement « sans accès ».

## 5. Fichiers de la version 3.6

- Backend :
  - `core/jetons.py` (cookie, rotation, révocation) ;
  - `core/mdp_oublie.py` ;
  - `core/models.py` (`Verrou`, `CodeReinitialisation`, `age_minimum_acces`) ;
  - **`metier/contributions.py`** ;
  - `metier/models.py` (`Contribution`, `AttestationAnnuelle`, accord parental, numéro sous verrou) ;
  - `metier/acces.py` (règle des mineurs) ;
  - migrations `core/0005`, `core/0006` et `metier/0004` ;
  - tests `core/test_concurrence.py` (PostgreSQL) et `metier/test_v36.py`.
- Frontend :
  - `api.js` et `auth.jsx` (jeton en mémoire, session par cookie) ;
  - pages `Contributions`, `MotDePasseOublie` et `VerifierAttestation` ;
  - `components/Recus.jsx` (reçu et attestation) ;
  - onglet « Mes dons » de l'espace membre ;
  - accord parental et âge minimum dans « Accès des membres ».

**Mise à jour d'une installation** : `python manage.py migrate`. Les utilisateurs devront se reconnecter une fois,
car les anciens jetons stockés dans le navigateur sont effacés. En production, configurez la messagerie
(variables `EMAIL_*`) pour les codes par e-mail.

## 6. Version 3.8 : déploiement prêt à l'emploi

- Le **proxy HTTPS Caddy** est inclus dans `docker-compose.prod.yml` : certificat automatique, compression, en-têtes de sécurité.
- **`UMURAGE_NUM_PROXIES=1`** est fixé dans le service `app`. L'application ne publie aucun port : seul Caddy la joint.
- **Vérification dans l'interface** : Paramètres → Intégrations → « Adresse IP des visiteurs ». La carte compare
  l'adresse retenue par le serveur avec l'adresse publique de l'appareil, et donne un verdict.
- **Testé derrière un vrai Caddy 2.8** :
  - une adresse falsifiée (`X-Forwarded-For: 6.6.6.6`) est remplacée par l'adresse réelle ;
  - avec 8 fausses adresses différentes, les demandes sont bloquées à partir de la 6ᵉ.

## 7. Version 3.9 : fusion, sécurité des fichiers et comparaison intelligente

- **Faille corrigée** : en 3.8, les fichiers téléversés (`/media/`) restaient publics en production. Vérifié sur la 3.8 :
  un titre foncier et la photo d'un fidèle s'ouvraient sans connexion (HTTP 200). En 3.9 : liens signés et temporaires,
  404 pour tout accès non autorisé (`core/fichiers.py`, 10 tests dans `core/test_fichiers.py`).
- **Production stricte**, contrôle de santé Docker, suivi des erreurs, intégration continue : réglés (points 14, 15 et 17
  de la liste ci-dessus).
- **Comparaison des églises par apprentissage automatique** (`metier/analyse_ml.py`, `components/AnalyseIA.jsx`) :
  profils (K-moyennes), carte (ACP), indice attendu (ridge, validation croisée), profils atypiques (auto-encodeur),
  églises jumelles (plus proches voisins). Chaque résultat est accompagné de sa lecture en langage simple et d'une mesure
  de fiabilité. 7 tests dans `metier/test_analyse_ml.py`.

Reste à faire, par priorité : traduction en kirundi (relue par des locuteurs natifs), données réelles d'un district
pilote (l'analyse intelligente n'a de valeur qu'avec elles), registres sacramentels, promesses de dons, import
Lumicash/EcoCash.
