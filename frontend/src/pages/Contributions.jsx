import { useEffect, useRef, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Ban, FileBadge, HandCoins, Loader2, Printer, Receipt, Search, UserRound, Users, X } from "lucide-react";
import { api } from "../api";
import { useAuth } from "../auth";
import { imprimerAttestation, imprimerRecu } from "../components/Recus";
import { Bandeau, Carte, Champ, EnTete, Etat, InfoBulle, Kpi, Modale, Pagination, Progres, Segments, useApi, useToast, Vide } from "../components/ui";
import { bif, date as dateFr, nombre } from "../format";
import { useCouleurs } from "../theme";

const TYPES = [["DIME", "Dîme"], ["OFFRANDE", "Offrande"], ["ACTION_GRACES", "Action de grâces"], ["CONSTRUCTION", "Construction"],
  ["MISSION", "Mission et solidarité"], ["MINISTERE", "Cotisation de ministère"], ["AUTRE", "Autre"]];
const MODES = [["ESPECES", "Espèces"], ["MOBILE", "Mobile Money"], ["BANQUE", "Banque"], ["NATURE", "En nature"]];
const MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."];
const aujourdhui = () => new Date().toISOString().slice(0, 10);

export default function Contributions() {
  const { moi } = useAuth();
  const org = moi.organisation;
  const saisie = ["ADMIN", "TRESORIER", "SURINTENDANT", "AGENT"].includes(moi.role);
  const annulation = ["ADMIN", "TRESORIER"].includes(moi.role);
  const [annee, setAnnee] = useState(new Date().getFullYear());
  const [version, setVersion] = useState(0);
  const synthese = useApi(`contributions/synthese/?annee=${annee}&v=${version}`, [annee, version]);
  const s = synthese.donnees;
  const recharger = () => setVersion((v) => v + 1);

  return (
    <>
      <EnTete titre="Dîmes et offrandes"
        sousTitre="Chaque contribution reçoit un reçu numéroté et entre dans la comptabilité. Les membres retrouvent leurs dons et leur attestation annuelle dans leur espace.">
        <select className="saisie-ui" value={annee} onChange={(e) => setAnnee(+e.target.value)} aria-label="Année">
          {(s?.annees || [annee]).map((a) => <option key={a} value={a}>{a}</option>)}
        </select>
      </EnTete>
      <div className="pile">
        <div className="kpis">
          <Kpi libelle={`Total ${annee}`} icone={HandCoins} ton="bon" valeur={s ? bif(s.total, true) : "…"}
            note={s?.evolution_pct != null ? `${s.evolution_pct > 0 ? "+" : ""}${s.evolution_pct.toLocaleString("fr-FR")} % sur la même période de ${annee - 1}` : "pas de comparaison"}
            noteTon={s?.evolution_pct < 0 ? "critique" : ""} />
          <Kpi libelle="Donateurs identifiés" icone={Users} ton="info" valeur={s ? nombre(s.donateurs) : "…"} note="membres ayant donné cette année" />
          <Kpi libelle="Quêtes anonymes" icone={HandCoins} ton="attention" valeur={s ? bif(s.anonyme, true) : "…"}
            note={s?.total ? `${Math.round((100 * s.anonyme) / s.total)} % du total` : ""} />
          <Kpi libelle="Reçus émis" icone={Receipt} ton="info" valeur={s ? nombre(s.nombre) : "…"} note="hors reçus annulés" />
        </div>
        <div className="grille g-3-2">
          <Carte titre="Contributions par mois" description={`${annee} comparé à ${annee - 1}`}>
            <Etat chargement={!s} erreur={synthese.erreur}><GraphiqueMois s={s} /></Etat>
          </Carte>
          {saisie ? <SaisieRapide org={org} onFait={recharger} /> : (
            <Carte titre="Par nature"><ParType s={s} /></Carte>
          )}
        </div>
        {saisie && (
          <div className="grille g2">
            <Carte titre="Par nature"><ParType s={s} /></Carte>
            <Carte brut titre="Par église locale">
              <ParParoisse s={s} />
            </Carte>
          </div>
        )}
        <Liste annee={annee} org={org} annulation={annulation} version={version} onChange={recharger} />
      </div>
    </>
  );
}

function GraphiqueMois({ s }) {
  const c = useCouleurs();
  const donnees = s.par_mois.map((m) => ({ mois: MOIS[m.mois - 1], [s.annee]: Number(m.total), [s.annee - 1]: Number(m.annee_precedente) }));
  return (
    <>
      <div className="legende-graphique">
        <span><i style={{ background: c.marque }} />{s.annee}</span>
        <span><i style={{ background: c.axe, opacity: 0.45 }} />{s.annee - 1}</span>
      </div>
      <div style={{ height: 250 }}>
        <ResponsiveContainer>
          <BarChart data={donnees} barGap={2} barCategoryGap="22%">
            <CartesianGrid vertical={false} stroke={c.grille} />
            <XAxis dataKey="mois" tick={{ fontSize: 12, fill: c.axe }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 12, fill: c.axe }} axisLine={false} tickLine={false} width={52}
              tickFormatter={(v) => (v >= 1e6 ? `${(v / 1e6).toLocaleString("fr-FR", { maximumFractionDigits: 1 })} M` : v >= 1e3 ? `${Math.round(v / 1e3)} k` : v)} />
            <Tooltip cursor={{ fill: c.curseur }} content={<InfoBulle format={(v) => bif(v)} />} />
            <Bar dataKey={String(s.annee - 1)} name={String(s.annee - 1)} fill={c.axe} fillOpacity={0.35} radius={[4, 4, 0, 0]} />
            <Bar dataKey={String(s.annee)} name={String(s.annee)} fill={c.marque} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </>
  );
}

function ParType({ s }) {
  if (!s) return null;
  if (!s.par_type.length) return <p className="muet">Aucune contribution cette année.</p>;
  return (
    <div className="pile" style={{ gap: 12 }}>
      {s.par_type.map((t) => (
        <div key={t.type}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}><span>{t.libelle}</span><b className="chiffre">{bif(t.total, true)}</b></div>
          <Progres valeur={s.total ? (100 * t.total) / s.total : 0} />
        </div>
      ))}
    </div>
  );
}

function ParParoisse({ s }) {
  if (!s?.par_paroisse.length) return <p className="muet" style={{ padding: "0 20px 20px" }}>Aucune contribution cette année.</p>;
  return (
    <div className="defilement"><table className="tableau">
      <thead><tr><th>Église locale</th><th className="num">Donateurs</th><th className="num">Total</th></tr></thead>
      <tbody>{s.par_paroisse.map((p) => (
        <tr key={p.paroisse}><td className="principal-cell">{p.nom}</td><td className="num chiffre">{nombre(p.donateurs)}</td><td className="num chiffre">{bif(p.total)}</td></tr>
      ))}</tbody>
    </table></div>
  );
}

// Saisie rapide pensée pour le dimanche : le membre, le montant, Entrée. L'église et la date restent pour la suivante.
function SaisieRapide({ org, onFait }) {
  const notifier = useToast();
  const { donnees: paroisses } = useApi("paroisses/");
  const [membre, setMembre] = useState(null);
  const [anonyme, setAnonyme] = useState(false);
  const [f, setF] = useState({ type: "DIME", montant: "", mode: "ESPECES", reference: "", date: aujourdhui(), paroisse: "", note: "" });
  const [erreur, setErreur] = useState("");
  const [encours, setEncours] = useState(false);
  const [dernier, setDernier] = useState(null);
  const refMontant = useRef(null);
  const maj = (k) => (e) => setF({ ...f, [k]: e.target.value });

  async function enregistrer(e) {
    e.preventDefault();
    setEncours(true); setErreur("");
    try {
      const corps = { ...f, membre: anonyme ? null : membre?.id, paroisse: f.paroisse || membre?.paroisse || null };
      if (!corps.paroisse) delete corps.paroisse;
      const r = await api("contributions/", { methode: "POST", corps });
      setDernier(r);
      notifier(`Reçu ${r.numero_recu} : ${bif(r.montant)}`);
      setMembre(null);
      setF({ ...f, montant: "", reference: "", note: "" });
      onFait();
    } catch (err) {
      setErreur(err.message);
    }
    setEncours(false);
  }
  const pret = (anonyme ? f.paroisse : membre) && Number(f.montant) > 0 && (f.mode !== "MOBILE" || f.reference);

  return (
    <Carte titre="Saisie rapide" description="Un reçu numéroté est créé à chaque enregistrement.">
      <form className="pile" style={{ gap: 12 }} onSubmit={enregistrer}>
        {erreur && <Bandeau type="erreur">{erreur}</Bandeau>}
        <Segments label="Donateur" valeur={anonyme ? "anonyme" : "membre"} onChange={(v) => setAnonyme(v === "anonyme")}
          options={[{ id: "membre", libelle: "Un membre" }, { id: "anonyme", libelle: "Quête anonyme" }]} />
        {anonyme ? (
          <Champ libelle="Église locale">
            <select value={f.paroisse} onChange={maj("paroisse")} required>
              <option value="">Choisir…</option>{(paroisses || []).map((p) => <option key={p.id} value={p.id}>{p.nom}</option>)}
            </select>
          </Champ>
        ) : <ChercherMembre membre={membre} onChoisir={(m) => { setMembre(m); setTimeout(() => refMontant.current?.focus(), 50); }} />}
        <div className="formulaire">
          <Champ libelle="Nature"><select value={f.type} onChange={maj("type")}>{TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></Champ>
          <Champ libelle={`Montant (${org?.devise})`}><input ref={refMontant} type="number" min="1" step="1" inputMode="numeric" value={f.montant} onChange={maj("montant")} required /></Champ>
          <Champ libelle="Mode"><select value={f.mode} onChange={maj("mode")}>{MODES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></Champ>
          <Champ libelle="Date"><input type="date" value={f.date} max={aujourdhui()} onChange={maj("date")} required /></Champ>
          {f.mode === "MOBILE" && <Champ libelle="Référence Lumicash / EcoCash" large><input value={f.reference} onChange={maj("reference")} required placeholder="ex. LUM48213377" /></Champ>}
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", justifyContent: "space-between", alignItems: "center" }}>
          {dernier ? <button type="button" className="bouton petit" onClick={() => imprimerRecu(dernier, org)}><Printer />Imprimer le reçu {dernier.numero_recu}</button> : <span />}
          <button className="bouton principal" disabled={!pret || encours}>{encours ? <Loader2 className="tourne" /> : <Receipt />}Enregistrer</button>
        </div>
      </form>
    </Carte>
  );
}

function ChercherMembre({ membre, onChoisir }) {
  const [q, setQ] = useState("");
  const [res, setRes] = useState([]);
  useEffect(() => {
    if (q.trim().length < 2) return setRes([]);
    const t = setTimeout(() => api(`registre/?search=${encodeURIComponent(q.trim())}&page_size=8`).then((d) => setRes(d.results || [])).catch(() => setRes([])), 250);
    return () => clearTimeout(t);
  }, [q]);
  if (membre) {
    return (
      <div className="membre-choisi">
        <UserRound size={18} />
        <div><b>{membre.prenom} {membre.nom}</b><div className="secondaire">{membre.numero} · {membre.paroisse_nom}</div></div>
        <button type="button" className="icone-bouton" aria-label="Changer de membre" onClick={() => { onChoisir(null); setQ(""); }}><X size={16} /></button>
      </div>
    );
  }
  return (
    <div style={{ position: "relative" }}>
      <label className="champ">Membre
        <div style={{ position: "relative" }}>
          <Search size={15} style={{ position: "absolute", left: 10, top: 12, color: "var(--encre-3)" }} />
          <input style={{ paddingLeft: 32 }} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Nom, numéro de membre ou téléphone" autoComplete="off" />
        </div>
      </label>
      {res.length > 0 && (
        <ul className="suggestions-membres" role="listbox">
          {res.map((m) => (
            <li key={m.id}><button type="button" onClick={() => onChoisir(m)}>
              <b>{m.prenom} {m.nom}</b><span>{m.numero} · {m.paroisse_nom}{m.statut === "DECEDE" || m.statut === "TRANSFERE" ? ` · ${m.statut_libelle}` : ""}</span>
            </button></li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Liste({ annee, org, annulation, version, onChange }) {
  const notifier = useToast();
  const [q, setQ] = useState("");
  const [type, setType] = useState("");
  const [page, setPage] = useState(1);
  const [annuler, setAnnuler] = useState(null);
  const [encours, setEncours] = useState(null);
  const filtres = new URLSearchParams({ annee, page, ...(q && { search: q }), ...(type && { type }) }).toString();
  const liste = useApi(`contributions/?${filtres}&v=${version}`, [filtres, version]);
  const lignes = liste.donnees?.results || [];

  async function attestation(c) {
    setEncours(c.id);
    try {
      imprimerAttestation(await api("contributions/attestation/", { methode: "POST", corps: { membre: c.membre, annee } }));
    } catch (e) {
      notifier(e.message, "erreur");
    }
    setEncours(null);
  }
  async function confirmerAnnulation() {
    try {
      await api(`contributions/${annuler.c.id}/annuler/`, { methode: "POST", corps: { motif: annuler.motif } });
      notifier(`Reçu ${annuler.c.numero_recu} annulé.`);
      setAnnuler(null);
      onChange();
    } catch (e) {
      notifier(e.message, "erreur");
    }
  }

  return (
    <Carte brut titre={`Contributions ${annee}`} description="Les plus récentes d'abord. Une erreur s'annule avec son motif ; rien n'est supprimé."
      actions={
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <div style={{ position: "relative" }}>
            <Search size={15} style={{ position: "absolute", left: 10, top: 11, color: "var(--encre-3)" }} />
            <input className="saisie-ui" style={{ paddingLeft: 32, width: 230 }} placeholder="Membre, n° de reçu, référence…" value={q}
              onChange={(e) => { setQ(e.target.value); setPage(1); }} aria-label="Rechercher" />
          </div>
          <select className="saisie-ui" value={type} onChange={(e) => { setType(e.target.value); setPage(1); }} aria-label="Nature">
            <option value="">Toutes les natures</option>{TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
      }>
      <Etat chargement={liste.chargement && !liste.donnees} erreur={liste.erreur}>
        {lignes.length === 0 ? <Vide icone={HandCoins} titre="Aucune contribution" texte="Rien ne correspond à ces critères." /> : (
          <div className="defilement"><table className="tableau">
            <thead><tr><th>Date</th><th>Reçu</th><th>Donateur</th><th>Nature</th><th className="masquer-mobile">Mode</th><th className="num">Montant</th><th /></tr></thead>
            <tbody>{lignes.map((c) => (
              <tr key={c.id} style={c.annulee ? { opacity: 0.55 } : undefined}>
                <td className="chiffre">{dateFr(c.date)}</td>
                <td className="code">{c.numero_recu}{c.annulee && <div><span className="badge critique" title={c.motif_annulation}>Annulé</span></div>}</td>
                <td>{c.membre_nom ? <><div className="principal-cell">{c.membre_nom}</div><div className="secondaire">{c.membre_numero} · {c.paroisse_nom}</div></>
                  : <><div className="muet">Quête anonyme</div><div className="secondaire">{c.paroisse_nom}</div></>}</td>
                <td>{c.type_libelle}</td>
                <td className="masquer-mobile secondaire">{c.mode_libelle}{c.reference ? ` · ${c.reference}` : ""}</td>
                <td className="num chiffre" style={c.annulee ? { textDecoration: "line-through" } : undefined}>{bif(c.montant)}</td>
                <td className="num" style={{ whiteSpace: "nowrap" }}>
                  <button className="icone-bouton" title="Imprimer le reçu" onClick={() => imprimerRecu(c, org)}><Printer size={16} /></button>
                  {c.membre && <button className="icone-bouton" title={`Attestation ${annee} du membre`} disabled={encours === c.id} onClick={() => attestation(c)}>
                    {encours === c.id ? <Loader2 size={16} className="tourne" /> : <FileBadge size={16} />}</button>}
                  {annulation && !c.annulee && <button className="icone-bouton" title="Annuler ce reçu" onClick={() => setAnnuler({ c, motif: "" })}><Ban size={16} /></button>}
                </td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
      </Etat>
      <div className="carte-pied"><Pagination page={page} total={liste.donnees?.count || 0} parPage={50} onChange={setPage} unite="reçus" /></div>
      {annuler && (
        <Modale titre={`Annuler le reçu ${annuler.c.numero_recu} ?`} onFermer={() => setAnnuler(null)}
          description={`${annuler.c.membre_nom || "Quête anonyme"} · ${bif(annuler.c.montant)} · ${dateFr(annuler.c.date)}. La recette est retirée de la comptabilité ; le reçu reste visible, barré.`}
          pied={<><button className="bouton" onClick={() => setAnnuler(null)}>Retour</button>
            <button className="bouton danger" disabled={annuler.motif.trim().length < 5} onClick={confirmerAnnulation}><Ban />Annuler le reçu</button></>}>
          <Champ libelle="Motif (inscrit au journal d'audit)">
            <input value={annuler.motif} onChange={(e) => setAnnuler({ ...annuler, motif: e.target.value })} placeholder="ex. Montant saisi deux fois" autoFocus />
          </Champ>
        </Modale>
      )}
    </Carte>
  );
}

