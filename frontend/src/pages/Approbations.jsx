import { useState } from "react";
import { CheckCircle2, CircleDot, Gavel, Play, Plus, XCircle } from "lucide-react";
import { useAuth } from "../auth";
import { api } from "../api";
import { Carte, EnTete, Etat, Kpi, Modale, Segments, useApi, useToast, Vide } from "../components/ui";
import { agir, FormModale, optionsBiens, useBiens } from "../components/metier";
import { bif, dateHeure } from "../format";

const TYPES = {
  CESSION: "Cession (vente, don) d'un bien", ACQUISITION: "Acquisition d'un bien", TRANSFERT: "Transfert vers un autre district",
  TRAVAUX: "Travaux importants", DEPENSE: "Dépense",
};
const ROLES = { SURINTENDANT: "Surintendant", TRESORIER: "Trésorier", EVEQUE: "Évêque / Direction", ADMIN: "Administrateur" };
const TON = { EN_ATTENTE: "info", APPROUVEE: "bon", EXECUTEE: "", REJETEE: "critique", ANNULEE: "" };
const CATEGORIES_DEPENSE = { ACHAT: "Achat de matériel", MAINTENANCE: "Maintenance", CONSTRUCTION: "Construction", FONCTIONNEMENT: "Fonctionnement", SALAIRE: "Salaires" };

export default function Approbations() {
  const { moi } = useAuth();
  const notifier = useToast();
  const [vue, setVue] = useState("a_traiter");
  const [nouvelle, setNouvelle] = useState(false);
  const [ouverte, setOuverte] = useState(null);
  const { donnees, erreur, chargement, recharger } = useApi("demandes/?page_size=200");
  const { donnees: districts } = useApi("districts/");
  const biens = useBiens();
  const liste = donnees?.results || [];
  const aTraiter = liste.filter((d) => d.je_peux_valider || d.je_peux_executer);
  const filtres = {
    a_traiter: aTraiter,
    en_cours: liste.filter((d) => d.statut === "EN_ATTENTE"),
    miennes: liste.filter((d) => d.demandeur_nom === moi.nom),
    toutes: liste,
  };
  const affichees = filtres[vue];

  return (
    <>
      <EnTete titre="Approbations" sousTitre="Les décisions qui engagent le patrimoine passent par plusieurs niveaux de validation. Personne ne valide sa propre demande, et chaque avis est tracé.">
        <button className="bouton principal" onClick={() => setNouvelle(true)}><Plus />Nouvelle demande</button>
      </EnTete>
      <Etat chargement={chargement && !donnees} erreur={erreur}>
        <div className="pile">
          <div className="kpis">
            <Kpi libelle="À traiter par moi" icone={Gavel} ton={aTraiter.length ? "attention" : "bon"} valeur={aTraiter.length} note="Validation ou exécution" />
            <Kpi libelle="En cours de circuit" icone={CircleDot} valeur={filtres.en_cours.length} note="En attente d'un avis" />
            <Kpi libelle="Approuvées à exécuter" icone={Play} ton="info" valeur={liste.filter((d) => d.statut === "APPROUVEE").length} />
            <Kpi libelle="Rejetées" icone={XCircle} valeur={liste.filter((d) => d.statut === "REJETEE").length} />
          </div>
          <Carte brut titre="Demandes" actions={<Segments label="Vue" valeur={vue} onChange={setVue} options={[
            { id: "a_traiter", libelle: "À traiter", nb: aTraiter.length }, { id: "en_cours", libelle: "En cours" },
            { id: "miennes", libelle: "Mes demandes" }, { id: "toutes", libelle: "Toutes" },
          ]} />}>
            <div style={{ height: 12 }} />
            {affichees.length === 0 ? <Vide titre="Rien à afficher" texte={vue === "a_traiter" ? "Aucune demande n'attend votre décision." : undefined} /> : (
              <div className="defilement"><table className="tableau">
                <thead><tr><th>Demande</th><th>Montant</th><th>Circuit</th><th>Statut</th><th /></tr></thead>
                <tbody>
                  {affichees.map((d) => (
                    <tr key={d.id} onClick={() => setOuverte(d)} style={{ cursor: "pointer" }}>
                      <td><div className="principal-cell">{d.titre}</div><div className="secondaire">{d.type_libelle} · {d.district_nom}{d.bien_code ? ` · ${d.bien_code}` : ""} · {d.demandeur_nom}</div></td>
                      <td className="num chiffre">{Number(d.montant) ? bif(d.montant, true) : "—"}</td>
                      <td><Circuit d={d} /></td>
                      <td><span className={`badge ${TON[d.statut]}`}>{d.statut_libelle}</span></td>
                      <td>{(d.je_peux_valider || d.je_peux_executer) && <span className="badge attention">À vous</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table></div>
            )}
          </Carte>
        </div>
      </Etat>

      {nouvelle && (
        <FormModale titre="Nouvelle demande" description="Le circuit de validation est choisi automatiquement selon le type et le montant."
          onFermer={() => setNouvelle(false)} onFait={() => { notifier("Demande envoyée en validation"); recharger(); }}
          envoyer={(c) => api("demandes/", { methode: "POST", corps: c })}
          initial={{ type: "CESSION", district: moi.voit_tout ? "" : moi.district }}
          champs={[
            { k: "type", libelle: "Type", type: "select", options: Object.entries(TYPES).map(([v, l]) => ({ v, l })), requis: true },
            { k: "titre", libelle: "Objet", requis: true, large: true, exemple: "Vente de la parcelle non exploitée de Muyange" },
            { k: "district", libelle: "District", type: "select", requis: true, options: [{ v: "", l: "—" }, ...(districts || []).map((x) => ({ v: x.id, l: x.nom }))] },
            { k: "bien", libelle: "Bien concerné", type: "select", options: optionsBiens(biens), cache: (f) => f.type === "ACQUISITION" },
            { k: "district_destination", libelle: "District qui reçoit le bien", type: "select", cache: (f) => f.type !== "TRANSFERT",
              options: [{ v: "", l: "—" }, ...(districts || []).map((x) => ({ v: x.id, l: x.nom }))] },
            { k: "montant", libelle: "Montant", type: "nombre", aide: "Prix de vente, coût des travaux ou de la dépense" },
            { k: "categorie_depense", libelle: "Nature de la dépense", type: "select", cache: (f) => f.type !== "DEPENSE",
              options: [{ v: "", l: "—" }, ...Object.entries(CATEGORIES_DEPENSE).map(([v, l]) => ({ v, l }))] },
            { k: "description", libelle: "Justification", type: "zone", exemple: "Pourquoi cette décision, devis, avis du conseil paroissial…" },
          ]} />
      )}
      {ouverte && <Detail d={ouverte} onFermer={() => setOuverte(null)} onMaj={(d) => { setOuverte(d); recharger(); }} />}
    </>
  );
}

function Circuit({ d }) {
  return (
    <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
      {d.circuit.map((r, i) => {
        const avis = d.avis.find((a) => a.niveau === i);
        const ton = avis ? (avis.decision === "APPROUVE" ? "bon" : "critique") : i === d.niveau && d.statut === "EN_ATTENTE" ? "info" : "";
        return <span key={i} className={`badge ${ton}`} title={avis ? `${avis.utilisateur_nom} : ${avis.commentaire || avis.decision}` : "En attente"}>{ROLES[r] || r}</span>;
      })}
    </div>
  );
}

function Detail({ d, onFermer, onMaj }) {
  const notifier = useToast();
  const [commentaire, setCommentaire] = useState("");
  const decider = async (decision) => {
    const r = await agir(`demandes/${d.id}/valider/`, { decision, commentaire }, notifier, decision === "REJETE" ? "Demande rejetée" : "Avis enregistré");
    if (r) onMaj(r);
  };
  const executer = async () => {
    const r = await agir(`demandes/${d.id}/executer/`, {}, notifier, "Décision exécutée");
    if (r) onMaj(r);
  };
  return (
    <Modale titre={d.titre} description={`${d.type_libelle} · ${d.district_nom} · demandé par ${d.demandeur_nom}`} onFermer={onFermer} largeur={640}
      pied={d.je_peux_valider ? (
        <>
          <button className="bouton danger" onClick={() => decider("REJETE")} disabled={!commentaire.trim()} title="Un motif est obligatoire"><XCircle />Rejeter</button>
          <button className="bouton principal" onClick={() => decider("APPROUVE")}><CheckCircle2 />Approuver</button>
        </>
      ) : d.je_peux_executer ? <button className="bouton principal" onClick={executer}><Play />Exécuter la décision</button> : null}>
      <div className="pile">
        {d.description && <p>{d.description}</p>}
        <div className="champs" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
          {d.bien_nom && <div><span className="secondaire">Bien</span><div>{d.bien_code} · {d.bien_nom}</div></div>}
          {Number(d.montant) > 0 && <div><span className="secondaire">Montant</span><div className="chiffre">{bif(d.montant)}</div></div>}
          {d.district_destination_nom && <div><span className="secondaire">Vers</span><div>{d.district_destination_nom}</div></div>}
          <div><span className="secondaire">Statut</span><div>{d.statut_libelle}</div></div>
        </div>
        <div>
          <h3 style={{ fontSize: "1rem", marginBottom: 8 }}>Circuit de validation</h3>
          <ol style={{ margin: 0, paddingLeft: 18, display: "grid", gap: 6 }}>
            {d.circuit.map((r, i) => {
              const a = d.avis.find((x) => x.niveau === i);
              return (
                <li key={i}>
                  <b>{ROLES[r] || r}</b>{" — "}
                  {a ? <span>{a.decision === "APPROUVE" ? "approuvé" : "rejeté"} par {a.utilisateur_nom}, {dateHeure(a.date)}{a.commentaire && <> : « {a.commentaire} »</>}</span>
                    : i === d.niveau && d.statut === "EN_ATTENTE" ? <span className="badge info">en attente</span> : <span className="muet">à venir</span>}
                </li>
              );
            })}
          </ol>
        </div>
        {d.resultat && <p className="secondaire">Exécution : {d.resultat}</p>}
        {d.je_peux_valider && (
          <label className="champ large">Votre avis (obligatoire pour un rejet)
            <textarea rows={2} value={commentaire} onChange={(e) => setCommentaire(e.target.value)} placeholder="Conditions, réserves, motif…" />
          </label>
        )}
      </div>
    </Modale>
  );
}
