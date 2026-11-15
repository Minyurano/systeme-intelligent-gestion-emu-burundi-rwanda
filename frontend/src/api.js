// Petit client pour l'API Django REST.
//
// Sécurité des jetons (v3.6) : le jeton d'accès (15 min) est gardé EN MÉMOIRE seulement ; le jeton de
// rafraîchissement est dans un cookie HttpOnly que le JavaScript ne peut pas lire. Une faille XSS ne peut
// donc plus voler une session de 7 jours en lisant le stockage du navigateur.
let acces = null;
let enVol = null;

try { localStorage.removeItem("umurage.jetons"); } catch { /* anciennes versions : jetons en clair, effacés */ }

export const jetons = () => (acces ? { access: acces } : null);

export function enregistrerJetons(j) {
  acces = j?.access || null;
}

// Demande un nouveau jeton d'accès avec le cookie. Renvoie true, false (pas de session) ou "reseau".
export function rafraichir() {
  if (!enVol) {
    enVol = fetch("/api/auth/refresh/", { method: "POST", credentials: "same-origin", headers: { "X-Umurage": "1" } })
      .then(async (r) => {
        if (!r.ok) { acces = null; return false; }
        acces = (await r.json()).access;
        return true;
      })
      .catch(() => "reseau")
      .finally(() => { enVol = null; });
  }
  return enVol;
}

// Ferme la session côté serveur et efface les réponses de l'API gardées pour le mode hors ligne
// (sinon la personne suivante sur le même téléphone pourrait les relire).
export async function fermerSession() {
  acces = null;
  try { await fetch("/api/auth/deconnexion/", { method: "POST", credentials: "same-origin" }); } catch { /* hors ligne */ }
  try {
    const cles = await caches.keys();
    await Promise.all(cles.filter((k) => k.endsWith("-api")).map((k) => caches.delete(k)));
  } catch { /* Cache API indisponible */ }
}

export class ErreurApi extends Error {
  constructor(message, statut, details) {
    super(message);
    this.statut = statut;
    this.details = details;
  }
}

function messageErreur(statut, corps) {
  if (corps?.detail) return corps.detail;
  if (corps?.erreur) return corps.erreur;
  if (corps && typeof corps === "object") {
    return Object.entries(corps)
      .map(([k, v]) => `${k} : ${Array.isArray(v) ? v.join(" ") : v}`)
      .join(" — ");
  }
  if (statut === 403) return "Votre rôle ne permet pas cette action.";
  return `Erreur ${statut}`;
}

export async function api(chemin, { methode = "GET", corps, brut = false, essai = 0 } = {}) {
  if (!acces && essai === 0) await rafraichir();
  const entetes = {};
  if (acces) entetes.Authorization = `Bearer ${acces}`;
  let body;
  if (corps instanceof FormData) body = corps;
  else if (corps !== undefined) {
    entetes["Content-Type"] = "application/json";
    body = JSON.stringify(corps);
  }
  let r;
  try {
    r = await fetch(`/api/${chemin}`, { method: methode, headers: entetes, body });
  } catch (e) {
    // Pas de réseau : les créations simples sont mises en file d'attente et envoyées plus tard
    if (methode === "POST" && !(corps instanceof FormData) && HORS_LIGNE_AUTORISE.some((x) => chemin.startsWith(x))) {
      mettreEnFile(chemin, corps);
      return { hors_ligne: true, ...corps };
    }
    throw new ErreurApi("Pas de connexion au serveur. Vérifiez le réseau.", 0);
  }
  if (r.status === 401 && essai === 0 && (await rafraichir()) === true) {
    return api(chemin, { methode, corps, brut, essai: 1 });
  }
  if (r.status === 401) {
    acces = null;
    window.dispatchEvent(new Event("umurage:deconnexion"));
  }
  if (brut) return r;
  const texte = await r.text();
  const donnees = texte ? JSON.parse(texte) : null;
  if (!r.ok) throw new ErreurApi(messageErreur(r.status, donnees), r.status, donnees);
  return donnees;
}

// Télécharge un fichier protégé (export CSV, QR code) avec le jeton.
export async function telecharger(chemin, nomFichier) {
  const r = await api(chemin, { brut: true });
  if (!r.ok) throw new ErreurApi("Téléchargement impossible", r.status);
  const url = URL.createObjectURL(await r.blob());
  if (!nomFichier) return url;
  const a = document.createElement("a");
  a.href = url;
  a.download = nomFichier;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// Récupère toutes les pages d'une liste paginée.
export async function tout(chemin) {
  let page = await api(chemin);
  if (!page?.results) return page;
  const res = [...page.results];
  while (page.next) {
    const suite = page.next.split("/api/")[1];
    page = await api(suite);
    res.push(...page.results);
  }
  return res;
}

/* ------------------------------------------------------------------ Mode hors ligne
   Les enregistrements faits sans réseau (biens, entretiens) sont conservés sur l'appareil
   et envoyés automatiquement dès que la connexion revient. */
const HORS_LIGNE_AUTORISE = ["biens/", "mouvements/"];
const FILE = "umurage.file";

function lireFile() {
  try {
    return JSON.parse(localStorage.getItem(FILE)) || [];
  } catch {
    return [];
  }
}

function ecrireFile(f) {
  try {
    localStorage.setItem(FILE, JSON.stringify(f));
  } catch {
    /* stockage plein ou indisponible */
  }
  window.dispatchEvent(new CustomEvent("umurage:file", { detail: f.length }));
}

function mettreEnFile(chemin, corps) {
  ecrireFile([...lireFile(), { chemin, corps, date: new Date().toISOString() }]);
}

export const tailleFile = () => lireFile().length;

let enCours = false;
export async function synchroniser() {
  if (enCours || !navigator.onLine) return 0;
  enCours = true;
  let envoyes = 0;
  try {
    for (const item of lireFile()) {
      try {
        await api(item.chemin, { methode: "POST", corps: item.corps });
      } catch (e) {
        if (e.statut === 0) break; // toujours hors ligne : on réessaiera
        // Refusé par le serveur (données invalides) : on le retire pour ne pas bloquer la file
      }
      ecrireFile(lireFile().slice(1));
      envoyes += 1;
    }
  } finally {
    enCours = false;
  }
  if (envoyes) window.dispatchEvent(new CustomEvent("umurage:synchronise", { detail: envoyes }));
  return envoyes;
}

if (typeof window !== "undefined") window.addEventListener("online", () => synchroniser());
