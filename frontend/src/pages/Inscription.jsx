import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, ArrowRight, CheckCircle2, Loader2, Plus, X } from "lucide-react";
import { Bandeau, Champ } from "../components/ui";

// Une Église ou une organisation crée son propre espace UMURAGE, sans intervention extérieure.
const MONNAIES = [
  ["BIF", "Franc burundais", 2950], ["RWF", "Franc rwandais", 1450], ["KES", "Shilling kényan", 130], ["UGX", "Shilling ougandais", 3700],
  ["TZS", "Shilling tanzanien", 2600], ["CDF", "Franc congolais", 2800], ["XOF", "Franc CFA (Ouest)", 600], ["XAF", "Franc CFA (Centre)", 600],
  ["ETB", "Birr éthiopien", 120], ["MZN", "Metical", 64], ["AOA", "Kwanza", 900], ["NGN", "Naira", 1500], ["MAD", "Dirham marocain", 10], ["USD", "Dollar américain", 1],
];

export default function Inscription() {
  const [etape, setEtape] = useState(1);
  const [f, setF] = useState({
    nom: "", sigle: "", pays: "", devise: "BIF", taux_usd: 2950, langue: "fr",
    districts: [], admin_prenom: "", admin_nom: "", admin_email: "", admin_identifiant: "", admin_mot_de_passe: "",
  });
  const [district, setDistrict] = useState("");
  const [erreur, setErreur] = useState("");
  const [encours, setEncours] = useState(false);
  const [fait, setFait] = useState(null);
  const maj = (k) => (e) => setF({ ...f, [k]: e.target.value });

  function choisirMonnaie(e) {
    const m = MONNAIES.find((x) => x[0] === e.target.value);
    setF({ ...f, devise: e.target.value, taux_usd: m ? m[2] : f.taux_usd });
  }
  function ajouterDistrict(e) {
    e?.preventDefault();
    const noms = district.split(/[,;\n]/).map((x) => x.trim()).filter(Boolean);
    if (noms.length) setF({ ...f, districts: [...new Set([...f.districts, ...noms])] });
    setDistrict("");
  }
  async function creer() {
    setEncours(true);
    setErreur("");
    try {
      const r = await fetch("/api/inscription/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(f) });
      const d = await r.json();
      if (!r.ok) {
        setErreur(Object.entries(d).map(([k, v]) => (Array.isArray(v) ? v.join(" ") : typeof v === "string" ? v : k)).join(" "));
      } else setFait(d);
    } catch {
      setErreur("Le serveur ne répond pas.");
    }
    setEncours(false);
  }

  const etape1 = f.nom && f.sigle && f.pays && f.devise && f.taux_usd;
  const etape2 = f.districts.length > 0;
  const etape3 = f.admin_prenom && f.admin_nom && f.admin_email && f.admin_identifiant && f.admin_mot_de_passe.length >= 8;

  return (
    <div className="connexion">
      <div className="connexion-visuel">
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <img src="/logo.svg" alt="" width="40" height="40" />
          <span style={{ fontSize: "0.9rem" }}>UMURAGE</span>
        </div>
        <div style={{ marginTop: "auto", marginBottom: "auto", paddingTop: 48 }}>
          <h1 style={{ fontSize: "clamp(2.2rem, 4.5vw, 3.4rem)" }}>Créez l'espace de votre Église</h1>
          <p className="accroche">
            UMURAGE est libre et gratuit. En quelques minutes, votre organisation dispose de son propre inventaire, de ses tableaux de
            bord et de son portail de transparence. Ses données restent strictement séparées de celles des autres organisations.
          </p>
        </div>
        <svg className="collines" viewBox="0 0 800 200" preserveAspectRatio="none" aria-hidden="true">
          <path d="M0 120C110 70 210 46 320 58s170 62 280 50 150-60 200-72v164H0z" fill="#164a33" />
          <path d="M0 150c120-36 230-50 340-38s150 36 260 32 140-34 200-42v98H0z" fill="#1a5a3d" />
          <path d="M0 176c140-22 260-28 380-20s160 18 260 16 110-14 160-20v48H0z" fill="#1e6b47" />
        </svg>
      </div>

      <div className="connexion-formulaire">
        <div style={{ width: "min(460px, 100%)" }}>
          {fait ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <CheckCircle2 size={44} style={{ color: "var(--succes)" }} />
              <h2 style={{ fontSize: "1.6rem" }}>{fait.nom} est prête</h2>
              <p className="muet">Connectez-vous avec l'identifiant <b>{fait.identifiant}</b>. Commencez par ajouter les membres de votre équipe, puis importez votre inventaire depuis Excel.</p>
              <Link to="/connexion" className="bouton principal">Se connecter</Link>
              <p className="petit muet">Portail public : {window.location.origin}/public/{fait.slug}</p>
            </div>
          ) : (
            <>
              <Link to="/connexion" className="petit" style={{ display: "inline-flex", gap: 6, alignItems: "center", textDecoration: "none", marginBottom: 18 }}><ArrowLeft size={14} />Retour à la connexion</Link>
              <div className="etapes" aria-label={`Étape ${etape} sur 3`}>{[1, 2, 3].map((i) => <div key={i} className={i <= etape ? "faite" : ""} />)}</div>
              {erreur && <Bandeau type="erreur" style={{ marginBottom: 14 }}>{erreur}</Bandeau>}

              {etape === 1 && (
                <div className="formulaire">
                  <h2 className="large" style={{ fontSize: "1.4rem" }}>Votre organisation</h2>
                  <Champ libelle="Nom complet" large><input value={f.nom} onChange={maj("nom")} placeholder="Église Méthodiste Unie du Rwanda" autoFocus /></Champ>
                  <Champ libelle="Sigle"><input value={f.sigle} onChange={maj("sigle")} placeholder="EMU Rwanda" /></Champ>
                  <Champ libelle="Pays"><input value={f.pays} onChange={maj("pays")} placeholder="Rwanda" /></Champ>
                  <Champ libelle="Monnaie">
                    <select value={f.devise} onChange={choisirMonnaie}>{MONNAIES.map(([c, n]) => <option key={c} value={c}>{c}, {n}</option>)}</select>
                  </Champ>
                  <Champ libelle="Taux pour 1 USD" aide="Modifiable plus tard."><input type="number" step="any" value={f.taux_usd} onChange={maj("taux_usd")} /></Champ>
                  <Champ libelle="Langue" large>
                    <select value={f.langue} onChange={maj("langue")}><option value="fr">Français</option><option value="en">English</option></select>
                  </Champ>
                </div>
              )}

              {etape === 2 && (
                <div>
                  <h2 style={{ fontSize: "1.4rem", marginBottom: 6 }}>Vos districts</h2>
                  <p className="muet petit" style={{ marginBottom: 14 }}>Districts, diocèses ou régions : ils servent à répartir l'inventaire et les responsabilités. Vous pourrez en ajouter d'autres.</p>
                  <form onSubmit={ajouterDistrict} style={{ display: "flex", gap: 8 }}>
                    <input className="saisie-ui" value={district} onChange={(e) => setDistrict(e.target.value)} placeholder="Kigali, Huye, Musanze" aria-label="Nom du district" autoFocus />
                    <button className="bouton"><Plus />Ajouter</button>
                  </form>
                  <div className="liste-districts">
                    {f.districts.map((d) => (
                      <span key={d}>{d}<button type="button" aria-label={`Retirer ${d}`} onClick={() => setF({ ...f, districts: f.districts.filter((x) => x !== d) })}><X size={14} /></button></span>
                    ))}
                  </div>
                </div>
              )}

              {etape === 3 && (
                <div className="formulaire">
                  <h2 className="large" style={{ fontSize: "1.4rem" }}>Compte administrateur</h2>
                  <Champ libelle="Prénom"><input value={f.admin_prenom} onChange={maj("admin_prenom")} autoFocus /></Champ>
                  <Champ libelle="Nom"><input value={f.admin_nom} onChange={maj("admin_nom")} /></Champ>
                  <Champ libelle="E-mail" large><input type="email" value={f.admin_email} onChange={maj("admin_email")} /></Champ>
                  <Champ libelle="Identifiant"><input value={f.admin_identifiant} onChange={maj("admin_identifiant")} autoComplete="username" /></Champ>
                  <Champ libelle="Mot de passe" aide="8 caractères minimum."><input type="password" value={f.admin_mot_de_passe} onChange={maj("admin_mot_de_passe")} autoComplete="new-password" /></Champ>
                </div>
              )}

              <div className="actions" style={{ justifyContent: "space-between", marginTop: 22 }}>
                {etape > 1 ? <button className="bouton" onClick={() => setEtape(etape - 1)}><ArrowLeft />Précédent</button> : <span />}
                {etape < 3 ? (
                  <button className="bouton principal" disabled={etape === 1 ? !etape1 : !(etape2 || district.trim())} onClick={() => { if (etape === 2 && district) ajouterDistrict(); setEtape(etape + 1); }}>
                    Continuer<ArrowRight />
                  </button>
                ) : (
                  <button className="bouton principal" onClick={creer} disabled={!etape3 || encours}>{encours && <Loader2 className="tourne" />}Créer l'espace</button>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
