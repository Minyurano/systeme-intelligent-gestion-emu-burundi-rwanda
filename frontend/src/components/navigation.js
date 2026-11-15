import {
  BookOpenCheck, Boxes, HandCoins, UserCheck, ChartColumnBig, UsersRound, GitCompareArrows, CalendarClock, ClipboardCheck, FolderKanban, Gauge, Gavel, KeyRound, LayoutDashboard, Map, MessageSquareText,
  Printer, Radio, ScanLine, ScrollText, Settings, ShieldCheck, Wallet, Wrench,
} from "lucide-react";

// Plan de l'application : barre latérale, fil d'Ariane et recherche. Les libellés sont des clés de traduction.
export const PAGES = [
  { groupe: "nav.pilotage", items: [
    { to: "/", libelle: "nav.tableau", icone: LayoutDashboard },
    { to: "/carte", libelle: "nav.carte", icone: Map },
    { to: "/qualite", libelle: "nav.qualite", icone: Gauge },
    { to: "/comparaison", libelle: "nav.comparaison", icone: GitCompareArrows },
    { to: "/rapport", libelle: "nav.rapport", icone: Printer },
  ] },
  { groupe: "nav.operations", items: [
    { to: "/approbations", libelle: "nav.approbations", icone: Gavel, compteur: "approbations" },
    { to: "/echeancier", libelle: "nav.echeancier", icone: CalendarClock, compteur: "echeances" },
    { to: "/maintenance", libelle: "nav.maintenance", icone: Wrench, compteur: "ordres_urgents" },
  ] },
  { groupe: "nav.eglise", items: [
    { to: "/statistiques", libelle: "nav.statistiques", icone: ChartColumnBig },
    { to: "/registre", libelle: "nav.registre", icone: UsersRound },
    { to: "/acces-membres", libelle: "nav.acces_membres", icone: UserCheck, droit: "acces_membres", compteur: "demandes_acces" },
  ] },
  { groupe: "nav.patrimoine", items: [
    { to: "/biens", libelle: "nav.inventaire", icone: Boxes },
    { to: "/inventaire-terrain", libelle: "nav.inventaire_terrain", icone: ScanLine },
    { to: "/declarations", libelle: "nav.declarations", icone: ClipboardCheck, compteur: "declarations" },
    { to: "/projets", libelle: "nav.projets", icone: FolderKanban },
  ] },
  { groupe: "nav.finances", items: [
    { to: "/finances", libelle: "nav.finances_page", icone: Wallet, compteur: "anomalies" },
    { to: "/contributions", libelle: "nav.contributions", icone: HandCoins, droit: "contributions" },
    { to: "/locations", libelle: "nav.locations", icone: KeyRound, compteur: "loyers_impayes" },
    { to: "/comptabilite", libelle: "nav.comptabilite", icone: BookOpenCheck, droit: "comptabilite" },
  ] },
  { groupe: "nav.intelligence", items: [
    { to: "/capteurs", libelle: "nav.capteurs", icone: Radio, compteur: "alertes" },
    { to: "/assistant", libelle: "nav.assistant", icone: MessageSquareText },
  ] },
  { groupe: "nav.gouvernance", items: [
    { to: "/journal", libelle: "nav.journal", icone: ScrollText, droit: "journal" },
    { to: "/securite", libelle: "nav.securite", icone: ShieldCheck },
    { to: "/parametres", libelle: "nav.parametres", icone: Settings, droit: "parametres" },
  ] },
];
