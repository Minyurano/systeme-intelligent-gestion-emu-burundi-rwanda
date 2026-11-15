import { useState } from "react";
import { Eye, EyeOff, KeyRound, Loader2, LogOut } from "lucide-react";
import { api, enregistrerJetons } from "../api";
import { useAuth } from "../auth";
import { Bandeau, Carte } from "./ui";

// Force du mot de passe, expliquée simplement
function force(m) {
  let n = 0;
  if (m.length >= 8) n++;
  if (m.length >= 12) n++;
  if (/[a-z]/.test(m) && /[A-Z]/.test(m)) n++;
  if (/\d/.test(m)) n++;
  if (/[^A-Za-z0-9]/.test(m)) n++;
  return Math.min(n, 4);
}
const NIVEAUX = [["Trop court", "critique"], ["Faible", "critique"], ["Moyen", "attention"], ["Bon", "bon"], ["Excellent", "bon"]];

export function FormulaireMotDePasse({ onFait, ancienParDefaut = "" }) {
  const [f, setF] = useState({ ancien: ancienParDefaut, nouveau: "", confirmation: "" });
  const [voir, setVoir] = useState(false);
  const [erreur, setErreur] = useState("");
  const [encours, setEncours] = useState(false);
  const niveau = force(f.nouveau);
  const differents = f.confirmation && f.nouveau !== f.confirmation;

  async function envoyer(e) {
    e.preventDefault();
    if (f.nouveau !== f.confirmation) return setErreur("Les deux nouveaux mots de passe ne sont pas identiques.");
    setEncours(true);
    setErreur("");
    try {
      const r = await api("moi/mot-de-passe/", { methode: "POST", corps: { ancien: f.ancien, nouveau: f.nouveau } });
      if (r?.access) enregistrerJetons(r); // les autres sessions sont fermées, celle-ci repart sur un jeton neuf
      setF({ ancien: "", nouveau: "", confirmation: "" });
      onFait?.();
    } catch (err) {
      const d = err.details || {};
      setErreur([].concat(d.ancien || [], d.nouveau || []).join(" ") || err.message);
    }
    setEncours(false);
  }

  const type = voir ? "text" : "password";
  return (
    <form className="pile" onSubmit={envoyer} style={{ gap: 14 }}>
      {erreur && <Bandeau type="erreur">{erreur}</Bandeau>}
      <label className="champ">Mot de passe actuel
        <input type={type} value={f.ancien} onChange={(e) => setF({ ...f, ancien: e.target.value })} autoComplete="current-password" required />
      </label>
      <label className="champ">Nouveau mot de passe
        <div style={{ position: "relative" }}>
          <input type={type} value={f.nouveau} onChange={(e) => setF({ ...f, nouveau: e.target.value })} autoComplete="new-password" required minLength={8} style={{ paddingRight: 42 }} />
          <button type="button" className="icone-bouton" onClick={() => setVoir(!voir)} aria-label={voir ? "Masquer" : "Afficher"} style={{ position: "absolute", right: 2, top: 1 }}>
            {voir ? <EyeOff /> : <Eye />}
          </button>
        </div>
      </label>
      {f.nouveau && (
        <div className="barre-completude" aria-live="polite">
          <div className="piste"><span style={{ width: `${(niveau + 1) * 20}%` }} /></div>
          <small><span className={`badge ${NIVEAUX[niveau][1]}`}>{NIVEAUX[niveau][0]}</span> 8 caractères au moins ; une phrase facile à retenir est idéale.</small>
        </div>
      )}
      <label className="champ">Confirmez le nouveau mot de passe
        <input type={type} value={f.confirmation} onChange={(e) => setF({ ...f, confirmation: e.target.value })} autoComplete="new-password" required />
        {differents && <small style={{ color: "var(--critique)" }}>Les deux saisies sont différentes.</small>}
      </label>
      <div><button className="bouton principal" disabled={encours || differents || f.nouveau.length < 8}>
        {encours ? <Loader2 className="tourne" /> : <KeyRound />}Changer le mot de passe
      </button></div>
    </form>
  );
}

export function CarteMotDePasse() {
  const [fait, setFait] = useState(false);
  return (
    <Carte titre="Mot de passe" description="Changez votre mot de passe régulièrement, et dès que vous pensez qu'il a été vu.">
      {fait && <Bandeau type="succes" style={{ marginBottom: 12 }}>Mot de passe changé.</Bandeau>}
      <FormulaireMotDePasse onFait={() => setFait(true)} />
    </Carte>
  );
}

// Écran affiché tant qu'un mot de passe provisoire (donné par un administrateur) n'a pas été remplacé.
export function ChangementObligatoire() {
  const { moi, deconnexion, rafraichir } = useAuth();
  return (
    <div className="ecran-centre">
      <div className="carte-ui" style={{ width: "min(460px, 100%)", padding: 28 }}>
        <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 14 }}>
          <img src="/logo.svg" alt="" width="36" height="36" />
          <div>
            <h1 style={{ fontSize: "1.3rem" }}>Bienvenue, {moi.nom.split(" ")[0]}</h1>
            <p className="petit muet">{moi.organisation?.nom}</p>
          </div>
        </div>
        <Bandeau type="info" style={{ marginBottom: 16 }}>
          Votre accès a été ouvert avec un mot de passe provisoire. Choisissez maintenant votre propre mot de passe : personne d'autre ne le connaîtra, pas même l'administrateur.
        </Bandeau>
        <FormulaireMotDePasse onFait={rafraichir} />
        <button className="bouton fantome petit" style={{ marginTop: 14 }} onClick={deconnexion}><LogOut />Se déconnecter</button>
      </div>
    </div>
  );
}
