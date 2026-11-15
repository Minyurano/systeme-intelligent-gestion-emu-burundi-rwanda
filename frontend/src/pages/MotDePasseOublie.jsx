import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowLeft, CheckCircle2, KeyRound, Loader2, Send } from "lucide-react";
import { Bandeau, Champ } from "../components/ui";

async function poster(chemin, corps) {
  let r;
  try {
    r = await fetch(`/api/auth/${chemin}/`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corps) });
  } catch {
    throw new Error("Pas de connexion au serveur.");
  }
  const d = await r.json().catch(() => ({}));
  if (r.status === 429) throw new Error("Trop de tentatives depuis cet appareil. Réessayez dans une heure.");
  if (!r.ok) throw new Error([].concat(d.code || [], d.nouveau || [], d.detail || []).join(" ") || "Opération impossible.");
  return d;
}

// Mot de passe oublié : code à 6 chiffres reçu sur WhatsApp ou par e-mail, puis nouveau mot de passe.
export default function MotDePasseOublie() {
  const nav = useNavigate();
  const [etape, setEtape] = useState(1);
  const [identifiant, setIdentifiant] = useState("");
  const [code, setCode] = useState("");
  const [nouveau, setNouveau] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [message, setMessage] = useState("");
  const [erreur, setErreur] = useState("");
  const [encours, setEncours] = useState(false);

  async function demander(e) {
    e.preventDefault();
    setEncours(true); setErreur("");
    try {
      setMessage((await poster("mot-de-passe-oublie", { identifiant })).message);
      setEtape(2);
    } catch (err) { setErreur(err.message); }
    setEncours(false);
  }
  async function valider(e) {
    e.preventDefault();
    if (nouveau !== confirmation) return setErreur("Les deux mots de passe ne sont pas identiques.");
    setEncours(true); setErreur("");
    try {
      await poster("reinitialiser", { identifiant, code, nouveau });
      setEtape(3);
    } catch (err) { setErreur(err.message); }
    setEncours(false);
  }

  return (
    <div className="ecran-centre">
      <div className="carte-ui" style={{ width: "min(460px, 100%)", padding: 28 }}>
        <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 18 }}>
          <img src="/logo.svg" alt="" width="36" height="36" />
          <div>
            <h1 style={{ fontSize: "1.3rem" }}>Mot de passe oublié</h1>
            <p className="petit muet">Étape {Math.min(etape, 2)} sur 2</p>
          </div>
        </div>
        {erreur && <Bandeau type="erreur" style={{ marginBottom: 14 }}>{erreur}</Bandeau>}
        {etape === 1 && (
          <form className="pile" style={{ gap: 14 }} onSubmit={demander}>
            <p className="petit">Saisissez votre identifiant. Pour un membre de l'Église, c'est votre numéro de membre (par exemple GIT-2026-00012).</p>
            <Champ libelle="Identifiant"><input value={identifiant} onChange={(e) => setIdentifiant(e.target.value)} required autoFocus autoComplete="username" /></Champ>
            <button className="bouton principal" disabled={encours}>{encours ? <Loader2 className="tourne" /> : <Send />}Recevoir un code</button>
          </form>
        )}
        {etape === 2 && (
          <form className="pile" style={{ gap: 14 }} onSubmit={valider}>
            <Bandeau type="info">{message}</Bandeau>
            <Champ libelle="Code reçu (6 chiffres)">
              <input value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))} inputMode="numeric" autoComplete="one-time-code" required autoFocus placeholder="123456" />
            </Champ>
            <Champ libelle="Nouveau mot de passe" aide="8 caractères au moins ; une phrase facile à retenir est idéale.">
              <input type="password" value={nouveau} onChange={(e) => setNouveau(e.target.value)} required minLength={8} autoComplete="new-password" />
            </Champ>
            <Champ libelle="Confirmez le nouveau mot de passe">
              <input type="password" value={confirmation} onChange={(e) => setConfirmation(e.target.value)} required autoComplete="new-password" />
            </Champ>
            <button className="bouton principal" disabled={encours || code.length !== 6}>{encours ? <Loader2 className="tourne" /> : <KeyRound />}Changer le mot de passe</button>
            <button type="button" className="bouton fantome petit" onClick={() => { setEtape(1); setCode(""); setErreur(""); }}>Je n'ai rien reçu : recommencer</button>
          </form>
        )}
        {etape === 3 && (
          <div className="pile" style={{ alignItems: "center", textAlign: "center", gap: 12 }}>
            <CheckCircle2 size={44} color="var(--succes)" />
            <p>Votre mot de passe est changé. Toutes vos anciennes sessions ont été fermées.</p>
            <button className="bouton principal" onClick={() => nav("/connexion")}>Se connecter</button>
          </div>
        )}
        {etape !== 3 && <p className="petit" style={{ textAlign: "center", marginTop: 16 }}><Link to="/connexion" style={{ display: "inline-flex", gap: 6, alignItems: "center" }}><ArrowLeft size={13} />Retour à la connexion</Link></p>}
      </div>
    </div>
  );
}
