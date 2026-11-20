import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

/*
  Traductions de l'interface. Ajouter une langue = ajouter un dictionnaire ci-dessous
  (kirundi, kinyarwanda, swahili, portugais...). Une clé absente retombe sur le français.
  Les traductions doivent être relues par des locuteurs natifs avant mise en service.
*/
const DICTIONNAIRES = {
  fr: {
    "nav.pilotage": "Pilotage", "nav.patrimoine": "Patrimoine", "nav.finances": "Finances", "nav.intelligence": "Intelligence",
    "nav.gouvernance": "Gouvernance", "nav.transparence": "Transparence",
    "nav.tableau": "Tableau de bord", "nav.carte": "Carte", "nav.rapport": "Rapport du patrimoine", "nav.qualite": "Qualité des données",
    "nav.inventaire": "Inventaire", "nav.declarations": "Déclarations du terrain", "nav.projets": "Projets et impact",
    "nav.finances_page": "Finances", "nav.capteurs": "Capteurs", "nav.assistant": "Assistant et archives",
    "nav.journal": "Journal d'audit", "nav.parametres": "Paramètres", "nav.portail": "Portail public",
    "nav.operations": "Opérations", "nav.approbations": "Approbations", "nav.echeancier": "Échéancier", "nav.maintenance": "Maintenance",
    "nav.inventaire_terrain": "Inventaire physique", "nav.locations": "Locations et loyers", "nav.comptabilite": "Comptabilité",
    "nav.securite": "Sécurité du compte", "nav.comparaison": "Comparaison des églises",
    "nav.eglise": "Vie de l'Église", "nav.registre": "Registre des membres", "nav.acces_membres": "Accès des membres", "nav.contributions": "Dîmes et offrandes", "co.oublie": "Mot de passe oublié ?",
    "co.membre": "Membre de l'Église sans identifiants ?", "co.demander": "Demander l'accès",
    "co.identifiant_aide": "Identifiant ou numéro de membre", "nav.statistiques": "Statistiques de l'Église",
    "haut.rechercher": "Rechercher un bien, un projet…", "haut.notifications": "Notifications", "haut.aucune_notif": "Aucune notification.",
    "haut.theme_clair": "Thème clair", "haut.theme_sombre": "Thème sombre", "haut.deconnexion": "Se déconnecter", "haut.langue": "English",
    "haut.tous_districts": "tous les districts", "haut.district_de": "district de {d}",
    "notif.anomalies": "{n} transaction(s) signalée(s) à vérifier", "notif.declarations": "{n} déclaration(s) du terrain à valider",
    "hors_ligne.titre": "Hors ligne", "hors_ligne.attente": "{n} enregistrement(s) seront envoyés au retour du réseau.",
    "hors_ligne.consultation": "Vous consultez les dernières données enregistrées sur cet appareil.", "hors_ligne.envoyes": "{n} enregistrement(s) fait(s) hors ligne ont été envoyés.",
    "co.titre": "Connexion", "co.sous": "Accédez à l'espace de gestion du patrimoine.", "co.identifiant": "Identifiant",
    "co.mdp": "Mot de passe", "co.bouton": "Se connecter", "co.encours": "Connexion…",
    "co.demo.eveque.role": "Direction épiscopale", "co.demo.eveque.desc": "voit et pilote tout le patrimoine",
    "co.demo.tresorier.role": "Trésorier", "co.demo.tresorier.desc": "finances et contrôle des anomalies",
    "co.demo.surintendant.gitega.role": "Surintendant de Gitega", "co.demo.surintendant.gitega.desc": "limité au district de Gitega",
    "co.demo.agent.burunga.role": "Agent de collecte", "co.demo.agent.burunga.desc": "recense les biens de Burunga",
    "co.demo.admin.role": "Administrateur", "co.demo.admin.desc": "comptes, rôles et paramètres",
    "co.demo.membre.kayero.role": "Membre de l'Église", "co.demo.membre.kayero.desc": "Esther, église de Kayero : espace membre uniquement",
    "co.demo.admin.rwanda.role": "EMU Rwanda (démo en anglais)", "co.demo.admin.rwanda.desc": "deuxième organisation, données séparées",
    "co.demo": "Comptes de démonstration. Cliquez pour remplir, mot de passe", "co.nouvelle": "Votre Église n'utilise pas encore UMURAGE ?",
    "co.creer": "Créer un espace gratuit", "co.accroche": "Notre héritage commun. La plateforme qui recense, protège et valorise le patrimoine de l'Église, pour le gérer fidèlement aujourd'hui et le transmettre demain.",
    "co.a1": "Un inventaire unique et géolocalisé", "co.a1t": "Terrains, bâtiments, forages et équipements, chacun avec son code et son QR code.",
    "co.a2": "Une saisie depuis WhatsApp", "co.a2t": "Un message ou une photo du terrain suffit ; le surintendant valide.",
    "co.a3": "Une intelligence artificielle explicable", "co.a3t": "Valorisation, risques et anomalies financières, toujours justifiés.",
    "co.a4": "Une gouvernance vérifiable", "co.a4t": "Accès par rôle et par district, journal d'audit scellé.",
    "tb.titre": "Tableau de bord", "tb.sous": "Situation du patrimoine, {date}.", "tb.rapport": "Rapport", "tb.relancer": "Relancer les analyses IA",
    "tb.analyse": "Analyse en cours…", "tb.valeur": "Valeur estimée du patrimoine", "tb.milliards": "milliards de {devise}",
    "tb.millions": "millions de {devise}", "tb.biens_recenses": "biens recensés", "tb.terrains_titres": "des terrains titrés",
    "tb.beneficiaires": "bénéficiaires des projets et forages", "tb.phrase": "{n} biens recensés : terrains, bâtiments, forages, équipements, véhicules et cheptel.",
    "tb.k_titre": "Terrains sans titre définitif", "tb.k_titre_n": "À régulariser en priorité", "tb.k_titre_ok": "Tous les terrains sont titrés",
    "tb.k_risque": "Biens à risque élevé", "tb.k_risque_n": "Score de risque de 50 ou plus", "tb.k_alertes": "Alertes des capteurs",
    "tb.k_alertes_n": "Intervention à planifier", "tb.k_alertes_ok": "Tous les capteurs sont normaux", "tb.k_anomalies": "Transactions à vérifier",
    "tb.k_anomalies_n": "Signalées par l'IA", "tb.finances": "Recettes et dépenses", "tb.finances_sous": "Douze derniers mois, en millions de {devise}",
    "tb.recettes": "Recettes", "tb.depenses": "Dépenses", "tb.solde": "Solde", "tb.recettes_cum": "Recettes cumulées", "tb.depenses_cum": "Dépenses cumulées",
    "tb.activite": "Activité récente", "tb.activite_sous": "Entretiens, alertes et signalements", "tb.mois_incomplet": "Mois écarté car incomplet (saisie en cours) : {mois}.", "tb.par_type": "Valeur par type de bien",
    "tb.par_type_sous": "Estimation des modèles de valorisation, en millions de {devise}", "tb.par_district": "Situation par district",
    "tb.district": "District", "tb.biens": "Biens", "tb.valeur_col": "Valeur", "tb.a_risque": "À risque", "tb.sans_titre": "Sans titre",
    "tb.intervention": "Biens qui demandent une intervention", "tb.intervention_sous": "Classés par score de risque : état, usure, entretien, capteurs et titre foncier",
    "tb.au_dessus": "{n} biens au-dessus du seuil", "tb.voir_inventaire": "Voir tout l'inventaire", "tb.sante": "Objectif santé 2030",
    "tb.sante_sous": "Un centre de santé par district", "tb.atteint": "Atteint", "tb.construction": "En construction", "tb.planifier": "À planifier",
    "tb.odd": "Objectifs de Développement Durable", "tb.objectif": "Objectif", "tb.projets_biens": "{p} projets, {b} biens",
    "tb.declarations": "Déclarations à valider", "tb.declarations_n": "Reçues du terrain", "tb.tous_districts": "Tous les districts",
    "commun.annuler": "Annuler", "commun.enregistrer": "Enregistrer", "commun.fermer": "Fermer", "commun.chargement": "Chargement…",
    "pt.espace": "Espace de gestion", "pt.titre": "Ce que vos dons construisent", "pt.accroche": "Forages, centres de santé, écoles et projets des femmes : chaque réalisation est recensée, suivie et mise à jour dans UMURAGE, notre plateforme de gestion du patrimoine.",
    "pt.eau": "Accès à l'eau potable", "pt.eau_n": "personnes, grâce à {n} forages", "pt.sante": "Centres de santé", "pt.sante_n": "en service ou en construction",
    "pt.education": "Éducation", "pt.education_n": "écoles et établissements de formation", "pt.benef": "Bénéficiaires", "pt.benef_n": "personnes touchées par {n} projets",
    "pt.ou": "Où nous agissons", "pt.ou_sous": "Les projets dans les {n} districts.", "pt.projets": "Nos projets", "pt.projets_sous": "Avancement mis à jour par les équipes de terrain.",
    "pt.odd": "Notre contribution aux Objectifs de Développement Durable", "pt.odd_sous": "Nombre de personnes touchées par objectif.",
    "pt.benef_court": "bénéficiaires", "pt.avec": "avec {f}", "pt.projets_biens": "{p} projets et {b} biens",
    "pt.mention": "Les données financières détaillées et les titres de propriété ne sont jamais publiés sur ce portail.", "pt.indispo": "Ce portail n'est pas disponible.",
  },
  en: {
    "nav.pilotage": "Overview", "nav.patrimoine": "Assets", "nav.finances": "Finance", "nav.intelligence": "Intelligence",
    "nav.gouvernance": "Governance", "nav.transparence": "Transparency",
    "nav.tableau": "Dashboard", "nav.carte": "Map", "nav.rapport": "Asset report", "nav.qualite": "Data quality",
    "nav.inventaire": "Inventory", "nav.declarations": "Field reports", "nav.projets": "Projects and impact",
    "nav.finances_page": "Finance", "nav.capteurs": "Sensors", "nav.assistant": "Assistant and archives",
    "nav.journal": "Audit log", "nav.parametres": "Settings", "nav.portail": "Public portal",
    "nav.operations": "Operations", "nav.approbations": "Approvals", "nav.echeancier": "Deadlines", "nav.maintenance": "Maintenance",
    "nav.inventaire_terrain": "Physical inventory", "nav.locations": "Leases and rents", "nav.comptabilite": "Accounting",
    "nav.securite": "Account security", "nav.comparaison": "Compare churches",
    "nav.eglise": "Church life", "nav.registre": "Membership register", "nav.acces_membres": "Member access", "nav.contributions": "Tithes and offerings", "co.oublie": "Forgot your password?",
    "co.membre": "Church member without a login?", "co.demander": "Request access",
    "co.identifiant_aide": "Username or membership number", "nav.statistiques": "Church statistics",
    "haut.rechercher": "Search an asset, a project…", "haut.notifications": "Notifications", "haut.aucune_notif": "No notifications.",
    "haut.theme_clair": "Light theme", "haut.theme_sombre": "Dark theme", "haut.deconnexion": "Sign out", "haut.langue": "Français",
    "haut.tous_districts": "all districts", "haut.district_de": "{d} district",
    "notif.anomalies": "{n} flagged transaction(s) to review", "notif.declarations": "{n} field report(s) to approve",
    "hors_ligne.titre": "Offline", "hors_ligne.attente": "{n} record(s) will be sent when the network is back.",
    "hors_ligne.consultation": "You are viewing the latest data saved on this device.", "hors_ligne.envoyes": "{n} record(s) made offline have been sent.",
    "co.titre": "Sign in", "co.sous": "Access the asset management workspace.", "co.identifiant": "Username",
    "co.mdp": "Password", "co.bouton": "Sign in", "co.encours": "Signing in…",
    "co.demo.eveque.role": "Bishop's office", "co.demo.eveque.desc": "sees and manages all assets",
    "co.demo.tresorier.role": "Treasurer", "co.demo.tresorier.desc": "finances and anomaly review",
    "co.demo.surintendant.gitega.role": "Gitega superintendent", "co.demo.surintendant.gitega.desc": "limited to the Gitega district",
    "co.demo.agent.burunga.role": "Field agent", "co.demo.agent.burunga.desc": "records the assets of Burunga",
    "co.demo.admin.role": "Administrator", "co.demo.admin.desc": "accounts, roles and settings",
    "co.demo.membre.kayero.role": "Church member", "co.demo.membre.kayero.desc": "Esther, Kayero church: member space only",
    "co.demo.admin.rwanda.role": "EMU Rwanda (English demo)", "co.demo.admin.rwanda.desc": "second organisation, separate data",
    "co.demo": "Demo accounts. Click to fill in, password", "co.nouvelle": "Your church does not use UMURAGE yet?",
    "co.creer": "Create a free workspace", "co.accroche": "Our shared heritage. The platform that records, protects and values the Church's assets, to manage them faithfully today and pass them on tomorrow.",
    "co.a1": "One geolocated inventory", "co.a1t": "Land, buildings, boreholes and equipment, each with its own code and QR code.",
    "co.a2": "Reporting from WhatsApp", "co.a2t": "A message or a photo from the field is enough; the superintendent approves.",
    "co.a3": "Explainable artificial intelligence", "co.a3t": "Valuation, risks and financial anomalies, always justified.",
    "co.a4": "Verifiable governance", "co.a4t": "Role and district based access, sealed audit log.",
    "tb.titre": "Dashboard", "tb.sous": "Asset situation, {date}.", "tb.rapport": "Report", "tb.relancer": "Re-run AI analyses",
    "tb.analyse": "Analysing…", "tb.valeur": "Estimated asset value", "tb.milliards": "billion {devise}",
    "tb.millions": "million {devise}", "tb.biens_recenses": "recorded assets", "tb.terrains_titres": "of land with a title deed",
    "tb.beneficiaires": "beneficiaries of projects and boreholes", "tb.phrase": "{n} recorded assets: land, buildings, boreholes, equipment, vehicles and livestock.",
    "tb.k_titre": "Land without a final title", "tb.k_titre_n": "Priority to regularise", "tb.k_titre_ok": "All land has a title deed",
    "tb.k_risque": "High-risk assets", "tb.k_risque_n": "Risk score of 50 or more", "tb.k_alertes": "Sensor alerts",
    "tb.k_alertes_n": "Intervention to plan", "tb.k_alertes_ok": "All sensors are normal", "tb.k_anomalies": "Transactions to review",
    "tb.k_anomalies_n": "Flagged by AI", "tb.finances": "Income and expenses", "tb.finances_sous": "Last twelve months, in million {devise}",
    "tb.recettes": "Income", "tb.depenses": "Expenses", "tb.solde": "Balance", "tb.recettes_cum": "Total income", "tb.depenses_cum": "Total expenses",
    "tb.activite": "Recent activity", "tb.activite_sous": "Maintenance, alerts and flags", "tb.mois_incomplet": "Month left out because it is incomplete (data entry in progress): {mois}.", "tb.par_type": "Value by asset type",
    "tb.par_type_sous": "Valuation model estimates, in million {devise}", "tb.par_district": "Situation by district",
    "tb.district": "District", "tb.biens": "Assets", "tb.valeur_col": "Value", "tb.a_risque": "At risk", "tb.sans_titre": "No title",
    "tb.intervention": "Assets needing intervention", "tb.intervention_sous": "Ranked by risk score: condition, wear, maintenance, sensors and land title",
    "tb.au_dessus": "{n} assets above the threshold", "tb.voir_inventaire": "See the full inventory", "tb.sante": "Health goal 2030",
    "tb.sante_sous": "One health centre per district", "tb.atteint": "Achieved", "tb.construction": "Under construction", "tb.planifier": "To plan",
    "tb.odd": "Sustainable Development Goals", "tb.objectif": "Goal", "tb.projets_biens": "{p} projects, {b} assets",
    "tb.declarations": "Field reports to approve", "tb.declarations_n": "Received from the field", "tb.tous_districts": "All districts",
    "commun.annuler": "Cancel", "commun.enregistrer": "Save", "commun.fermer": "Close", "commun.chargement": "Loading…",
    "pt.espace": "Management workspace", "pt.titre": "What your gifts are building", "pt.accroche": "Boreholes, health centres, schools and women's projects: every achievement is recorded, monitored and kept up to date in UMURAGE, our asset management platform.",
    "pt.eau": "Access to clean water", "pt.eau_n": "people, thanks to {n} boreholes", "pt.sante": "Health centres", "pt.sante_n": "operating or under construction",
    "pt.education": "Education", "pt.education_n": "schools and training centres", "pt.benef": "Beneficiaries", "pt.benef_n": "people reached by {n} projects",
    "pt.ou": "Where we work", "pt.ou_sous": "Projects across {n} districts.", "pt.projets": "Our projects", "pt.projets_sous": "Progress updated by field teams.",
    "pt.odd": "Our contribution to the Sustainable Development Goals", "pt.odd_sous": "Number of people reached per goal.",
    "pt.benef_court": "beneficiaries", "pt.avec": "with {f}", "pt.projets_biens": "{p} projects and {b} assets",
    "pt.mention": "Detailed financial data and property titles are never published on this portal.", "pt.indispo": "This portal is not available.",
  },
};

export const LANGUES = { fr: "Français", en: "English" };
const CLE = "umurage.langue";
const Ctx = createContext(null);

function langueInitiale() {
  try {
    const l = localStorage.getItem(CLE);
    if (DICTIONNAIRES[l]) return l;
  } catch {
    /* stockage indisponible */
  }
  return navigator.language?.startsWith("fr") ? "fr" : navigator.language?.startsWith("en") ? "en" : "fr";
}

export function LangueProvider({ children }) {
  const [langue, setLangueEtat] = useState(langueInitiale);
  const setLangue = useCallback((l, memoriser = true) => {
    if (!DICTIONNAIRES[l]) return;
    setLangueEtat(l);
    if (memoriser) {
      try {
        localStorage.setItem(CLE, l);
      } catch {
        /* stockage indisponible */
      }
    }
  }, []);
  useEffect(() => {
    document.documentElement.lang = langue;
  }, [langue]);
  const t = useCallback(
    (cle, vars = {}) => {
      const modele = DICTIONNAIRES[langue][cle] ?? DICTIONNAIRES.fr[cle] ?? cle;
      return modele.replace(/\{(\w+)\}/g, (_, k) => (vars[k] ?? `{${k}}`));
    },
    [langue]
  );
  const valeur = useMemo(() => ({ langue, setLangue, t, choisie: (() => { try { return !!localStorage.getItem(CLE); } catch { return false; } })() }), [langue, setLangue, t]);
  return <Ctx.Provider value={valeur}>{children}</Ctx.Provider>;
}

export const useLangue = () => useContext(Ctx);
export const useT = () => useContext(Ctx).t;
