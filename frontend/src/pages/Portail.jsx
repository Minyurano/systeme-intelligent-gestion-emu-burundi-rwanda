import { useEffect, useState } from "react";
import { CircleMarker, MapContainer, Popup, TileLayer } from "react-leaflet";
import { Droplets, GraduationCap, HandHeart, HeartPulse, LogIn } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { useLangue } from "../i18n";
import { Bandeau, Kpi, Progres, Squelette } from "../components/ui";
import { nombre } from "../format";
import { useTheme } from "../theme";

const TON = { "En cours": "info", "Terminé": "bon", "Prévu": "", "Suspendu": "critique" };

// Portail de transparence : sans compte, uniquement des données d'impact agrégées.
export default function Portail() {
  const { theme } = useTheme();
  const { slug } = useParams();
  const { t, setLangue, choisie } = useLangue();
  const [d, setD] = useState(null);
  const [erreur, setErreur] = useState("");
  useEffect(() => {
    fetch(`/api/public/${slug ? `?organisation=${encodeURIComponent(slug)}` : ""}`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((x) => {
        setD(x);
        if (!choisie && x.organisation?.langue) setLangue(x.organisation.langue, false);
        document.title = `${x.organisation.sigle} — UMURAGE`;
      })
      .catch(() => setErreur(t("pt.indispo")));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug]);
  const tuiles = theme === "dark" ? "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png" : "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";

  return (
    <div className="portail-page">
      <header className="portail-entete">
        <div className="portail-largeur">
          <nav className="portail-nav">
            <img src="/logo.svg" alt="" width="36" height="36" />
            <span style={{ fontWeight: 600 }}>{d?.organisation.nom || "UMURAGE"}</span>
            <Link to="/connexion" className="bouton petit"><LogIn />{t("pt.espace")}</Link>
          </nav>
          <h1>{t("pt.titre")}{d ? ` — ${d.organisation.pays}` : ""}</h1>
          <p className="accroche">{t("pt.accroche")}</p>
        </div>
        <svg className="collines" viewBox="0 0 1200 160" preserveAspectRatio="none" aria-hidden="true">
          <path d="M0 90C160 50 300 36 460 46s240 46 400 38 240-44 340-52v128H0z" fill="#164a33" />
          <path d="M0 120c180-30 340-40 500-30s220 28 380 24 220-26 320-32v78H0z" fill="#1a5a3d" />
          <path d="M0 160V140c200-14 380-18 560-12s240 12 380 10 180-8 260-12v34z" fill="var(--fond)" />
        </svg>
      </header>

      <div className="portail-largeur">
        {erreur && <Bandeau type="erreur" style={{ marginTop: 20 }}>{erreur}</Bandeau>}
        {!d && !erreur && <Squelette lignes={6} hauteur={24} style={{ marginTop: 20 }} />}
        {d && (
          <>
            <div className="chiffres-publics">
              <Kpi libelle={t("pt.eau")} icone={Droplets} ton="info" valeur={nombre(d.chiffres.personnes_eau)} note={t("pt.eau_n", { n: d.chiffres.forages })} />
              <Kpi libelle={t("pt.sante")} icone={HeartPulse} ton="critique" valeur={d.chiffres.centres_sante} note={t("pt.sante_n")} />
              <Kpi libelle={t("pt.education")} icone={GraduationCap} ton="attention" valeur={d.chiffres.ecoles} note={t("pt.education_n")} />
              <Kpi libelle={t("pt.benef")} icone={HandHeart} ton="bon" valeur={nombre(d.chiffres.beneficiaires)} note={t("pt.benef_n", { n: d.chiffres.projets })} />
            </div>

            <section className="portail-section">
              <h2>{t("pt.ou")}</h2>
              <p>{t("pt.ou_sous", { n: d.chiffres.districts })}</p>
              <div className="carte-geo" style={{ height: 440, minHeight: 0 }}>
                <MapContainer key={theme} center={[-3.35, 29.95]} zoom={8} style={{ height: "100%" }} scrollWheelZoom={false}>
                  <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' url={tuiles} />
                  {d.projets.filter((p) => p.lat).map((p) => (
                    <CircleMarker key={p.nom} center={[p.lat, p.lon]} radius={9} pathOptions={{ color: theme === "dark" ? "#131c18" : "#fff", weight: 2, fillColor: "#1E8A57", fillOpacity: 1 }}>
                      <Popup><b>{p.nom}</b>{p.district}, {p.statut.toLowerCase()}, {p.avancement} %</Popup>
                    </CircleMarker>
                  ))}
                </MapContainer>
              </div>
            </section>

            <section className="portail-section">
              <h2>{t("pt.projets")}</h2>
              <p>{t("pt.projets_sous")}</p>
              <div className="grille g3">
                {d.projets.map((p) => (
                  <article key={p.nom} className="carte-projet">
                    <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                      <span className="badge">{p.domaine}</span>
                      <span className={`badge ${TON[p.statut] || ""}`}>{p.statut}</span>
                    </div>
                    <h3>{p.nom}</h3>
                    <p className="petit muet">{p.district}{p.financeur ? `, ${t("pt.avec", { f: p.financeur })}` : ""}</p>
                    <div style={{ marginTop: "auto" }}><Progres valeur={p.avancement} /></div>
                    <p className="petit"><b className="chiffre">{nombre(p.beneficiaires)}</b> <span className="muet">{t("pt.benef_court")}</span></p>
                  </article>
                ))}
              </div>
            </section>

            <section className="portail-section">
              <h2>{t("pt.odd")}</h2>
              <p>{t("pt.odd_sous")}</p>
              <div className="grille g3">
                {d.impact_odd.map((o) => (
                  <div key={o.odd} className="kpi">
                    <div className="kpi-tete"><span>{o.libelle}</span></div>
                    <div className="kpi-valeur">{nombre(o.beneficiaires)}</div>
                    <span className="kpi-note">{t("pt.projets_biens", { p: o.projets, b: o.biens })}</span>
                  </div>
                ))}
              </div>
            </section>

            <footer className="portail-pied">
              <span>{d.organisation.nom}. UMURAGE</span>
              <span>{t("pt.mention")}</span>
            </footer>
          </>
        )}
      </div>
    </div>
  );
}
