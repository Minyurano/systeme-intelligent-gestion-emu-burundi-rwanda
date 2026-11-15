import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ClipboardList, Lock, PackageSearch, Plus, ScanLine, SearchX, ShieldAlert } from "lucide-react";
import { api } from "../api";
import { useAuth } from "../auth";
import { Bandeau, Carte, EnTete, Etat, Kpi, Progres, useApi, useToast, Vide } from "../components/ui";
import { agir, FormModale } from "../components/metier";
import { ETATS, date, dateHeure } from "../format";

export default function InventaireTerrain() {
  const { peut } = useAuth();
  const notifier = useToast();
  const [ajout, setAjout] = useState(false);
  const { donnees: campagnes, erreur, chargement, recharger } = useApi("campagnes/");
  const { donnees: districts } = useApi("districts/");
  const [choisie, setChoisie] = useState(null);
  useEffect(() => {
    if (campagnes?.length && !choisie) setChoisie(campagnes.find((c) => c.statut === "OUVERTE")?.id || campagnes[0].id);
  }, [campagnes, choisie]);
  const campagne = campagnes?.find((c) => c.id === choisie);

  return (
    <>
      <EnTete titre="Inventaire physique" sousTitre="Chaque année, les agents passent sur le terrain et scannent le QR code de chaque bien. UMURAGE liste les biens non vus, introuvables ou dont l'état a changé, puis produit le procès-verbal.">
        {campagnes?.length > 0 && (
          <select className="saisie-ui" value={choisie || ""} onChange={(e) => setChoisie(Number(e.target.value))} aria-label="Campagne">
            {campagnes.map((c) => <option key={c.id} value={c.id}>{c.nom}</option>)}
          </select>
        )}
        {peut("projets") && <button className="bouton principal" onClick={() => setAjout(true)}><Plus />Nouvelle campagne</button>}
      </EnTete>
      <Etat chargement={chargement && !campagnes} erreur={erreur}>
        {!campagnes?.length ? <Vide titre="Aucune campagne d'inventaire" texte="Lancez une campagne pour un district ou pour toute l'organisation." /> :
          campagne && <Campagne c={campagne} onMaj={recharger} />}
      </Etat>
      {ajout && (
        <FormModale titre="Nouvelle campagne d'inventaire" onFermer={() => setAjout(false)}
          onFait={(c) => { notifier("Campagne ouverte"); setChoisie(c.id); recharger(); }}
          envoyer={(c) => api("campagnes/", { methode: "POST", corps: c })} initial={{ nom: `Inventaire annuel ${new Date().getFullYear()}` }}
          champs={[
            { k: "nom", libelle: "Nom", requis: true, large: true },
            { k: "district", libelle: "District", type: "select", options: [{ v: "", l: "Toute l'organisation" }, ...(districts || []).map((d) => ({ v: d.id, l: d.nom }))] },
            { k: "date_debut", libelle: "Début", type: "date" },
          ]} />
      )}
    </>
  );
}

function Campagne({ c, onMaj }) {
  const { peut } = useAuth();
  const notifier = useToast();
  const { donnees: e, recharger } = useApi(`campagnes/${c.id}/ecarts/`, [c.id]);
  const [code, setCode] = useState("");
  const [etat, setEtat] = useState("");
  const [trouve, setTrouve] = useState(true);
  const [dernier, setDernier] = useState(null);
  const saisie = useRef(null);
  const ouverte = c.statut === "OUVERTE";

  async function scanner(ev) {
    ev?.preventDefault();
    if (!code.trim()) return;
    try {
      const r = await api(`campagnes/${c.id}/scanner/`, { methode: "POST", corps: { code: code.trim(), etat_constate: etat, trouve } });
      setDernier({ ok: true, texte: `${r.bien_code} · ${r.bien_nom} enregistré${trouve ? "" : " comme introuvable"}` });
      setCode(""); setEtat(""); setTrouve(true);
      recharger();
    } catch (err) {
      setDernier({ ok: false, texte: err.message });
    }
    saisie.current?.focus();
  }

  async function cloturer() {
    if (!window.confirm("Clôturer la campagne ? Le procès-verbal sera figé.")) return;
    const appliquer = e?.etats_differents?.length ? window.confirm("Mettre à jour l'état des biens dans l'inventaire avec les états constatés sur le terrain ?") : false;
    if (await agir(`campagnes/${c.id}/cloturer/`, { appliquer_etats: appliquer }, notifier, "Campagne clôturée, procès-verbal établi")) onMaj();
  }

  if (!e) return null;
  return (
    <div className="pile">
      <div className="kpis">
        <Kpi libelle="Avancement" icone={ClipboardList} ton="info" valeur={`${e.avancement} %`} note={`${e.vus} biens vus sur ${e.biens}`} />
        <Kpi libelle="Conformes" icone={PackageSearch} ton="bon" valeur={e.conformes} />
        <Kpi libelle="État différent de la fiche" icone={ShieldAlert} ton={e.etats_differents.length ? "attention" : "bon"} valeur={e.etats_differents.length} />
        <Kpi libelle="Introuvables" icone={SearchX} ton={e.introuvables.length ? "critique" : "bon"} valeur={e.introuvables.length} note="Un ordre d'inspection sera ouvert" />
      </div>
      <Carte titre={c.nom} description={`${c.district_nom || "Toute l'organisation"} · ouverte le ${date(c.date_debut)}${c.cloturee_le ? ` · clôturée le ${dateHeure(c.cloturee_le)}` : ""}`}
        actions={ouverte && peut("projets") && <button className="bouton" onClick={cloturer}><Lock />Clôturer et établir le PV</button>}>
        <Progres valeur={e.avancement} />
        {ouverte ? (
          <form onSubmit={scanner} className="formulaire" style={{ marginTop: 14 }}>
            <fieldset>
              <legend>Scanner un bien</legend>
              <label className="champ">Code du bien (QR code ou saisie)
                <input ref={saisie} value={code} onChange={(x) => setCode(x.target.value)} placeholder="GIT-IMM-0003" autoFocus />
              </label>
              <label className="champ">État constaté
                <select value={etat} onChange={(x) => setEtat(x.target.value)}>
                  <option value="">Identique à la fiche</option>
                  {Object.entries(ETATS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
              </label>
              <label className="champ">Bien trouvé ?
                <select value={trouve ? "1" : "0"} onChange={(x) => setTrouve(x.target.value === "1")}>
                  <option value="1">Oui, vu sur place</option><option value="0">Non, introuvable</option>
                </select>
              </label>
              <div style={{ display: "flex", alignItems: "end" }}><button className="bouton principal" type="submit" disabled={!code.trim()}><ScanLine />Enregistrer</button></div>
            </fieldset>
            {dernier && <Bandeau type={dernier.ok ? "succes" : "erreur"}>{dernier.texte}</Bandeau>}
          </form>
        ) : <Bandeau type="succes" style={{ marginTop: 14 }}>Campagne clôturée. Procès-verbal établi par {c.proces_verbal?.cloture_par}{c.proces_verbal?.etats_appliques ? ", états mis à jour dans l'inventaire" : ""}.</Bandeau>}
      </Carte>
      {e.etats_differents.length > 0 && (
        <Carte brut titre="État différent de la fiche">
          <table className="tableau"><thead><tr><th>Bien</th><th>Fiche</th><th>Constaté</th><th>Par</th></tr></thead>
            <tbody>{e.etats_differents.map((k) => (
              <tr key={k.id}><td><Link to={`/biens/${k.bien}`}>{k.bien_code}</Link> · {k.bien_nom}</td><td>{ETATS[k.etat_fiche]}</td>
                <td><span className="badge attention">{ETATS[k.etat_constate]}</span></td><td>{k.agent_nom}</td></tr>
            ))}</tbody></table>
        </Carte>
      )}
      {e.introuvables.length > 0 && (
        <Carte brut titre="Biens introuvables">
          <table className="tableau"><tbody>{e.introuvables.map((k) => (
            <tr key={k.id}><td><Link to={`/biens/${k.bien}`}>{k.bien_code}</Link> · {k.bien_nom}</td><td>{k.commentaire}</td><td>{k.agent_nom}</td></tr>
          ))}</tbody></table>
        </Carte>
      )}
      <Carte brut titre="Biens pas encore vus" description={`${e.non_vus.length} bien(s)`}>
        {e.non_vus.length === 0 ? <Vide titre="Tous les biens ont été vus" /> : (
          <div className="defilement" style={{ maxHeight: 360 }}><table className="tableau"><tbody>{e.non_vus.map((b) => (
            <tr key={b.id}><td><button className="bouton fantome petit" onClick={() => setCode(b.code)} disabled={!ouverte}>{b.code}</button></td><td>{b.nom}</td><td>{b.district}</td></tr>
          ))}</tbody></table></div>
        )}
      </Carte>
    </div>
  );
}
