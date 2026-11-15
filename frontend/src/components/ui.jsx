import { createContext, useCallback, useContext, useEffect, useId, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertTriangle, ArrowDown, ArrowUp, ArrowUpDown, CheckCircle2, ChevronLeft, ChevronRight, CircleAlert, Info, Inbox, X,
} from "lucide-react";
import { api } from "../api";

/* ------------------------------------------------------------------ Données */

// Charge une ressource de l'API : { donnees, erreur, chargement, recharger }.
export function useApi(chemin, deps = []) {
  const [etat, setEtat] = useState({ donnees: null, erreur: null, chargement: !!chemin });
  const recharger = useCallback(async () => {
    if (!chemin) return;
    setEtat((e) => ({ ...e, chargement: true }));
    try {
      const d = await api(chemin);
      setEtat({ donnees: d, erreur: null, chargement: false });
    } catch (e) {
      setEtat({ donnees: null, erreur: e.message, chargement: false });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chemin, ...deps]);
  useEffect(() => {
    recharger();
  }, [recharger]);
  return { ...etat, recharger };
}

/* ------------------------------------------------------------------ Notifications */

const ToastCtx = createContext(() => {});

export function ToastProvider({ children }) {
  const [liste, setListe] = useState([]);
  const notifier = useCallback((message, type = "succes") => {
    const id = Math.random().toString(36).slice(2);
    setListe((l) => [...l, { id, message, type }]);
    setTimeout(() => setListe((l) => l.filter((t) => t.id !== id)), 4000);
  }, []);
  return (
    <ToastCtx.Provider value={notifier}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {liste.map((t) => (
          <div key={t.id} className={`toast ${t.type}`}>
            {t.type === "erreur" ? <CircleAlert /> : <CheckCircle2 />}
            {t.message}
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}
export const useToast = () => useContext(ToastCtx);

/* ------------------------------------------------------------------ Mise en page */

export function EnTete({ titre, sousTitre, children }) {
  return (
    <div className="entete-page">
      <div>
        <h1>{titre}</h1>
        {sousTitre && <p className="sous-titre">{sousTitre}</p>}
      </div>
      {children && <div className="actions">{children}</div>}
    </div>
  );
}

export function Carte({ titre, description, actions, children, plein, brut, pied, className = "", style }) {
  return (
    <section className={`carte-ui ${className}`} style={style}>
      {(titre || actions) && (
        <div className="carte-tete">
          <div>
            {titre && <h2>{titre}</h2>}
            {description && <p className="description">{description}</p>}
          </div>
          {actions && <div className="actions">{actions}</div>}
        </div>
      )}
      {brut ? children : <div className={`carte-corps${plein ? " plein" : ""}`}>{children}</div>}
      {pied && <div className="carte-pied">{pied}</div>}
    </section>
  );
}

/* ------------------------------------------------------------------ États */

export function Squelette({ lignes = 3, hauteur = 16, style }) {
  return (
    <div style={{ display: "grid", gap: 10, ...style }} aria-busy="true" aria-label="Chargement">
      {Array.from({ length: lignes }).map((_, i) => (
        <div key={i} className="squelette" style={{ height: hauteur, width: `${100 - ((i * 13) % 35)}%` }} />
      ))}
    </div>
  );
}

export function Etat({ chargement, erreur, children, lignes = 4 }) {
  if (erreur) return <Bandeau type="erreur">{erreur}</Bandeau>;
  if (chargement) return <Squelette lignes={lignes} />;
  return children;
}

export function Bandeau({ type = "info", children, style }) {
  const Ic = { erreur: CircleAlert, attention: AlertTriangle, succes: CheckCircle2, info: Info }[type];
  return (
    <div className={`bandeau ${type}`} role={type === "erreur" ? "alert" : "status"} style={style}>
      <Ic />
      <div>{children}</div>
    </div>
  );
}

export function Vide({ icone: Ic = Inbox, titre, texte, action }) {
  return (
    <div className="vide">
      <div className="icone"><Ic /></div>
      {titre && <b>{titre}</b>}
      {texte && <p className="petit" style={{ maxWidth: "46ch" }}>{texte}</p>}
      {action}
    </div>
  );
}

/* ------------------------------------------------------------------ Indicateurs */

export function Kpi({ libelle, valeur, unite, icone: Ic, ton, note, noteTon, serie, couleurSerie, lien }) {
  const contenu = (
    <>
      <div className="kpi-tete">
        <span>{libelle}</span>
        {Ic && <div className={`kpi-icone ${ton || ""}`}><Ic /></div>}
      </div>
      <div className="kpi-valeur">
        {valeur}
        {unite && <small>{unite}</small>}
      </div>
      <div className="kpi-bas">
        <span className={`kpi-note ${noteTon || ""}`}>{note}</span>
        {serie && serie.length > 1 && <MiniCourbe valeurs={serie} couleur={couleurSerie} />}
      </div>
    </>
  );
  return lien ? <Link to={lien} className="kpi">{contenu}</Link> : <div className="kpi">{contenu}</div>;
}

export function MiniCourbe({ valeurs, couleur = "var(--marque)", largeur = 84, hauteur = 24 }) {
  const id = useId();
  const min = Math.min(...valeurs);
  const max = Math.max(...valeurs);
  const pas = largeur / (valeurs.length - 1);
  const y = (v) => hauteur - 2 - ((v - min) / (max - min || 1)) * (hauteur - 4);
  const points = valeurs.map((v, i) => `${(i * pas).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  return (
    <svg width={largeur} height={hauteur} viewBox={`0 0 ${largeur} ${hauteur}`} aria-hidden="true" style={{ overflow: "visible" }}>
      <defs>
        <linearGradient id={id} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor={couleur} stopOpacity="0.18" />
          <stop offset="1" stopColor={couleur} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={`0,${hauteur} ${points} ${largeur},${hauteur}`} fill={`url(#${id})`} />
      <polyline points={points} fill="none" stroke={couleur} strokeWidth="1.6" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={largeur} cy={y(valeurs[valeurs.length - 1])} r="2.4" fill={couleur} />
    </svg>
  );
}

const TON_ETAT = { BON: "bon", MOYEN: "attention", MAUVAIS: "critique", CONSTRUCTION: "info" };
export function BadgeEtat({ etat, libelle }) {
  return (
    <span className={`badge ${TON_ETAT[etat] || ""}`}>
      {libelle}
    </span>
  );
}

// Niveau de voyant d'un score de risque : ≥ 85 urgence, ≥ 70 élevé, ≥ 50 à traiter
export const niveauVoyant = (s) => (s >= 85 ? "n-urgence" : s >= 70 ? "n-eleve" : s >= 50 ? "n-attention" : "");

export function Risque({ score }) {
  if (score === null || score === undefined) return <span className="muet">—</span>;
  const s = Math.round(score);
  const couleur = s >= 70 ? "var(--critique)" : s >= 40 ? "var(--sorgho)" : "var(--succes)";
  const mot = s >= 70 ? "élevé" : s >= 40 ? "moyen" : "faible";
  return (
    <span className={`jauge-risque ${niveauVoyant(s)}`} title={`Risque ${mot} : ${s} sur 100`}>
      <span className="piste"><span style={{ width: `${Math.max(4, s)}%`, background: couleur }} /></span>
      <b style={{ color: couleur }}>{s}</b>
      <span className="sr">Risque {mot}</span>
    </span>
  );
}

export function Progres({ valeur, couleur }) {
  return (
    <div className="progres" role="progressbar" aria-valuenow={valeur} aria-valuemin={0} aria-valuemax={100}>
      <div className="piste"><span style={{ width: `${Math.min(100, valeur)}%`, background: couleur }} /></div>
      <b>{Math.round(Number(valeur) || 0)} %</b>
    </div>
  );
}

/* ------------------------------------------------------------------ Navigation interne */

export function Onglets({ onglets, actif, onChange }) {
  return (
    <div className="onglets" role="tablist">
      {onglets.map((o) => (
        <button key={o.id} role="tab" aria-selected={actif === o.id} onClick={() => onChange(o.id)}>
          {o.icone && <o.icone size={16} />}
          {o.libelle}
          {o.nb !== undefined && <span className="nb">{o.nb}</span>}
        </button>
      ))}
    </div>
  );
}

export function Segments({ options, valeur, onChange, label }) {
  return (
    <div className="segments" role="tablist" aria-label={label}>
      {options.map((o) => (
        <button key={o.id} role="tab" aria-selected={valeur === o.id} onClick={() => onChange(o.id)}>
          {o.libelle}
          {o.nb ? <span className="nb">{o.nb}</span> : null}
        </button>
      ))}
    </div>
  );
}

export function Pagination({ page, total, parPage = 50, onChange, unite = "éléments" }) {
  const nbPages = Math.max(1, Math.ceil(total / parPage));
  const pages = [];
  for (let p = 1; p <= nbPages; p++) {
    if (p === 1 || p === nbPages || Math.abs(p - page) <= 1) pages.push(p);
    else if (pages[pages.length - 1] !== "…") pages.push("…");
  }
  const debut = total ? (page - 1) * parPage + 1 : 0;
  return (
    <div className="pagination">
      <span>
        {debut}–{Math.min(page * parPage, total)} sur {total} {unite}
      </span>
      {nbPages > 1 && (
        <div className="pages">
          <button aria-label="Page précédente" disabled={page <= 1} onClick={() => onChange(page - 1)}><ChevronLeft /></button>
          {pages.map((p, i) =>
            p === "…" ? <span key={`e${i}`} className="muet">…</span> : (
              <button key={p} aria-current={p === page ? "page" : undefined} onClick={() => onChange(p)}>{p}</button>
            )
          )}
          <button aria-label="Page suivante" disabled={page >= nbPages} onClick={() => onChange(page + 1)}><ChevronRight /></button>
        </div>
      )}
    </div>
  );
}

// En-tête de colonne triable. `tri` vaut "champ" ou "-champ".
export function ColonneTri({ champ, tri, onTri, children, num }) {
  const actif = tri === champ || tri === `-${champ}`;
  const desc = tri === `-${champ}`;
  const Ic = !actif ? ArrowUpDown : desc ? ArrowDown : ArrowUp;
  return (
    <th className={num ? "num" : undefined} aria-sort={actif ? (desc ? "descending" : "ascending") : "none"}>
      <button onClick={() => onTri(actif && !desc ? `-${champ}` : champ)}>
        {children}
        <Ic style={{ opacity: actif ? 1 : 0.4 }} />
      </button>
    </th>
  );
}

/* ------------------------------------------------------------------ Modale */

export function Modale({ titre, description, onFermer, children, pied, largeur }) {
  const ref = useRef(null);
  useEffect(() => {
    const k = (e) => e.key === "Escape" && onFermer();
    window.addEventListener("keydown", k);
    ref.current?.querySelector("input, select, textarea, button")?.focus();
    return () => window.removeEventListener("keydown", k);
  }, [onFermer]);
  return (
    <div className="voile" onMouseDown={(e) => e.target === e.currentTarget && onFermer()}>
      <div className="modale" role="dialog" aria-modal="true" aria-label={titre} ref={ref} style={largeur ? { width: `min(${largeur}px, 100%)` } : undefined}>
        <header>
          <div>
            <h2 style={{ fontSize: "1.2rem" }}>{titre}</h2>
            {description && <p>{description}</p>}
          </div>
          <button className="icone-bouton" onClick={onFermer} aria-label="Fermer"><X /></button>
        </header>
        <div className="corps">{children}</div>
        {pied && <footer>{pied}</footer>}
      </div>
    </div>
  );
}

export function Champ({ libelle, aide, large, children }) {
  return (
    <label className={`champ${large ? " large" : ""}`}>
      {libelle}
      {children}
      {aide && <span className="aide">{aide}</span>}
    </label>
  );
}

/* ------------------------------------------------------------------ Graphiques */

export function InfoBulle({ active, payload, label, format = (v) => v, titre, filtre }) {
  if (!active || !payload?.length) return null;
  const lignes = filtre ? filtre(payload) : payload;
  return (
    <div className="infobulle">
      <strong>{titre ? titre(label, lignes) : label}</strong>
      {lignes.map((p) => (
        <div key={p.dataKey} className="ligne">
          <span><i className="pastille" style={{ background: p.color || p.fill }} />{p.name}</span>
          <b>{format(p.value)}</b>
        </div>
      ))}
    </div>
  );
}
