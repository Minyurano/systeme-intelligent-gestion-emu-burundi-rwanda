import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, enregistrerJetons, fermerSession, rafraichir, synchroniser } from "./api";
import { definirDevise } from "./format";
import { useLangue } from "./i18n";

const Ctx = createContext(null);

export function AuthProvider({ children }) {
  const { setLangue, choisie } = useLangue();
  const [moi, setMoi] = useState(null);
  const [pret, setPret] = useState(false);

  // Profil gardé sur l'appareil (sans aucun jeton) pour rouvrir l'application hors ligne
  const MOI = "umurage.moi";
  const garder = (m) => { try { m ? localStorage.setItem(MOI, JSON.stringify(m)) : localStorage.removeItem(MOI); } catch { /* indisponible */ } };
  const garde = () => { try { return JSON.parse(localStorage.getItem(MOI)); } catch { return null; } };

  const charger = useCallback(async () => {
    const session = await rafraichir(); // cookie HttpOnly → nouveau jeton d'accès en mémoire
    if (session === "reseau") {
      // Pas de réseau : on rouvre avec le dernier profil connu ; les pages lisent les données mises en cache
      const m = garde();
      if (m) { definirDevise(m.organisation?.devise); setMoi({ ...m, hors_ligne: true }); }
      setPret(true);
      return;
    }
    if (!session) {
      garder(null);
      setMoi(null);
      setPret(true);
      return;
    }
    try {
      const m = await api("moi/");
      // Monnaie et langue de l'organisation (sauf si l'utilisateur a choisi sa langue)
      definirDevise(m.organisation?.devise);
      if (!choisie && m.organisation?.langue) setLangue(m.organisation.langue, false);
      setMoi(m);
      garder(m);
      synchroniser();
    } catch {
      setMoi(null);
    }
    setPret(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    charger();
    const fin = () => setMoi(null);
    window.addEventListener("umurage:deconnexion", fin);
    return () => window.removeEventListener("umurage:deconnexion", fin);
  }, [charger]);

  async function connexion(username, password, code) {
    let r;
    try {
      r = await fetch("/api/auth/token/", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(code ? { username, password, code } : { username, password }),
      });
    } catch {
      throw new Error("Le serveur ne répond pas. Vérifiez que le backend Django est lancé.");
    }
    if (r.status === 401) {
      const corps = await r.json().catch(() => ({}));
      if (corps.otp_requis) {
        const err = new Error(code ? "Code de vérification incorrect." : "Saisissez le code à 6 chiffres de votre application d'authentification.");
        err.otp = true;
        throw err;
      }
      throw new Error("Identifiant ou mot de passe incorrect.");
    }
    if (!r.ok) throw new Error("Le serveur ne répond pas. Vérifiez que le backend Django est lancé (python manage.py runserver).");
    enregistrerJetons(await r.json()); // jeton d'accès en mémoire ; le rafraîchissement est dans le cookie
    const m = await api("moi/");
    definirDevise(m.organisation?.devise);
    if (!choisie && m.organisation?.langue) setLangue(m.organisation.langue, false);
    setMoi(m);
    garder(m);
    synchroniser();
  }

  async function deconnexion() {
    garder(null);
    setMoi(null);
    await fermerSession();
  }

  // Droits d'écriture par rôle (le serveur les vérifie aussi)
  const peut = (domaine) => {
    if (!moi) return false;
    const r = moi.role;
    const regles = {
      inventaire: ["ADMIN", "SURINTENDANT", "AGENT"],
      finances: ["ADMIN", "TRESORIER"],
      projets: ["ADMIN", "SURINTENDANT"],
      declarations: ["ADMIN", "SURINTENDANT", "EVEQUE"],
      parametres: ["ADMIN"],
      import: ["ADMIN", "SURINTENDANT", "AGENT"],
      analyses: ["ADMIN", "TRESORIER", "EVEQUE"],
      journal: ["ADMIN", "EVEQUE"],
      comptabilite: ["ADMIN", "TRESORIER", "EVEQUE"],
      documents: ["ADMIN", "SURINTENDANT", "AGENT", "TRESORIER", "EVEQUE"],
      acces_membres: ["ADMIN"],
      contributions: ["ADMIN", "TRESORIER", "EVEQUE", "SURINTENDANT", "AGENT"],
    };
    return (regles[domaine] || ["ADMIN"]).includes(r);
  };

  return <Ctx.Provider value={{ moi, pret, connexion, deconnexion, peut, rafraichir: charger }}>{children}</Ctx.Provider>;
}

export const useAuth = () => useContext(Ctx);
