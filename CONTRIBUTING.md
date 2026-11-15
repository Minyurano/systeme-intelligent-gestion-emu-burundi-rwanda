# Contribuer à UMURAGE

UMURAGE est un logiciel libre (licence MIT) au service des Églises et des organisations
communautaires. Toute contribution est bienvenue : code, traductions, retours de terrain.

## Les contributions les plus utiles

1. **Traductions** — kirundi, kinyarwanda, swahili, portugais, anglais. Les textes de l'interface sont
   dans `frontend/src/i18n.jsx` ; ajoutez un dictionnaire et faites-le relire par des locuteurs natifs.
   Le vocabulaire de la saisie WhatsApp est dans `backend/patrimoine/comprehension.py`.
2. **Retours de terrain** — ce qui bloque un agent ou un trésorier vaut plus qu'une nouvelle fonction.
3. **Données de référence** — ventes foncières réelles (anonymisées) pour améliorer la valorisation.

## Règles

- Avant toute modification du code : `python manage.py test` (dans `backend`) et `npm test` (dans `frontend`)
  doivent réussir. L'intégration continue GitHub les relance à chaque envoi, sur PostgreSQL.
- Toute évolution visible est notée dans `CHANGELOG.md`, et la version est mise à jour dans
  `backend/config/version.py` et `frontend/package.json`.
- Une organisation ne doit **jamais** voir les données d'une autre : toute nouvelle API passe par
  `DistrictScopedMixin` ou `OrganisationScopedMixin` (`backend/core/securite.py`), avec un test.
- Les textes de l'interface sont écrits en langage simple, du point de vue de l'utilisateur.
- Les données personnelles et financières ne sont jamais publiées sur le portail public.
