import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Boxes, CornerDownLeft, FileText, FolderKanban, Search } from "lucide-react";
import { api } from "../api";
import { useAuth } from "../auth";
import { useT } from "../i18n";
import { PAGES } from "./navigation";

const ICONES = { Bien: Boxes, Projet: FolderKanban, Document: FileText };

// Recherche globale ouverte par Ctrl+K : pages de l'application et données (biens, projets, documents).
export default function PaletteCommandes({ onFermer }) {
  const { peut } = useAuth();
  const t = useT();
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const [resultats, setResultats] = useState([]);
  const [sel, setSel] = useState(0);

  useEffect(() => {
    if (q.trim().length < 2) {
      setResultats([]);
      return;
    }
    const t = setTimeout(() => api(`recherche/?q=${encodeURIComponent(q.trim())}`).then(setResultats).catch(() => setResultats([])), 180);
    return () => clearTimeout(t);
  }, [q]);

  const pages = useMemo(
    () =>
      PAGES.flatMap((g) => g.items)
        .filter((p) => !p.droit || peut(p.droit))
        .filter((p) => t(p.libelle).toLowerCase().includes(q.trim().toLowerCase()))
        .map((p) => ({ type: "Page", titre: t(p.libelle), detail: "Aller à la page", lien: p.to, icone: p.icone })),
    [q, peut, t]
  );
  const items = [...resultats.map((r) => ({ ...r, icone: ICONES[r.type] })), ...pages];

  useEffect(() => setSel(0), [q, resultats.length]);

  function aller(item) {
    if (!item) return;
    nav(item.lien);
    onFermer();
  }

  function touche(e) {
    if (e.key === "ArrowDown") { e.preventDefault(); setSel((s) => Math.min(items.length - 1, s + 1)); }
    if (e.key === "ArrowUp") { e.preventDefault(); setSel((s) => Math.max(0, s - 1)); }
    if (e.key === "Enter") aller(items[sel]);
    if (e.key === "Escape") onFermer();
  }

  let groupe = null;
  return (
    <div className="voile palette" onMouseDown={(e) => e.target === e.currentTarget && onFermer()}>
      <div className="modale" role="dialog" aria-modal="true" aria-label="Recherche">
        <div className="palette-saisie">
          <Search />
          <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={touche}
            placeholder="Rechercher un bien, un code, un projet, un document…" aria-label="Rechercher" />
          <kbd>Échap</kbd>
        </div>
        <div className="palette-liste" role="listbox">
          {items.length === 0 && <p className="petit muet" style={{ padding: "18px 12px" }}>{q.length < 2 ? "Tapez au moins deux lettres." : "Aucun résultat."}</p>}
          {items.map((it, i) => {
            const titreGroupe = it.type !== groupe ? (groupe = it.type) : null;
            const Ic = it.icone || Search;
            return (
              <div key={`${it.type}-${it.lien}-${i}`}>
                {titreGroupe && <div className="palette-groupe">{{ Bien: "Biens", Projet: "Projets", Document: "Documents", Page: "Pages" }[titreGroupe]}</div>}
                <div className="palette-item" role="option" aria-selected={i === sel} onMouseEnter={() => setSel(i)} onClick={() => aller(it)}>
                  <span className="ic"><Ic /></span>
                  <div><b>{it.titre}</b><span>{it.detail}</span></div>
                </div>
              </div>
            );
          })}
        </div>
        <div className="palette-pied">
          <span><kbd>↑</kbd> <kbd>↓</kbd> pour naviguer</span>
          <span><kbd><CornerDownLeft size={10} style={{ display: "inline" }} /></kbd> pour ouvrir</span>
        </div>
      </div>
    </div>
  );
}
