const nf = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });

// Monnaie de l'organisation connectée (BIF, RWF, KES...) : définie à la connexion.
let DEVISE = "BIF";
export const definirDevise = (d) => { DEVISE = d || "BIF"; };
export const devise = () => DEVISE;

export const nombre = (v) => (v === null || v === undefined ? "—" : nf.format(v));

// Montant en monnaie locale (le nom historique « bif » est conservé dans le code).
export function bif(v, compact = false) {
  if (v === null || v === undefined || v === "") return "—";
  const n = Number(v);
  if (compact) {
    if (Math.abs(n) >= 1e9) return `${(n / 1e9).toLocaleString("fr-FR", { maximumFractionDigits: 2 })} Md ${DEVISE}`;
    if (Math.abs(n) >= 1e6) return `${(n / 1e6).toLocaleString("fr-FR", { maximumFractionDigits: 1 })} M ${DEVISE}`;
  }
  return `${nf.format(n)} ${DEVISE}`;
}

export const date = (v) => (v ? new Date(v).toLocaleDateString("fr-FR") : "—");
export const dateHeure = (v) =>
  v ? new Date(v).toLocaleString("fr-FR", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) : "—";

export const moisCourt = (m) => {
  const [a, mo] = m.split("-");
  return new Date(+a, +mo - 1, 1).toLocaleDateString("fr-FR", { month: "short", year: "2-digit" });
};

// Palette catégorielle validée (contraste, daltonisme) — ordre fixe, jamais recyclé.
// Couleurs des catégories et des districts : pas de rouge, réservé aux alertes et aux risques.
export const COULEURS = ["#1E8A57", "#8A44A8", "#B07A12", "#2766B0", "#5B6B82", "#0B8FB0"];

export const CATEGORIES = {
  FON: "Foncier (terrain)",
  IMM: "Immobilier (bâtiment)",
  INF: "Infrastructure (forage, usine...)",
  EQP: "Équipement / matériel",
  VEH: "Véhicule",
  AGR: "Agricole et élevage",
};
export const COULEUR_CATEGORIE = Object.fromEntries(Object.keys(CATEGORIES).map((c, i) => [c, COULEURS[i]]));

export const ETATS = { BON: "Bon", MOYEN: "Moyen", MAUVAIS: "Mauvais", CONSTRUCTION: "En construction" };
export const JURIDIQUE = {
  TITRE: "Titre de propriété",
  EN_COURS: "Démarches en cours",
  SANS_TITRE: "Sans titre",
  NA: "Non applicable",
};
