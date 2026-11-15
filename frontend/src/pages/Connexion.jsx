import { useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { BrainCircuit, Eye, EyeOff, Languages, Loader2, MapPinned, MessageCircle, ShieldCheck } from "lucide-react";
import { useAuth } from "../auth";
import { useLangue } from "../i18n";
import { Bandeau } from "../components/ui";

// Comptes de démonstration : affichés seulement si le serveur est en mode démonstration (UMURAGE_DEMO).
// Les libellés sont traduits (clés co.demo.<identifiant>.role / .desc dans i18n.jsx).
const DEMO = [
  ["eveque", "DE"], ["tresorier", "TR"], ["surintendant.gitega", "SG"], ["agent.burunga", "AB"],
  ["admin", "AD"], ["membre.kayero", "ME"], ["admin.rwanda", "RW"],
];

const ATOUTS = [[MapPinned, "co.a1"], [MessageCircle, "co.a2"], [BrainCircuit, "co.a3"], [ShieldCheck, "co.a4"]];

export default function Connexion() {
  const { moi, connexion } = useAuth();
  const { t, langue, setLangue } = useLangue();
  const [u, setU] = useState("");
  const [p, setP] = useState("");
  const [voir, setVoir] = useState(false);
  const [erreur, setErreur] = useState("");
  const [encours, setEncours] = useState(false);
  const [otp, setOtp] = useState(false);
  const [code, setCode] = useState("");
  const [demo, setDemo] = useState(false);
  useEffect(() => {
    // Le serveur indique s'il est en mode démonstration ; sinon aucun compte de test n'est montré.
    fetch("/api/sante/").then((r) => r.json()).then((d) => setDemo(Boolean(d.demo))).catch(() => setDemo(false));
  }, []);
  if (moi) return <Navigate to={moi.est_membre ? "/membre" : "/"} replace />;

  async function envoyer(e) {
    e?.preventDefault();
    setEncours(true);
    setErreur("");
    try {
      await connexion(u, p, otp ? code : undefined);
    } catch (err) {
      if (err.otp) setOtp(true);
      setErreur(err.message);
    }
    setEncours(false);
  }

  return (
    <div className="connexion">
      <div className="connexion-visuel">
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <img src="/logo.svg" alt="" width="40" height="40" />
          <span style={{ fontSize: "0.9rem" }}>UMURAGE</span>
          <button type="button" onClick={() => setLangue(langue === "fr" ? "en" : "fr")} className="bouton petit"
            style={{ marginLeft: "auto", background: "rgba(255,255,255,.08)", color: "#fff", borderColor: "rgba(255,255,255,.2)", boxShadow: "none" }}>
            <Languages />{langue === "fr" ? "English" : "Français"}
          </button>
        </div>
        <div style={{ marginTop: "auto", marginBottom: "auto", paddingTop: 48 }}>
          <h1>UMURAGE</h1>
          <p className="accroche">{t("co.accroche")}</p>
          <ul className="connexion-atouts">
            {ATOUTS.map(([Ic, cle]) => (
              <li key={cle}>
                <span className="ic"><Ic /></span>
                <div><b>{t(cle)}</b><span>{t(cle + "t")}</span></div>
              </li>
            ))}
          </ul>
        </div>
        <svg className="collines" viewBox="0 0 800 200" preserveAspectRatio="none" aria-hidden="true">
          <path d="M0 120C110 70 210 46 320 58s170 62 280 50 150-60 200-72v164H0z" fill="#164a33" />
          <path d="M0 150c120-36 230-50 340-38s150 36 260 32 140-34 200-42v98H0z" fill="#1a5a3d" />
          <path d="M0 176c140-22 260-28 380-20s160 18 260 16 110-14 160-20v48H0z" fill="#1e6b47" />
        </svg>
      </div>

      <div className="connexion-formulaire">
        <form onSubmit={envoyer}>
          <div>
            <h2 style={{ fontSize: "1.6rem" }}>{t("co.titre")}</h2>
            <p className="muet" style={{ marginTop: 6 }}>{t("co.sous")}</p>
          </div>
          {erreur && <Bandeau type="erreur">{erreur}</Bandeau>}
          <label className="champ">
            {t("co.identifiant")}
            <input value={u} onChange={(e) => setU(e.target.value)} autoComplete="username" required autoFocus placeholder={t("co.identifiant_aide")} />
          </label>
          <label className="champ">
            {t("co.mdp")}
            <div style={{ position: "relative" }}>
              <input type={voir ? "text" : "password"} value={p} onChange={(e) => setP(e.target.value)} autoComplete="current-password" required style={{ paddingRight: 42 }} />
              <button type="button" className="icone-bouton" onClick={() => setVoir(!voir)} aria-label={voir ? "Masquer le mot de passe" : "Afficher le mot de passe"}
                style={{ position: "absolute", right: 2, top: 1 }}>
                {voir ? <EyeOff /> : <Eye />}
              </button>
            </div>
          </label>
          {otp && (
            <label className="champ">
              Code de vérification (application d'authentification)
              <input value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))} inputMode="numeric"
                autoComplete="one-time-code" placeholder="123456" autoFocus required />
            </label>
          )}
          <button className="bouton principal" disabled={encours}>
            {encours && <Loader2 className="tourne" />}
            {encours ? t("co.encours") : t("co.bouton")}
          </button>
          <p className="petit" style={{ textAlign: "center", marginTop: -6 }}><Link to="/mot-de-passe-oublie">{t("co.oublie")}</Link></p>

          {demo && <div className="comptes-demo">
            <p>{t("co.demo")} <strong>umurage2026</strong>.</p>
            {DEMO.map(([id, ini]) => (
              <button type="button" key={id} onClick={() => { setU(id); setP("umurage2026"); }}>
                <span className="avatar">{ini}</span>
                <div><b>{t(`co.demo.${id}.role`)}</b><span>{id} · {t(`co.demo.${id}.desc`)}</span></div>
              </button>
            ))}
          </div>}
          <p className="petit" style={{ textAlign: "center" }}>
            {t("co.membre")} <Link to="/demande-acces">{t("co.demander")}</Link>
          </p>
          <p className="petit" style={{ textAlign: "center" }}>
            {t("co.nouvelle")} <Link to="/inscription">{t("co.creer")}</Link>
          </p>
        </form>
      </div>
    </div>
  );
}
