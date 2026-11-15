// Fonctions d'interprétation de l'analyse intelligente (sans React, testées par Vitest).

// Couleur d'un profil : suit le profil (ordre fixe), jamais son rang dans une liste filtrée.
export const COULEURS_PROFILS = ["#1E8A57", "#8A44A8", "#B07A12", "#2766B0"];
export const couleurProfil = (i) => COULEURS_PROFILS[i % COULEURS_PROFILS.length];

export function signe(n) {
  if (n === null || n === undefined) return "—";
  return n > 0 ? `+${n}` : `${n}`;
}

// Traduit un écart standardisé (en écarts-types) en mots simples.
export function niveauEcart(z) {
  const a = Math.abs(z);
  if (a < 0.25) return "dans la moyenne";
  if (a < 0.75) return z > 0 ? "un peu au-dessus de la moyenne" : "un peu en dessous de la moyenne";
  if (a < 1.5) return z > 0 ? "nettement au-dessus de la moyenne" : "nettement en dessous de la moyenne";
  return z > 0 ? "très au-dessus de la moyenne" : "très en dessous de la moyenne";
}

// Fiche personnalisée d'une église : ce que disent les cinq méthodes à son sujet, en phrases simples.
export function ficheEglise(d, id) {
  if (!d?.disponible) return null;
  const point = d.carte?.points?.find((p) => p.id === id);
  if (!point) return null;
  const profil = d.profils?.find((p) => p.id === point.profil);
  const attendu = d.attendu?.lignes?.find((l) => l.id === id);
  const atypique = d.atypiques?.lignes?.find((l) => l.id === id);
  const jumelle = d.jumelles?.find((j) => j.id === id);
  const modelePour = (d.jumelles || []).filter((j) => j.modele.id === id).map((j) => j.nom);
  const phrases = [];
  if (profil) phrases.push({ type: "profil", texte: `Appartient au profil « ${profil.nom} » (${profil.effectif} au total).` });
  if (attendu) phrases.push({ type: attendu.ecart >= 10 ? "bon" : attendu.ecart <= -10 ? "alerte" : "neutre", texte: attendu.texte });
  if (atypique?.atypique) phrases.push({ type: "alerte", texte: `Profil atypique : ${atypique.raisons.join(" ; ")}.` });
  if (jumelle) phrases.push({ type: "piste", texte: `${jumelle.texte} Points à travailler : ${jumelle.lecons.join(" ; ")}.` });
  if (modelePour.length) phrases.push({ type: "bon", texte: `Sert de modèle à : ${modelePour.join(", ")}. Son expérience mérite d'être partagée.` });
  return { nom: point.nom, indice: point.indice, profil, phrases };
}

// Données du graphique « réel moins attendu », triées du meilleur au plus faible.
export function donneesEcarts(attendu) {
  return (attendu?.lignes || []).map((l) => ({ ...l, nom_court: l.nom.length > 16 ? `${l.nom.slice(0, 15)}…` : l.nom }));
}

// Étiquettes de la carte : on nomme d'abord l'église choisie, puis les petits profils et les points éloignés
// du centre, en sautant tout nom qui chevaucherait un nom déjà placé (les autres restent visibles au survol).
export function etiquettesVisibles(points, effectifs = {}, selection = null, { parLettre = 0.0125, hauteur = 0.08 } = {}) {
  if (!points?.length) return new Set();
  const xs = points.map((p) => p.x), ys = points.map((p) => p.y);
  const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  const nx = (v) => (x1 > x0 ? (v - x0) / (x1 - x0) : 0.5), ny = (v) => (y1 > y0 ? (v - y0) / (y1 - y0) : 0.5);
  const priorite = (p) => (p.id === selection ? 1e9 : 0) + ((effectifs[p.profil] ?? 99) <= 3 ? 1e6 : 0) + Math.hypot(nx(p.x) - 0.5, ny(p.y) - 0.5);
  const places = [], visibles = new Set();
  for (const p of [...points].sort((a, b) => priorite(b) - priorite(a))) {
    // Largeur du nom proportionnelle à sa longueur (en part de la largeur du graphique)
    const x = nx(p.x), y = ny(p.y), l = Math.max(0.08, (p.nom || "").length * parLettre);
    const choisie = p.id === selection; // l'église choisie est toujours nommée
    if (!choisie && places.some((q) => Math.abs(q.x - x) < (q.l + l) / 2 && Math.abs(q.y - y) < hauteur)) continue;
    // Le nom s'écrit au-dessus du point : on ne le pose pas sur le point d'une autre église
    if (!choisie && points.some((q) => q.id !== p.id && Math.abs(nx(q.x) - x) < l / 2 + 0.04 && ny(q.y) - y > -0.02 && ny(q.y) - y < hauteur + 0.04)) continue;
    places.push({ x, y, l });
    visibles.add(p.id);
  }
  return visibles;
}
