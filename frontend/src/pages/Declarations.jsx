import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Check, CheckCheck, ClipboardCheck, Image, Loader2, Mic, PencilLine, RefreshCw, Send, X } from "lucide-react";
import { api } from "../api";
import { useAuth } from "../auth";
import { Bandeau, Carte, Champ, EnTete, Etat, Modale, Segments, useApi, useToast, Vide } from "../components/ui";
import { CATEGORIES, ETATS, bif, dateHeure, devise } from "../format";

const ETAT_LIB = { BON: "Bon état", MOYEN: "État moyen", MAUVAIS: "Mauvais état", CONSTRUCTION: "En construction" };

export default function Declarations() {
  const { peut, moi } = useAuth();
  const notifier = useToast();
  const [statut, setStatut] = useState("EN_ATTENTE");
  const liste = useApi(`declarations/?statut=${statut}`);
  const enAttente = useApi("declarations/?statut=EN_ATTENTE");
  const [validation, setValidation] = useState(null);
  const [rejet, setRejet] = useState(null);

  const recharger = () => { liste.recharger(); enAttente.recharger(); };

  return (
    <>
      <EnTete titre="Déclarations du terrain"
        sousTitre="Les pasteurs et agents signalent un bien ou un problème par WhatsApp, en texte, photo ou message vocal. UMURAGE comprend le message ; vous vérifiez et validez en un clic.">
        <button className="bouton" onClick={recharger}><RefreshCw />Actualiser</button>
      </EnTete>

      <div className="grille g-3-2">
        <Carte brut titre="Boîte de réception"
          actions={<Segments label="Statut" valeur={statut} onChange={setStatut} options={[
            { id: "EN_ATTENTE", libelle: "À valider", nb: enAttente.donnees?.count },
            { id: "VALIDEE", libelle: "Validées" },
            { id: "REJETEE", libelle: "Rejetées" },
          ]} />}>
          <div style={{ height: 12 }} />
          <Etat chargement={liste.chargement && !liste.donnees} erreur={liste.erreur} lignes={6}>
            {liste.donnees?.results.length === 0 ? (
              <Vide icone={ClipboardCheck} titre={statut === "EN_ATTENTE" ? "Rien à valider" : "Aucune déclaration"}
                texte="Les messages envoyés au numéro WhatsApp de l'Église apparaîtront ici. Essayez le simulateur à côté." />
            ) : (
              <div style={{ borderTop: "1px solid var(--trait)" }}>
                {liste.donnees?.results.map((d) => (
                  <LigneDeclaration key={d.id} d={d} peutValider={peut("declarations")}
                    onValider={() => setValidation(d)} onRejeter={() => setRejet(d)} />
                ))}
              </div>
            )}
          </Etat>
        </Carte>

        <div className="pile">
          <Simulateur moi={moi} onMessage={recharger} />
          <Carte titre="Brancher le vrai numéro WhatsApp">
            <ol className="petit" style={{ margin: 0, paddingLeft: 18, display: "grid", gap: 6, color: "var(--encre-2)" }}>
              <li>Créez une application sur Meta for Developers et ajoutez le produit WhatsApp.</li>
              <li>Déclarez l'adresse du webhook : <code className="code">{window.location.origin}/api/whatsapp/webhook/</code></li>
              <li>Renseignez <code className="code">WHATSAPP_TOKEN</code>, <code className="code">WHATSAPP_PHONE_ID</code> et <code className="code">WHATSAPP_VERIFY_TOKEN</code> sur le serveur.</li>
              <li>Ajoutez le numéro de téléphone de chaque agent dans <Link to="/parametres">Paramètres</Link>.</li>
            </ol>
          </Carte>
        </div>
      </div>

      {validation && <Validation d={validation} onFermer={() => setValidation(null)}
        onFait={(r) => { setValidation(null); notifier(r.bien_code ? `Validée : ${r.bien_code} est dans l'inventaire.` : "Déclaration validée."); recharger(); }} />}
      {rejet && <Rejet d={rejet} onFermer={() => setRejet(null)} onFait={() => { setRejet(null); notifier("Déclaration rejetée, l'auteur est prévenu."); recharger(); }} />}
    </>
  );
}

function LigneDeclaration({ d, peutValider, onValider, onRejeter }) {
  const i = d.interpretation || {};
  const ex = i.bien_existant;
  return (
    <article className="declaration">
      <div style={{ minWidth: 0 }}>
        <div className="actions" style={{ gap: 8 }}>
          <b>{d.auteur_nom || d.expediteur}</b>
          <span className="badge info">{d.canal_libelle}</span>
          <span className="petit muet">{d.district_nom ? `${d.district_nom}, ` : ""}{dateHeure(d.recue_le)}</span>
        </div>
        {(d.texte || d.transcription) && (
          <div className="citation">
            {d.transcription && <Mic size={13} style={{ display: "inline", verticalAlign: -2, marginRight: 6 }} />}
            {d.texte || d.transcription}
          </div>
        )}
        {ex ? (
          <Bandeau type="info" style={{ margin: "6px 0" }}>Concerne un bien existant : <Link to={`/biens/${ex.id}`}>{ex.code} — {ex.nom}</Link></Bandeau>
        ) : null}
        <div className="champs">
          {i.sous_type && <span className="badge">{i.sous_type}</span>}
          {i.etat && <span className={`badge ${i.etat === "BON" ? "bon" : i.etat === "MAUVAIS" ? "critique" : "attention"}`}>{ETAT_LIB[i.etat]}</span>}
          {i.paroisse_nom && <span className="badge">Paroisse : {i.paroisse_nom}</span>}
          {i.quantite > 1 && <span className="badge">{i.quantite} unités</span>}
          {i.valeur_acquisition ? <span className="badge">{bif(i.valeur_acquisition)}</span> : null}
          {i.financeur && <span className="badge">Financeur : {i.financeur}</span>}
          {i.manquants?.length > 0 && <span className="badge attention">Manque : {i.manquants.join(", ")}</span>}
        </div>
        <div className="actions" style={{ marginTop: 10, gap: 14 }}>
          <span className="confiance" title="Part des informations essentielles comprises automatiquement">
            Compréhension <span className="piste"><span style={{ width: `${(i.confiance || 0) * 100}%` }} /></span> {Math.round((i.confiance || 0) * 100)} %
          </span>
          {d.statut === "VALIDEE" && d.bien && <span className="petit">Enregistré : <Link to={`/biens/${d.bien}`}>{d.bien_code}</Link>, par {d.traitee_par}</span>}
          {d.statut === "REJETEE" && <span className="petit muet">Rejetée par {d.traitee_par}{d.motif_rejet ? ` : ${d.motif_rejet}` : ""}</span>}
        </div>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 8, alignItems: "flex-end" }}>
        {d.media && d.media_type === "image" && <img className="media" src={d.media} alt="Photo envoyée" />}
        {d.media && d.media_type === "audio" && <audio controls src={d.media} style={{ width: 200 }} />}
        {d.statut === "EN_ATTENTE" && peutValider && (
          <>
            <button className="bouton principal petit" onClick={onValider}><Check />Valider</button>
            <button className="bouton petit" onClick={onRejeter}><X />Rejeter</button>
          </>
        )}
      </div>
    </article>
  );
}

function Validation({ d, onFermer, onFait }) {
  const i = d.interpretation || {};
  const ex = i.bien_existant;
  const [mode, setMode] = useState(ex ? "mise_a_jour" : "nouveau");
  const [f, setF] = useState({
    nom: i.nom || "", categorie: i.categorie || "IMM", sous_type: i.sous_type || "", etat: i.etat || "BON",
    district: d.district || "", paroisse: i.paroisse || "", quantite: i.quantite || 1, valeur_acquisition: i.valeur_acquisition || 0,
    financeur: i.financeur || "",
  });
  const { donnees: districts } = useApi("districts/");
  const { donnees: paroisses } = useApi(f.district ? `paroisses/?district=${f.district}` : null, [f.district]);
  const [erreur, setErreur] = useState("");
  const [encours, setEncours] = useState(false);
  const maj = (k) => (e) => setF({ ...f, [k]: e.target.value });

  async function valider() {
    setEncours(true);
    setErreur("");
    try {
      const corps = mode === "mise_a_jour" ? { mode, etat: f.etat } : { ...f, paroisse: f.paroisse || null };
      onFait(await api(`declarations/${d.id}/valider/`, { methode: "POST", corps }));
    } catch (e) {
      setErreur(e.message);
    }
    setEncours(false);
  }

  return (
    <Modale titre={`Valider la déclaration n° ${d.id}`} description={`De ${d.auteur_nom}. Corrigez si besoin : l'auteur recevra la confirmation sur WhatsApp.`}
      onFermer={onFermer} largeur={680}
      pied={<><button className="bouton" onClick={onFermer}>Annuler</button><button className="bouton principal" onClick={valider} disabled={encours || (mode === "nouveau" && (!f.nom || !f.district))}>{encours ? <Loader2 className="tourne" /> : <CheckCheck />}{mode === "mise_a_jour" ? "Mettre à jour la fiche" : "Ajouter à l'inventaire"}</button></>}>
      {erreur && <Bandeau type="erreur" style={{ marginBottom: 14 }}>{erreur}</Bandeau>}
      <div className="citation" style={{ fontSize: "0.92rem", background: "var(--surface-2)", borderLeft: "3px solid var(--marque)", borderRadius: "0 8px 8px 0", padding: "8px 12px", marginBottom: 16 }}>
        {d.texte || d.transcription || "(message sans texte)"}
      </div>
      {ex && (
        <div style={{ marginBottom: 16 }}>
          <Segments label="Action" valeur={mode} onChange={setMode} options={[
            { id: "mise_a_jour", libelle: `Mettre à jour ${ex.code}` },
            { id: "nouveau", libelle: "Créer un nouveau bien" },
          ]} />
        </div>
      )}
      {mode === "mise_a_jour" ? (
        <div className="formulaire">
          <p className="large petit muet">L'état de <b>{ex.nom}</b> sera mis à jour et le signalement ajouté à son historique comme inspection. Son score de risque sera recalculé.</p>
          <Champ libelle="Nouvel état">
            <select value={f.etat} onChange={maj("etat")}>{Object.entries(ETATS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
          </Champ>
        </div>
      ) : (
        <div className="formulaire">
          <Champ libelle="Nom du bien" large><input value={f.nom} onChange={maj("nom")} /></Champ>
          <Champ libelle="Catégorie">
            <select value={f.categorie} onChange={maj("categorie")}>{Object.entries(CATEGORIES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
          </Champ>
          <Champ libelle="Type précis"><input value={f.sous_type} onChange={maj("sous_type")} /></Champ>
          <Champ libelle="District">
            <select value={f.district} onChange={(e) => setF({ ...f, district: e.target.value, paroisse: "" })}>
              <option value="">Choisir…</option>{districts?.map((x) => <option key={x.id} value={x.id}>{x.nom}</option>)}
            </select>
          </Champ>
          <Champ libelle="Paroisse">
            <select value={f.paroisse || ""} onChange={maj("paroisse")}><option value="">Aucune</option>{paroisses?.map((p) => <option key={p.id} value={p.id}>{p.nom}</option>)}</select>
          </Champ>
          <Champ libelle="État">
            <select value={f.etat} onChange={maj("etat")}>{Object.entries(ETATS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
          </Champ>
          <Champ libelle="Quantité"><input type="number" min="1" value={f.quantite} onChange={maj("quantite")} /></Champ>
          <Champ libelle={`Valeur d'acquisition (${devise()})`}><input type="number" min="0" value={f.valeur_acquisition} onChange={maj("valeur_acquisition")} /></Champ>
          <Champ libelle="Financeur"><input value={f.financeur} onChange={maj("financeur")} /></Champ>
        </div>
      )}
    </Modale>
  );
}

function Rejet({ d, onFermer, onFait }) {
  const [motif, setMotif] = useState("");
  const [encours, setEncours] = useState(false);
  async function rejeter() {
    setEncours(true);
    await api(`declarations/${d.id}/rejeter/`, { methode: "POST", corps: { motif } }).catch(() => {});
    onFait();
  }
  return (
    <Modale titre={`Rejeter la déclaration n° ${d.id}`} description="L'auteur recevra le motif par WhatsApp." onFermer={onFermer} largeur={520}
      pied={<><button className="bouton" onClick={onFermer}>Annuler</button><button className="bouton danger" onClick={rejeter} disabled={encours}><X />Rejeter</button></>}>
      <Champ libelle="Motif"><textarea value={motif} onChange={(e) => setMotif(e.target.value)} placeholder="Ce bien est déjà enregistré, information incomplète…" /></Champ>
    </Modale>
  );
}

const DEMO_NUMEROS = [
  ["+25779000001", "Agent de Burunga"],
  ["+25779000002", "Surintendant de Gitega"],
];

function Simulateur({ moi, onMessage }) {
  const [tel, setTel] = useState(moi.organisation?.slug === "emu-burundi" ? DEMO_NUMEROS[0][0] : "");
  const [texte, setTexte] = useState("");
  const [fil, setFil] = useState([{ de: "recu", texte: "Bienvenue ! Décrivez un bien en une phrase, ou écrivez AIDE.", heure: new Date() }]);
  const [encours, setEncours] = useState(false);
  const [photo, setPhoto] = useState(null);
  const refFil = useRef(null);
  useEffect(() => refFil.current?.scrollTo({ top: 99999, behavior: "smooth" }), [fil]);

  async function envoyer(e) {
    e.preventDefault();
    if (!texte.trim() && !photo) return;
    const message = texte.trim();
    setFil((f) => [...f, { de: "envoye", texte: (photo ? "📷 Photo\n" : "") + message, heure: new Date() }]);
    setTexte("");
    setEncours(true);
    try {
      const fd = new FormData();
      fd.append("telephone", tel);
      fd.append("texte", message);
      if (photo) fd.append("media", photo);
      const r = await api("declarations/simuler/", { methode: "POST", corps: fd });
      setFil((f) => [...f, { de: "recu", texte: r.reponse, heure: new Date() }]);
      if (r.declaration) onMessage();
    } catch (err) {
      setFil((f) => [...f, { de: "recu", texte: `Erreur : ${err.message}`, heure: new Date() }]);
    }
    setPhoto(null);
    setEncours(false);
  }

  const heure = (d) => d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
  return (
    <section aria-label="Simulateur WhatsApp">
      <div className="actions" style={{ marginBottom: 10, justifyContent: "space-between" }}>
        <h2>Simulateur WhatsApp</h2>
        <select className="saisie-ui" value={tel} onChange={(e) => setTel(e.target.value)} aria-label="Numéro de l'expéditeur" style={{ height: 32, fontSize: "0.82rem" }}>
          <option value="">Mon numéro</option>
          {DEMO_NUMEROS.map(([n, l]) => <option key={n} value={n}>{l}</option>)}
        </select>
      </div>
      <div className="telephone">
        <div className="telephone-tete">
          <img src="/logo.svg" alt="" />
          <div><b>{moi.organisation?.sigle || "UMURAGE"}</b><span>Compte professionnel</span></div>
        </div>
        <div className="telephone-fil" ref={refFil}>
          {fil.map((m, i) => (
            <div key={i} className={`msg ${m.de}`}>{m.texte}<time>{heure(m.heure)}</time></div>
          ))}
          {encours && <div className="msg recu"><span className="points-attente"><span /><span /><span /></span></div>}
        </div>
        <form className="telephone-saisie" onSubmit={envoyer}>
          <label className="icone-bouton" style={{ cursor: "pointer" }} title="Joindre une photo">
            <Image />
            <input type="file" accept="image/*" hidden onChange={(e) => setPhoto(e.target.files[0])} />
          </label>
          <input value={texte} onChange={(e) => setTexte(e.target.value)} placeholder={photo ? `Photo : ${photo.name}` : "Nouveau forage à Kayero, bon état…"} aria-label="Message" />
          <button disabled={encours} aria-label="Envoyer"><Send /></button>
        </form>
      </div>
      <p className="petit muet" style={{ marginTop: 8 }}>
        <PencilLine size={13} style={{ display: "inline", verticalAlign: -2 }} /> Essayez : « 7 chèvres pour les femmes de Kayero, bon état », « ETAT BRG-INF-0001 » ou « Le toit de l'église de Murore fuit ».
      </p>
    </section>
  );
}
