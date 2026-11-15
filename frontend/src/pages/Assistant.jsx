import { Fragment, useEffect, useRef, useState } from "react";
import { BookOpen, Database, FileText, Loader2, Mic, Send, Sparkles, Upload } from "lucide-react";
import { api } from "../api";
import { useAuth } from "../auth";
import { Bandeau, Carte, Champ, EnTete, Etat, Modale, useApi, useToast } from "../components/ui";
import { date } from "../format";

const SUGGESTIONS = [
  "Quels terrains n'ont pas de titre foncier ?",
  "Quels biens sont à risque ?",
  "Qui a financé le forage de Muyange ?",
  "Quand le champ missionnaire a-t-il ouvert à Kayero ?",
  "Quelle est la valeur des forages ?",
  "Où en sont les projets de Butanyerera ?",
];

const Reconnaissance = typeof window !== "undefined" && (window.SpeechRecognition || window.webkitSpeechRecognition);
const initiales = (nom = "") => nom.split(/\s+/).filter(Boolean).slice(0, 2).map((m) => m[0]).join("").toUpperCase();

// Remplace « [Source n] » par une petite pastille de référence.
function avecReferences(texte) {
  return texte.split(/(\[Source \d+\])/g).map((m, i) => {
    const n = m.match(/\[Source (\d+)\]/);
    return n ? <span key={i} className="ref" title={`Source ${n[1]}`}>{n[1]}</span> : <Fragment key={i}>{m}</Fragment>;
  });
}

// Met en forme la réponse : sections « D'après la base de données » et « Dans les archives ».
function Reponse({ texte }) {
  return texte.split(/\n\n+/).map((bloc, i) => {
    const lignes = bloc.split("\n");
    const titre = lignes[0].endsWith(":") ? lignes.shift().replace(/\s*:$/, "") : null;
    const Ic = titre?.includes("base") ? Database : titre?.includes("archives") ? BookOpen : null;
    const puces = lignes.filter((l) => l.startsWith("• "));
    return (
      <div className="section" key={i}>
        {titre && <h4>{Ic && <Ic />}{titre}</h4>}
        {puces.length ? (
          <ul>{puces.map((l, j) => <li key={j}>{avecReferences(l.slice(2))}</li>)}</ul>
        ) : <p>{avecReferences(lignes.join("\n"))}</p>}
      </div>
    );
  });
}

export default function Assistant() {
  const { moi, peut } = useAuth();
  const notifier = useToast();
  const [fil, setFil] = useState([]);
  const [question, setQuestion] = useState("");
  const [encours, setEncours] = useState(false);
  const [ecoute, setEcoute] = useState(false);
  const [ajout, setAjout] = useState(false);
  const docs = useApi("documents/");
  const bas = useRef(null);

  useEffect(() => bas.current?.scrollIntoView({ behavior: "smooth", block: "end" }), [fil, encours]);

  async function poser(q) {
    const texte = (q ?? question).trim();
    if (texte.length < 3 || encours) return;
    setQuestion("");
    setFil((f) => [...f, { de: "moi", texte }]);
    setEncours(true);
    try {
      const r = await api("ia/assistant/", { methode: "POST", corps: { question: texte } });
      setFil((f) => [...f, { de: "ia", texte: r.reponse, sources: r.sources, mode: r.mode, avertissement: r.avertissement }]);
    } catch (e) {
      setFil((f) => [...f, { de: "ia", texte: `La question n'a pas pu être traitée : ${e.message}` }]);
    }
    setEncours(false);
  }

  function dicter() {
    const rec = new Reconnaissance();
    rec.lang = "fr-FR";
    rec.onresult = (e) => setQuestion(e.results[0][0].transcript);
    rec.onend = () => setEcoute(false);
    rec.onerror = () => setEcoute(false);
    setEcoute(true);
    rec.start();
  }

  return (
    <>
      <EnTete titre="Assistant et archives" sousTitre="Posez une question en langage courant. L'assistant répond à partir de l'inventaire et des archives de l'Église, et cite toujours ses sources." />
      <div className="grille g-2-1">
        <section className="carte-ui conversation" aria-label="Conversation avec l'assistant">
          <div className="fil" aria-live="polite">
            {fil.length === 0 && (
              <div className="accueil-assistant">
                <div className="logo-ia"><img src="/logo.svg" alt="" /></div>
                <div>
                  <h2 style={{ fontSize: "1.3rem" }}>Que voulez-vous savoir sur le patrimoine ?</h2>
                  <p className="muet" style={{ marginTop: 6 }}>Les chiffres viennent de la base de données, les faits historiques des documents archivés.</p>
                </div>
                <div className="suggestions">
                  {SUGGESTIONS.map((s) => <button key={s} onClick={() => poser(s)}><Sparkles />{s}</button>)}
                </div>
              </div>
            )}
            {fil.map((m, i) => (
              m.de === "moi" ? (
                <div key={i} className="message moi"><div className="bulle">{m.texte}</div></div>
              ) : (
                <div key={i} className="message ia">
                  <span className="avatar ia"><img src="/logo.svg" alt="" /></span>
                  <div>
                    <div className="bulle">
                      <Reponse texte={m.texte} />
                      {m.avertissement && <Bandeau type="attention" style={{ marginTop: 10 }}>{m.avertissement}</Bandeau>}
                    </div>
                    {m.sources?.length > 0 && (
                      <div className="sources">
                        {m.sources.map((s, j) => (
                          <details key={j}>
                            <summary><span className="ref">{j + 1}</span><FileText />{s.titre}</summary>
                            <p>{s.extrait}…</p>
                          </details>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )
            ))}
            {encours && (
              <div className="message ia">
                <span className="avatar ia"><img src="/logo.svg" alt="" /></span>
                <div className="bulle" style={{ display: "inline-flex", alignItems: "center", gap: 10, width: "fit-content" }}>
                  <span className="points-attente"><span /><span /><span /></span>
                  <span className="muet petit">Recherche dans les données et les archives</span>
                </div>
              </div>
            )}
            <div ref={bas} />
          </div>
          <form className="compositeur" onSubmit={(e) => { e.preventDefault(); poser(); }}>
            <span className="avatar masquer-mobile" style={{ width: 32, height: 32, fontSize: "0.72rem" }}>{initiales(moi.nom)}</span>
            <input value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="Posez votre question…" aria-label="Votre question" />
            {Reconnaissance && (
              <button type="button" className="bouton" onClick={dicter} disabled={ecoute} aria-label="Dicter la question" title="Dicter la question (français)">
                {ecoute ? <Loader2 className="tourne" /> : <Mic />}
              </button>
            )}
            <button className="bouton principal" disabled={encours || question.trim().length < 3}><Send />Envoyer</button>
          </form>
        </section>

        <Carte titre="Archives" description="Le texte des PDF, documents Word et photos est extrait automatiquement (OCR)." plein
          actions={peut("documents") && <button className="bouton petit" onClick={() => setAjout(true)}><Upload />Ajouter</button>}
          pied={docs.donnees && <span>{docs.donnees.count} documents indexés</span>}>
          <Etat chargement={docs.chargement && !docs.donnees} erreur={docs.erreur}>
            <ul className="fil-activite">
              {docs.donnees?.results.map((d) => (
                <li key={d.id}>
                  <span className="icone" style={{ background: "var(--lac-pale)", color: "var(--lac)", borderRadius: 9 }}><FileText /></span>
                  <div>
                    <div className="titre">{d.fichier ? <a href={d.fichier} target="_blank" rel="noreferrer">{d.titre}</a> : d.titre}</div>
                    <div className="meta">{d.type_libelle}, {date(d.date)}{d.taille_texte ? "" : ", texte non extrait"}</div>
                  </div>
                </li>
              ))}
            </ul>
          </Etat>
        </Carte>
      </div>
      {ajout && <NouveauDocument onFermer={() => setAjout(false)} onEnregistre={() => { setAjout(false); notifier("Document ajouté et indexé pour l'assistant."); docs.recharger(); }} />}
    </>
  );
}

function NouveauDocument({ onFermer, onEnregistre }) {
  const [titre, setTitre] = useState("");
  const [type, setType] = useState("RAPPORT");
  const [ddate, setDdate] = useState("");
  const [fichier, setFichier] = useState(null);
  const [contenu, setContenu] = useState("");
  const [erreur, setErreur] = useState("");
  const [encours, setEncours] = useState(false);

  async function envoyer() {
    const fd = new FormData();
    fd.append("titre", titre);
    fd.append("type", type);
    if (ddate) fd.append("date", ddate);
    if (fichier) fd.append("fichier", fichier);
    if (contenu) fd.append("contenu", contenu);
    setEncours(true);
    try {
      await api("documents/", { methode: "POST", corps: fd });
      onEnregistre();
    } catch (e) {
      setErreur(e.message);
    }
    setEncours(false);
  }

  return (
    <Modale titre="Ajouter un document aux archives" description="Titres fonciers, contrats, rapports : le texte sera lu par l'assistant." onFermer={onFermer} largeur={640}
      pied={<><button className="bouton" onClick={onFermer}>Annuler</button><button className="bouton principal" onClick={envoyer} disabled={!titre || (!fichier && !contenu) || encours}>{encours ? <Loader2 className="tourne" /> : <Upload />}{encours ? "Extraction du texte…" : "Ajouter le document"}</button></>}>
      {erreur && <Bandeau type="erreur" style={{ marginBottom: 14 }}>{erreur}</Bandeau>}
      <div className="formulaire">
        <Champ libelle="Titre" large><input value={titre} onChange={(e) => setTitre(e.target.value)} /></Champ>
        <Champ libelle="Type">
          <select value={type} onChange={(e) => setType(e.target.value)}>
            <option value="TITRE_FONCIER">Titre foncier</option><option value="CONTRAT">Contrat</option><option value="RAPPORT">Rapport</option>
            <option value="CONVENTION">Convention</option><option value="FACTURE">Facture</option><option value="AUTRE">Autre</option>
          </select>
        </Champ>
        <Champ libelle="Date du document"><input type="date" value={ddate} onChange={(e) => setDdate(e.target.value)} /></Champ>
        <Champ libelle="Fichier" aide="PDF, Word, photo (JPG, PNG) ou texte." large>
          <input type="file" accept=".pdf,.docx,.txt,.md,.jpg,.jpeg,.png" onChange={(e) => setFichier(e.target.files[0])} style={{ height: "auto", padding: 8 }} />
        </Champ>
        <Champ libelle="Ou texte du document" aide="Facultatif si un fichier est joint." large>
          <textarea value={contenu} onChange={(e) => setContenu(e.target.value)} />
        </Champ>
      </div>
    </Modale>
  );
}
