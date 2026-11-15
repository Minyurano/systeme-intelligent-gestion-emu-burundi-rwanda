import { createContext, useContext, useEffect, useMemo, useState } from "react";

const Ctx = createContext(null);
const CLE = "umurage.theme";

function lire() {
  try {
    const t = localStorage.getItem(CLE);
    if (t === "light" || t === "dark") return t;
  } catch {
    /* stockage indisponible */
  }
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(lire);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem(CLE, theme);
    } catch {
      /* stockage indisponible */
    }
  }, [theme]);
  const valeur = useMemo(() => ({ theme, basculer: () => setTheme((t) => (t === "dark" ? "light" : "dark")) }), [theme]);
  return <Ctx.Provider value={valeur}>{children}</Ctx.Provider>;
}

export const useTheme = () => useContext(Ctx);

// Couleurs des graphiques pour le thème actif (les graphiques SVG ne lisent pas les variables CSS).
export function useCouleurs() {
  const { theme } = useTheme();
  return theme === "dark"
    ? { grille: "#23302a", axe: "#8a9b92", texte: "#a7b7ae", curseur: "#1a2620", lac: "#6ea3e2", critique: "#f27a6b", marque: "#3aa673", surface: "#131c18" }
    : { grille: "#e6ebe7", axe: "#74827a", texte: "#47574e", curseur: "#f1f5f2", lac: "#2766b0", critique: "#b42318", marque: "#1e6b47", surface: "#ffffff" };
}
