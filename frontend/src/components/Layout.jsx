import { createContext, useContext, useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { Bell, ChevronRight, CloudOff, FileText, Globe, Languages, LogOut, Menu, Moon, Pause, Play, Search, Sun } from "lucide-react";
import { api, synchroniser, tailleFile } from "../api";
import { useAuth } from "../auth";
import { useLangue } from "../i18n";
import { useTheme } from "../theme";
import { PAGES } from "./navigation";
import PaletteCommandes from "./PaletteCommandes";
import { useToast } from "./ui";

// Les pages peuvent préciser le dernier élément du fil d'Ariane (ex. le nom d'un bien).
const ArianeCtx = createContext(() => {});
export const useAriane = (libelle) => {
  const definir = useContext(ArianeCtx);
  useEffect(() => {
    definir(libelle);
    return () => definir(null);
  }, [libelle, definir]);
};

// Voyant de chaque compteur selon la gravité : rouge clignotant = critique, orange = à traiter, bleu = information
const VOYANTS = {
  alertes: (c) => (c.alertes_critiques ? ["critique clignote", "Alerte critique d'un capteur"] : ["attention", "Alertes de capteurs"]),
  echeances: (c) => (c.echeances_retard ? ["critique clignote", `${c.echeances_retard} échéance(s) en retard`] : ["attention", "Échéances dans les 7 jours"]),
  ordres_urgents: (c) => (c.ordres_critiques ? ["critique clignote", `${c.ordres_critiques} travail(aux) urgent(s)`] : ["attention", "Travaux prioritaires"]),
  loyers_impayes: (c) => (c.loyers_impayes_anciens ? ["critique", "Loyers impayés depuis plus de 60 jours"] : ["attention", "Loyers impayés"]),
  approbations: () => ["attention", "Demandes qui attendent votre décision"],
  anomalies: () => ["attention", "Transactions signalées par l'IA"],
  declarations: () => ["info", "Déclarations du terrain à valider"],
  demandes_acces: () => ["info", "Demandes d'accès de membres à traiter"],
};
export const voyant = (cle, c) => {
  const [classe, titre] = (VOYANTS[cle] || (() => ["doux", ""]))(c);
  return { classe, titre };
};

const initiales = (nom = "") => nom.split(/\s+/).filter(Boolean).slice(0, 2).map((m) => m[0]).join("").toUpperCase();

// Suit l'état du réseau et la file des enregistrements faits hors ligne.
function useHorsLigne() {
  const [enLigne, setEnLigne] = useState(navigator.onLine);
  const [file, setFile] = useState(tailleFile());
  const notifier = useToast();
  const { t } = useLangue();
  useEffect(() => {
    const on = () => { setEnLigne(true); synchroniser(); };
    const off = () => setEnLigne(false);
    const f = (e) => setFile(e.detail);
    const s = (e) => notifier(t("hors_ligne.envoyes", { n: e.detail }));
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    window.addEventListener("umurage:file", f);
    window.addEventListener("umurage:synchronise", s);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
      window.removeEventListener("umurage:file", f);
      window.removeEventListener("umurage:synchronise", s);
    };
  }, [notifier, t]);
  return { enLigne, file };
}

export default function Layout() {
  const { moi, deconnexion, peut } = useAuth();
  const { theme, basculer } = useTheme();
  const { t, langue, setLangue } = useLangue();
  const [ouvert, setOuvert] = useState(false);
  const [palette, setPalette] = useState(false);
  const [menu, setMenu] = useState(null);
  const [compteurs, setCompteurs] = useState({});
  const [alertes, setAlertes] = useState([]);
  const [detail, setDetail] = useState(null);
  const { enLigne, file } = useHorsLigne();
  const loc = useLocation();
  const nav = useNavigate();
  const refMenu = useRef(null);
  const org = moi.organisation || {};

  useEffect(() => {
    const charger = () => Promise.all([api("compteurs/").catch(() => ({})), api("metier/compteurs/").catch(() => ({}))])
      .then(([a, b]) => setCompteurs({ ...a, ...b }));
    charger();
    const tm = setInterval(charger, 60000);
    return () => clearInterval(tm);
  }, [loc.pathname]);

  useEffect(() => {
    setOuvert(false);
    setMenu(null);
  }, [loc.pathname]);

  useEffect(() => {
    const k = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPalette(true);
      }
    };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, []);

  useEffect(() => {
    if (!menu) return;
    const clic = (e) => !refMenu.current?.contains(e.target) && setMenu(null);
    document.addEventListener("mousedown", clic);
    return () => document.removeEventListener("mousedown", clic);
  }, [menu]);

  // Pause des animations (préférence de ce navigateur)
  const [voyantsPause, setVoyantsPause] = useState(() => {
    try { return localStorage.getItem("umurage.voyants") === "pause"; } catch { return false; }
  });
  useEffect(() => {
    document.documentElement.dataset.voyants = voyantsPause ? "pause" : "actifs";
    try { localStorage.setItem("umurage.voyants", voyantsPause ? "pause" : "actifs"); } catch { /* stockage indisponible */ }
  }, [voyantsPause]);
  const basculerVoyants = () => setVoyantsPause((v) => !v);

  async function ouvrirAlertes() {
    if (menu === "alertes") return setMenu(null);
    setMenu("alertes");
    setAlertes(await api("alertes/?resolue=false").catch(() => []));
  }

  const page = PAGES.flatMap((g) => g.items).find((p) => (p.to === "/" ? loc.pathname === "/" : loc.pathname.startsWith(p.to)));
  const nbNotifs = (compteurs.alertes || 0) + (compteurs.anomalies || 0) + (peut("declarations") ? compteurs.declarations || 0 : 0)
    + (compteurs.approbations || 0) + (compteurs.demandes_acces || 0) + (compteurs.echeances_retard || 0) + (compteurs.ordres_critiques || 0) + (compteurs.loyers_impayes || 0);
  const nbUrgences = (compteurs.alertes_critiques || 0) + (compteurs.echeances_retard || 0) + (compteurs.ordres_critiques || 0);
  const critique = nbUrgences > 0;
  // Titre de l'onglet : le nombre d'urgences reste visible même quand l'onglet est en arrière-plan
  useEffect(() => {
    const base = page ? `${t(page.libelle)} — UMURAGE` : "UMURAGE";
    document.title = nbUrgences > 0 ? `(${nbUrgences}) ⚠ ${base}` : base;
  }, [nbUrgences, page, t]);
  const changerLangue = () => setLangue(langue === "fr" ? "en" : "fr");

  return (
    <ArianeCtx.Provider value={setDetail}>
      <div className="app">
        <aside className={`barre${ouvert ? " ouverte" : ""}`} aria-label="Navigation">
          <Link to="/" className="marque">
            <img src="/logo.svg" alt="" />
            <div>
              <strong>UMURAGE</strong>
              <span>{org.nom}</span>
            </div>
          </Link>
          <nav className="nav">
            {PAGES.map((g) => {
              const items = g.items.filter((i) => !i.droit || peut(i.droit));
              if (!items.length) return null;
              return (
                <div key={g.groupe}>
                  <div className="nav-groupe">{t(g.groupe)}</div>
                  {items.map((i) => (
                    <NavLink key={i.to} to={i.to} end={i.to === "/"}>
                      <i.icone />
                      {t(i.libelle)}
                      {i.compteur && compteurs[i.compteur] > 0 && (
                        <span className={`compteur ${voyant(i.compteur, compteurs).classe}`} title={voyant(i.compteur, compteurs).titre}>{compteurs[i.compteur]}</span>
                      )}
                    </NavLink>
                  ))}
                </div>
              );
            })}
            <div className="nav-groupe">{t("nav.transparence")}</div>
            <a href={`/public/${org.slug || ""}`} target="_blank" rel="noreferrer">
              <Globe />
              {t("nav.portail")}
            </a>
            <div className="legende-voyants" aria-label="Légende des voyants">
              <span title="Danger immédiat : retard, urgence, alerte critique"><i className="v-urgence" style={{ background: "rgb(var(--v-urgence))" }} />Urgence</span>
              <span title="Risque élevé, à planifier rapidement"><i className="v-eleve" style={{ background: "rgb(var(--v-eleve))" }} />Élevé</span>
              <span title="À traiter dans les prochains jours"><i className="v-attention" style={{ background: "rgb(var(--v-attention))" }} />À traiter</span>
              <span title="Pour information"><i className="v-info" style={{ background: "rgb(var(--v-info))" }} />Information</span>
              <span title="Situation normale"><i style={{ background: "rgb(var(--v-normal))" }} />Normal</span>
              <button className="pause" onClick={basculerVoyants} aria-pressed={voyantsPause}>
                {voyantsPause ? <><Play />Animer les voyants</> : <><Pause />Figer les voyants</>}
              </button>
            </div>
          </nav>
          <div className="barre-pied">
            {org.sigle}{org.pays ? `, ${org.pays}` : ""}
            <br />
            UMURAGE {__UMURAGE_VERSION__}{org.statut === "ESSAI" ? " — essai" : ""}
          </div>
        </aside>

        <div className="zone-principale">
          {(!enLigne || file > 0) && (
            <div className="bandeau-reseau" role="status">
              <CloudOff size={16} />
              <b>{!enLigne ? t("hors_ligne.titre") : ""}</b>
              <span>{file > 0 ? t("hors_ligne.attente", { n: file }) : t("hors_ligne.consultation")}</span>
            </div>
          )}
          <header className="haut">
            <button className="icone-bouton menu-mobile" aria-label="Menu" onClick={() => setOuvert(true)}><Menu /></button>
            <nav className="ariane" aria-label="Fil d'Ariane">
              <span className="intermediaire">{moi.district_nom || org.sigle}</span>
              <ChevronRight className="intermediaire" />
              {detail ? (
                <>
                  <Link to={page?.to || "/"} className="intermediaire">{page && t(page.libelle)}</Link>
                  <ChevronRight className="intermediaire" />
                  <b>{detail}</b>
                </>
              ) : (
                <b>{page ? t(page.libelle) : "UMURAGE"}</b>
              )}
            </nav>

            <div className="haut-droite" ref={refMenu}>
              <button className="recherche-declencheur" onClick={() => setPalette(true)} aria-label={t("haut.rechercher")}>
                <Search />
                <span className="libelle">{t("haut.rechercher")}</span>
                <kbd>Ctrl K</kbd>
              </button>

              <div className="menu-utilisateur">
                <button className="icone-bouton" onClick={ouvrirAlertes} aria-label={`${t("haut.notifications")} (${nbNotifs})`} aria-expanded={menu === "alertes"}>
                  <Bell />
                  {nbNotifs > 0 && <span className={`point-alerte${critique ? " clignote" : ""}`}>{nbNotifs > 9 ? "9+" : nbNotifs}</span>}
                </button>
                {menu === "alertes" && (
                  <div className="deroulant" style={{ width: 360 }}>
                    <div className="entete"><h3>{t("haut.notifications")}</h3></div>
                    {peut("declarations") && compteurs.declarations > 0 && (
                      <button onClick={() => nav("/declarations")}>
                        <span className="badge info">WhatsApp</span>
                        <span className="petit">{t("notif.declarations", { n: compteurs.declarations })}</span>
                      </button>
                    )}
                    {alertes.map((a) => (
                      <button key={a.id} onClick={() => nav("/capteurs")}>
                        <span className={`badge ${a.niveau === "CRITIQUE" ? "critique" : "attention"}`}>{a.niveau_libelle}</span>
                        <span className="petit" style={{ lineHeight: 1.35 }}>{a.message}</span>
                      </button>
                    ))}
                    {compteurs.anomalies > 0 && (
                      <button onClick={() => nav("/finances")}>
                        <span className="badge attention">{t("nav.finances_page")}</span>
                        <span className="petit">{t("notif.anomalies", { n: compteurs.anomalies })}</span>
                      </button>
                    )}
                    {compteurs.echeances_retard > 0 && (
                      <button onClick={() => nav("/echeancier")}><span className="badge critique">Retard</span><span className="petit">{compteurs.echeances_retard} échéance(s) dépassée(s)</span></button>
                    )}
                    {compteurs.ordres_critiques > 0 && (
                      <button onClick={() => nav("/maintenance")}><span className="badge critique">Urgent</span><span className="petit">{compteurs.ordres_critiques} travail(aux) urgent(s) à lancer</span></button>
                    )}
                    {compteurs.approbations > 0 && (
                      <button onClick={() => nav("/approbations")}><span className="badge attention">Décision</span><span className="petit">{compteurs.approbations} demande(s) attendent votre décision</span></button>
                    )}
                    {peut("acces_membres") && compteurs.demandes_acces > 0 && (
                      <button onClick={() => nav("/acces-membres")}><span className="badge info">Membres</span><span className="petit">{compteurs.demandes_acces} demande(s) d'accès à traiter</span></button>
                    )}
                    {compteurs.loyers_impayes > 0 && (
                      <button onClick={() => nav("/locations")}><span className={`badge ${compteurs.loyers_impayes_anciens ? "critique" : "attention"}`}>Loyers</span><span className="petit">{compteurs.loyers_impayes} loyer(s) impayé(s)</span></button>
                    )}
                    {nbNotifs === 0 && <p className="petit muet" style={{ padding: 10 }}>{t("haut.aucune_notif")}</p>}
                  </div>
                )}
              </div>

              <button className="icone-bouton" onClick={basculer} aria-label={theme === "dark" ? t("haut.theme_clair") : t("haut.theme_sombre")}>
                {theme === "dark" ? <Sun /> : <Moon />}
              </button>

              <div className="menu-utilisateur">
                <button onClick={() => setMenu(menu === "compte" ? null : "compte")} aria-expanded={menu === "compte"}>
                  <span className="avatar">{initiales(moi.nom)}</span>
                  <span className="qui">
                    <b>{moi.nom}</b>
                    <span>{moi.role_libelle}</span>
                  </span>
                </button>
                {menu === "compte" && (
                  <div className="deroulant">
                    <div className="entete">
                      <b>{moi.nom}</b>
                      <div className="petit muet">
                        {moi.role_libelle}, {moi.district_nom ? t("haut.district_de", { d: moi.district_nom }) : t("haut.tous_districts")}
                      </div>
                      <div className="petit muet">{org.nom}</div>
                    </div>
                    <Link to="/rapport"><FileText />{t("nav.rapport")}</Link>
                    <a href={`/public/${org.slug || ""}`} target="_blank" rel="noreferrer"><Globe />{t("nav.portail")}</a>
                    <button onClick={changerLangue}><Languages />{t("haut.langue")}</button>
                    <button onClick={basculer}>{theme === "dark" ? <Sun /> : <Moon />}{theme === "dark" ? t("haut.theme_clair") : t("haut.theme_sombre")}</button>
                    <button onClick={deconnexion}><LogOut />{t("haut.deconnexion")}</button>
                  </div>
                )}
              </div>
            </div>
          </header>

          <main className="contenu" id="contenu">
            <Outlet />
          </main>
        </div>
        {palette && <PaletteCommandes onFermer={() => setPalette(false)} />}
      </div>
    </ArianeCtx.Provider>
  );
}
