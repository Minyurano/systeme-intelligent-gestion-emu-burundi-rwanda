import { useState } from "react";
import { ShieldCheck, ShieldOff, Smartphone } from "lucide-react";
import { api } from "../api";
import { useAuth } from "../auth";
import { CarteMotDePasse } from "../components/MotDePasse";
import { Bandeau, Carte, EnTete, useToast } from "../components/ui";

// Double authentification : recommandée pour l'évêque, le trésorier et l'administrateur.
export default function Securite() {
  const { moi } = useAuth();
  const notifier = useToast();
  const [actif, setActif] = useState(!!moi.totp_actif);
  const [qr, setQr] = useState(null);
  const [code, setCode] = useState("");
  const [erreur, setErreur] = useState("");
  const sensible = ["ADMIN", "EVEQUE", "TRESORIER"].includes(moi.role);

  async function demarrer() {
    setErreur("");
    try { setQr(await api("2fa/activer/", { methode: "POST" })); } catch (e) { setErreur(e.message); }
  }
  async function confirmer() {
    setErreur("");
    try {
      await api("2fa/confirmer/", { methode: "POST", corps: { code } });
      setActif(true); setQr(null); setCode("");
      notifier("Double authentification activée");
    } catch (e) { setErreur(e.message); }
  }
  async function desactiver() {
    setErreur("");
    try {
      await api("2fa/desactiver/", { methode: "POST", corps: { code } });
      setActif(false); setCode("");
      notifier("Double authentification désactivée");
    } catch (e) { setErreur(e.message); }
  }

  return (
    <>
      <EnTete titre="Sécurité du compte" sousTitre="Votre mot de passe, et la double authentification qui demande en plus un code à 6 chiffres affiché par une application sur votre téléphone." />
      <div style={{ marginBottom: 16 }}><CarteMotDePasse /></div>
      <Carte titre="Double authentification" description={actif ? "Activée : un code vous sera demandé à chaque connexion." : "Désactivée."}>
        {erreur && <Bandeau type="erreur" style={{ marginBottom: 12 }}>{erreur}</Bandeau>}
        {!actif && sensible && !qr && <Bandeau type="attention" style={{ marginBottom: 12 }}>Votre rôle ({moi.role_libelle}) donne accès aux finances ou à l'ensemble du patrimoine : la double authentification est fortement recommandée.</Bandeau>}
        {actif ? (
          <div className="pile">
            <Bandeau type="succes"><ShieldCheck size={16} /> Votre compte est protégé.</Bandeau>
            <label className="champ">Pour désactiver, saisissez un code actuel
              <input value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))} inputMode="numeric" placeholder="123456" />
            </label>
            <div><button className="bouton danger" onClick={desactiver} disabled={code.length !== 6}><ShieldOff />Désactiver</button></div>
          </div>
        ) : qr ? (
          <div className="pile">
            <p>1. Installez <b>Google Authenticator</b> ou <b>Microsoft Authenticator</b> sur votre téléphone.<br />
              2. Scannez ce QR code (ou saisissez la clé <code>{qr.secret}</code>).<br />3. Tapez le code à 6 chiffres affiché.</p>
            <img src={qr.qr} alt="QR code de double authentification" width={200} height={200} style={{ background: "#fff", padding: 8, borderRadius: 8 }} />
            <label className="champ">Code à 6 chiffres
              <input value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))} inputMode="numeric" placeholder="123456" autoFocus />
            </label>
            <div><button className="bouton principal" onClick={confirmer} disabled={code.length !== 6}><ShieldCheck />Activer</button></div>
          </div>
        ) : <button className="bouton principal" onClick={demarrer}><Smartphone />Activer la double authentification</button>}
      </Carte>
    </>
  );
}
