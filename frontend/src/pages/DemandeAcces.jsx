import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, CheckCircle2, Loader2, Send } from "lucide-react";
import { Bandeau, Champ } from "../components/ui";

// Page publique : un fidèle inscrit au registre demande l'accès à son espace membre.
export default function DemandeAcces() {
  const [orgs, setOrgs] = useState(null);
  const [f, setF] = useState({ organisation: "", numero: "", nom: "", telephone: "", message: "" });
  const [erreur, setErreur] = useState("");
  const [fait, setFait] = useState(null);
  const [encours, setEncours] = useState(false);

  useEffect(() => {
    fetch("/api/acces/organisations/").then((r) => r.json()).then((l) => {
      setOrgs(l);
      if (l.length === 1) setF((x) => ({ ...x, organisation: l[0].slug }));
    }).catch(() => setOrgs([]));
  }, []);
  const maj = (k) => (e) => setF({ ...f, [k]: e.target.value });

  async function envoyer(e) {
    e.preventDefault();
    setEncours(true);
    setErreur("");
    try {
      const r = await fetch("/api/acces/demande/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(f) });
      const corps = await r.json().catch(() => ({}));
      if (r.status === 429) throw new Error("Trop de demandes depuis cet appareil. Réessayez dans une heure.");
      if (!r.ok) throw new Error(corps.detail || Object.values(corps).flat().join(" ") || "Demande impossible pour le moment.");
      setFait(corps.message);
    } catch (err) {
      setErreur(err.message === "Failed to fetch" ? "Pas de connexion au serveur." : err.message);
    }
    setEncours(false);
  }

  return (
    <div className="ecran-centre">
      <div className="carte-ui" style={{ width: "min(520px, 100%)", padding: 28 }}>
        <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 18 }}>
          <img src="/logo.svg" alt="" width="38" height="38" />
          <div>
            <h1 style={{ fontSize: "1.35rem" }}>Demander l'accès à l'espace membre</h1>
            <p className="petit muet">Pour les membres inscrits au registre de leur église locale.</p>
          </div>
        </div>
        {fait ? (
          <div className="pile" style={{ alignItems: "center", textAlign: "center", gap: 12 }}>
            <CheckCircle2 size={44} color="var(--succes)" />
            <h2 style={{ fontSize: "1.15rem" }}>Demande envoyée</h2>
            <p className="muet">{fait}</p>
            <Link className="bouton" to="/connexion"><ArrowLeft />Retour à la connexion</Link>
          </div>
        ) : (
          <form className="pile" style={{ gap: 14 }} onSubmit={envoyer}>
            {erreur && <Bandeau type="erreur">{erreur}</Bandeau>}
            {orgs && orgs.length === 0 && <Bandeau type="attention">Aucune Église n'accepte de demandes en ligne pour le moment. Adressez-vous à votre pasteur.</Bandeau>}
            {orgs?.length > 1 && (
              <Champ libelle="Votre Église">
                <select value={f.organisation} onChange={maj("organisation")} required>
                  <option value="">Choisir…</option>
                  {orgs.map((o) => <option key={o.slug} value={o.slug}>{o.nom} ({o.pays})</option>)}
                </select>
              </Champ>
            )}
            <Champ libelle="Prénom et nom"><input value={f.nom} onChange={maj("nom")} required minLength={4} autoComplete="name" /></Champ>
            <Champ libelle="Numéro de membre" aide="Il figure sur votre carte de membre, par exemple GIT-2026-00012. Facultatif, mais la vérification est alors immédiate.">
              <input value={f.numero} onChange={(e) => setF({ ...f, numero: e.target.value.toUpperCase() })} placeholder="GIT-2026-00012" />
            </Champ>
            <Champ libelle="Téléphone (WhatsApp)" aide="Le même que sur votre fiche : vos identifiants y seront envoyés.">
              <input value={f.telephone} onChange={maj("telephone")} required inputMode="tel" autoComplete="tel" placeholder="+257 79 00 00 00" />
            </Champ>
            <Champ libelle="Message pour l'administrateur (facultatif)">
              <textarea rows={3} value={f.message} onChange={maj("message")} maxLength={500} placeholder="ex. Je suis à la chorale de Kayero." />
            </Champ>
            <button className="bouton principal" disabled={encours || !f.organisation}>{encours ? <Loader2 className="tourne" /> : <Send />}Envoyer la demande</button>
            <p className="petit" style={{ textAlign: "center" }}><Link to="/connexion">Retour à la connexion</Link></p>
          </form>
        )}
      </div>
    </div>
  );
}
