import { useEffect, useState } from "react";
import { Building2, CheckCircle2, DatabaseBackup, Download, Globe, Loader2, MapPinned, Network, Plug, Plus, Save, TriangleAlert, UserPlus, Users } from "lucide-react";
import { api, telecharger } from "../api";
import { useAuth } from "../auth";
import { Bandeau, Carte, Champ, EnTete, Etat, Modale, Onglets, useApi, useToast } from "../components/ui";
import { dateHeure } from "../format";

const ROLES = {
  ADMIN: "Administrateur", EVEQUE: "Évêque / Direction", TRESORIER: "Trésorier",
  SURINTENDANT: "Surintendant de district", AGENT: "Agent de collecte",
};

export default function Parametres() {
  const [onglet, setOnglet] = useState("organisation");
  return (
    <>
      <EnTete titre="Paramètres" sousTitre="Organisation, comptes des responsables, districts et connexions avec d'autres outils. Les accès des fidèles se gèrent dans « Accès des membres »." />
      <Onglets actif={onglet} onChange={setOnglet} onglets={[
        { id: "organisation", libelle: "Organisation", icone: Building2 },
        { id: "membres", libelle: "Comptes des responsables", icone: Users },
        { id: "districts", libelle: "Districts", icone: MapPinned },
        { id: "integrations", libelle: "Intégrations", icone: Plug },
      ]} />
      {onglet === "organisation" && <Organisation />}
      {onglet === "membres" && <Membres />}
      {onglet === "districts" && <Districts />}
      {onglet === "integrations" && <Integrations />}
    </>
  );
}

function Organisation() {
  const notifier = useToast();
  const { donnees, erreur } = useApi("organisation/");
  const [f, setF] = useState(null);
  const [encours, setEncours] = useState(false);
  useEffect(() => { if (donnees) setF(donnees); }, [donnees]);
  const maj = (k) => (e) => setF({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });

  async function enregistrer() {
    setEncours(true);
    try {
      await api("organisation/", { methode: "PATCH", corps: f });
      notifier("Paramètres enregistrés. Rechargez la page pour appliquer la monnaie et la langue.");
    } catch (e) {
      notifier(e.message, "erreur");
    }
    setEncours(false);
  }

  return (
    <Etat chargement={!f} erreur={erreur}>
      {f && (
        <Carte titre="Identité de l'organisation" description={`Adresse du portail public : ${window.location.origin}/public/${f.slug}`}
          pied={<><span>Statut : {f.statut === "ESSAI" ? "période d'essai" : "active"}</span>
            <button className="bouton principal" onClick={enregistrer} disabled={encours}>{encours ? <Loader2 className="tourne" /> : <Save />}Enregistrer</button></>}>
          <div className="formulaire">
            <Champ libelle="Nom complet" large><input value={f.nom} onChange={maj("nom")} /></Champ>
            <Champ libelle="Sigle"><input value={f.sigle} onChange={maj("sigle")} /></Champ>
            <Champ libelle="Pays"><input value={f.pays} onChange={maj("pays")} /></Champ>
            <Champ libelle="Monnaie locale" aide="Code à trois lettres : BIF, RWF, KES, UGX, TZS, CDF…"><input value={f.devise} onChange={maj("devise")} maxLength={3} /></Champ>
            <Champ libelle="Taux de change" aide="Unités de monnaie locale pour 1 USD."><input type="number" step="any" value={f.taux_usd} onChange={maj("taux_usd")} /></Champ>
            <Champ libelle="Langue par défaut">
              <select value={f.langue} onChange={maj("langue")}><option value="fr">Français</option><option value="en">English</option></select>
            </Champ>
            <Champ libelle="Numéro WhatsApp de l'Église"><input value={f.whatsapp_numero} onChange={maj("whatsapp_numero")} placeholder="+257…" /></Champ>
            <label className="large" style={{ display: "flex", gap: 10, alignItems: "center" }}>
              <input type="checkbox" checked={f.portail_public} onChange={maj("portail_public")} />
              Publier le portail de transparence (chiffres d'impact et projets, sans données financières)
            </label>
            <label className="large" style={{ display: "flex", gap: 10, alignItems: "center" }}>
              <input type="checkbox" checked={!!f.demandes_acces_ouvertes} onChange={maj("demandes_acces_ouvertes")} />
              Autoriser les membres inscrits au registre à demander eux-mêmes un accès (décision par un administrateur)
            </label>
          </div>
        </Carte>
      )}
    </Etat>
  );
}

function Membres() {
  const notifier = useToast();
  const { moi } = useAuth();
  const { donnees, erreur, chargement, recharger } = useApi("membres/");
  const [edition, setEdition] = useState(null);
  return (
    <Carte brut titre="Comptes des responsables" description="Chaque responsable a un rôle ; les surintendants et agents sont limités à leur district. Le téléphone permet la saisie par WhatsApp. Les simples fidèles reçoivent leur accès depuis la page « Accès des membres »."
      actions={<button className="bouton principal petit" onClick={() => setEdition({})}><UserPlus />Ajouter un responsable</button>}>
      <div style={{ height: 12 }} />
      <Etat chargement={chargement && !donnees} erreur={erreur}>
        <div className="defilement">
          <table className="tableau">
            <thead><tr><th>Responsable</th><th>Rôle</th><th>District</th><th className="masquer-mobile">Téléphone (WhatsApp)</th><th className="masquer-mobile">Dernière connexion</th><th /></tr></thead>
            <tbody>
              {donnees?.map((m) => (
                <tr key={m.id}>
                  <td><div className="principal-cell">{[m.prenom, m.nom].filter(Boolean).join(" ") || m.username}</div><div className="secondaire">{m.username}{m.email ? `, ${m.email}` : ""}</div></td>
                  <td>{m.role_libelle}{!m.actif && <span className="badge critique" style={{ marginLeft: 6 }}>Désactivé</span>}</td>
                  <td>{m.district_nom || <span className="muet">Tous</span>}</td>
                  <td className="masquer-mobile">{m.telephone || <span className="muet">—</span>}</td>
                  <td className="masquer-mobile petit muet">{m.derniere_connexion ? dateHeure(m.derniere_connexion) : "Jamais"}</td>
                  <td className="num"><button className="bouton petit" onClick={() => setEdition(m)}>Modifier</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Etat>
      {edition && <MembreFormulaire membre={edition.id ? edition : null} soiMeme={edition.username === moi.username}
        onFermer={() => setEdition(null)} onFait={(msg) => { setEdition(null); notifier(msg); recharger(); }} />}
    </Carte>
  );
}

function MembreFormulaire({ membre, soiMeme, onFermer, onFait }) {
  const [f, setF] = useState(membre ? { ...membre, mot_de_passe: "" } : { username: "", prenom: "", nom: "", email: "", role: "AGENT", district: "", telephone: "", mot_de_passe: "", actif: true });
  const { donnees: districts } = useApi("districts/");
  const [erreur, setErreur] = useState("");
  const [encours, setEncours] = useState(false);
  const maj = (k) => (e) => setF({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  async function enregistrer() {
    setEncours(true);
    setErreur("");
    const corps = { ...f, district: f.district || null };
    if (!corps.mot_de_passe) delete corps.mot_de_passe;
    try {
      await api(membre ? `membres/${membre.id}/` : "membres/", { methode: membre ? "PATCH" : "POST", corps });
      onFait(membre ? "Compte mis à jour." : `Compte ${f.username} créé.`);
    } catch (e) {
      setErreur(e.message);
    }
    setEncours(false);
  }
  return (
    <Modale titre={membre ? `Modifier ${membre.username}` : "Ajouter un responsable"} onFermer={onFermer} largeur={640}
      pied={<><button className="bouton" onClick={onFermer}>Annuler</button><button className="bouton principal" onClick={enregistrer} disabled={encours}>{encours && <Loader2 className="tourne" />}Enregistrer</button></>}>
      {erreur && <Bandeau type="erreur" style={{ marginBottom: 14 }}>{erreur}</Bandeau>}
      <div className="formulaire">
        <Champ libelle="Prénom"><input value={f.prenom} onChange={maj("prenom")} /></Champ>
        <Champ libelle="Nom"><input value={f.nom} onChange={maj("nom")} /></Champ>
        <Champ libelle="Identifiant de connexion"><input value={f.username} onChange={maj("username")} /></Champ>
        <Champ libelle="E-mail"><input type="email" value={f.email} onChange={maj("email")} /></Champ>
        <Champ libelle="Rôle">
          <select value={f.role} onChange={maj("role")} disabled={soiMeme}>{Object.entries(ROLES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
        </Champ>
        <Champ libelle="District" aide="Obligatoire pour un surintendant ou un agent.">
          <select value={f.district || ""} onChange={maj("district")}><option value="">Tous les districts</option>{districts?.map((d) => <option key={d.id} value={d.id}>{d.nom}</option>)}</select>
        </Champ>
        <Champ libelle="Téléphone WhatsApp" aide="Format international, par exemple +257 79 00 00 00."><input value={f.telephone} onChange={maj("telephone")} /></Champ>
        <Champ libelle={membre ? "Nouveau mot de passe" : "Mot de passe"} aide={membre ? "Laissez vide pour le conserver." : "8 caractères minimum."}>
          <input type="password" value={f.mot_de_passe} onChange={maj("mot_de_passe")} autoComplete="new-password" />
        </Champ>
        {membre && !soiMeme && (
          <label className="large" style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <input type="checkbox" checked={f.actif} onChange={maj("actif")} />Compte actif
          </label>
        )}
      </div>
    </Modale>
  );
}

function Districts() {
  const notifier = useToast();
  const { donnees, recharger } = useApi("districts/");
  const [f, setF] = useState({ code: "", nom: "", siege: "" });
  async function ajouter(e) {
    e.preventDefault();
    try {
      await api("districts/", { methode: "POST", corps: f });
      notifier(`District ${f.nom} ajouté.`);
      setF({ code: "", nom: "", siege: "" });
      recharger();
    } catch (err) {
      notifier(err.message, "erreur");
    }
  }
  return (
    <div className="grille g-3-2">
      <Carte titre="Districts" plein>
        <table className="tableau">
          <thead><tr><th>Code</th><th>District</th><th>Siège</th></tr></thead>
          <tbody>{donnees?.map((d) => <tr key={d.id}><td className="code">{d.code}</td><td className="principal-cell">{d.nom}</td><td>{d.siege}</td></tr>)}</tbody>
        </table>
      </Carte>
      <Carte titre="Ajouter un district">
        <form className="formulaire" onSubmit={ajouter} style={{ gridTemplateColumns: "1fr" }}>
          <Champ libelle="Code" aide="Trois lettres, utilisées dans les codes des biens."><input value={f.code} onChange={(e) => setF({ ...f, code: e.target.value.toUpperCase().slice(0, 5) })} required /></Champ>
          <Champ libelle="Nom"><input value={f.nom} onChange={(e) => setF({ ...f, nom: e.target.value })} required /></Champ>
          <Champ libelle="Siège"><input value={f.siege} onChange={(e) => setF({ ...f, siege: e.target.value })} required /></Champ>
          <button className="bouton principal"><Plus />Ajouter le district</button>
        </form>
      </Carte>
    </div>
  );
}

function Integrations() {
  const { moi } = useAuth();
  const org = moi.organisation;
  return (
    <div className="grille g2">
      <Carte titre="WhatsApp" description="Saisie et signalements depuis le terrain">
        <p className="petit" style={{ marginBottom: 8 }}>Adresse du webhook à déclarer chez Meta :</p>
        <code className="code" style={{ display: "block", padding: 10, background: "var(--surface-2)", borderRadius: 8, whiteSpace: "normal", wordBreak: "break-all" }}>
          {window.location.origin}/api/whatsapp/webhook/
        </code>
        <p className="petit muet" style={{ marginTop: 8 }}>Variables du serveur : WHATSAPP_TOKEN, WHATSAPP_PHONE_ID, WHATSAPP_VERIFY_TOKEN.</p>
      </Carte>
      <Carte titre="Standard IATI" description="Transparence de l'aide internationale">
        <p className="petit" style={{ marginBottom: 12 }}>Les projets sont exportés au format IATI 2.03, que les bailleurs (UMCOR, GBGM, agences de coopération) peuvent intégrer directement.</p>
        <button className="bouton" onClick={() => telecharger("export/iati/", `iati_${org.slug}.xml`)}><Download />Télécharger le fichier IATI</button>
      </Carte>
      <Carte titre="Portail public" description="Pour les donateurs et partenaires">
        <p className="petit" style={{ marginBottom: 12 }}>Chiffres d'impact et projets, sans aucune donnée financière détaillée ni titre de propriété.</p>
        <a className="bouton" href={`/public/${org.slug}`} target="_blank" rel="noreferrer"><Globe />Ouvrir le portail</a>
      </Carte>
      <DiagnosticAdresse />
      <Carte titre="Sauvegardes" description="Base de données et fichiers">
        <p className="petit" style={{ marginBottom: 8 }}>Sur le serveur, planifiez chaque nuit :</p>
        <code className="code" style={{ display: "block", padding: 10, background: "var(--surface-2)", borderRadius: 8 }}>python manage.py sauvegarder --garder 30</code>
        <p className="petit muet" style={{ marginTop: 8, display: "flex", gap: 6, alignItems: "center" }}><DatabaseBackup size={14} />Avec Docker, le service « sauvegarde » s'en charge automatiquement.</p>
      </Carte>
    </div>
  );
}

// Adresse privée (réseau interne, proxy, Docker) : ce ne peut pas être l'adresse publique d'un visiteur
const privee = (ip = "") => /^(10\.|127\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|::1$|fc|fd|fe80)/i.test(ip);

function DiagnosticAdresse() {
  const [r, setR] = useState(null);
  const [publique, setPublique] = useState(null);
  const [encours, setEncours] = useState(false);
  const [erreur, setErreur] = useState("");

  async function verifier() {
    setEncours(true); setErreur(""); setPublique(null);
    try {
      setR(await api("diagnostic/adresse-ip/"));
      // Adresse publique de cet appareil, vue de l'extérieur (service ipify, seulement sur ce clic)
      try {
        const x = await fetch("https://api.ipify.org?format=json").then((y) => y.json());
        setPublique(x.ip);
      } catch { setPublique(""); }
    } catch (e) {
      setErreur(e.message);
    }
    setEncours(false);
  }

  let verdict = null;
  if (r) {
    if (publique && r.adresse_retenue === publique) verdict = ["succes", "Réglage correct : le serveur reconnaît l'adresse publique de votre appareil. Les limites de tentatives visent bien chaque visiteur."];
    else if (privee(r.adresse_retenue) && publique && !privee(publique)) verdict = ["erreur", `Le serveur voit une adresse interne (${r.adresse_retenue}) au lieu de la vôtre (${publique}) : tous les visiteurs partagent la même adresse. Mettez UMURAGE_NUM_PROXIES=1 (docker-compose.prod.yml le fait déjà) et vérifiez que le proxy ajoute X-Forwarded-For.`];
    else if (publique && r.adresse_retenue !== publique) verdict = ["attention", `Adresse retenue ${r.adresse_retenue}, adresse publique ${publique}. C'est normal si vous êtes sur le même réseau que le serveur ; sinon, revoyez UMURAGE_NUM_PROXIES.`];
    else verdict = [r.conseil?.startsWith("Réglage cohérent") ? "info" : "attention", r.conseil];
  }

  return (
    <Carte titre="Adresse IP des visiteurs" description="Les limites de tentatives (connexion, mot de passe oublié…) comptent par adresse : elle doit être la vraie.">
      <div className="pile" style={{ gap: 12 }}>
        {erreur && <Bandeau type="erreur">{erreur}</Bandeau>}
        {r && (
          <dl className="proprietes" style={{ border: "1px solid var(--trait)", borderRadius: 8, margin: 0 }}>
            {[["Adresse retenue par le serveur", r.adresse_retenue], ["Votre adresse publique", publique === null ? "…" : publique || "non disponible"],
              ["Proxys de confiance", r.num_proxies], ["X-Forwarded-For reçu", r.x_forwarded_for || "aucun"]].map(([k, v]) => (
              <div key={k}><dt>{k}</dt><dd className="code">{String(v)}</dd></div>))}
          </dl>
        )}
        {verdict && <Bandeau type={verdict[0]}>{verdict[1]}</Bandeau>}
        <div><button className="bouton" onClick={verifier} disabled={encours}>{encours ? <Loader2 className="tourne" /> : r ? <CheckCircle2 /> : <Network />}{r ? "Vérifier à nouveau" : "Vérifier"}</button></div>
        <p className="petit muet" style={{ display: "flex", gap: 6, alignItems: "flex-start" }}><TriangleAlert size={13} style={{ flex: "none", marginTop: 3 }} />La comparaison interroge le service public ipify pour connaître l'adresse de cet appareil, uniquement quand vous cliquez.</p>
      </div>
    </Carte>
  );
}
