import { useState } from "react";
import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ArrowDownLeft, ArrowUpRight, CheckCircle2, Download, Landmark, Loader2, Plus, ShieldCheck, Smartphone, TriangleAlert, Wallet } from "lucide-react";
import { api, telecharger } from "../api";
import { useAuth } from "../auth";
import { useCouleurs } from "../theme";
import {
  Bandeau, Carte, Champ, EnTete, Etat, InfoBulle, Kpi, Modale, Pagination, Segments, useApi, useToast, Vide,
} from "../components/ui";
import { bif, COULEURS, date, moisCourt, devise } from "../format";

const CATS = {
  DIME: "Dîmes et offrandes", DON: "Don", SUBVENTION: "Subvention partenaire", REVENU_PROJET: "Revenu de projet",
  SALAIRE: "Salaires", MAINTENANCE: "Maintenance", CONSTRUCTION: "Construction", FONCTIONNEMENT: "Fonctionnement", ACHAT: "Achat de matériel",
};
const ICONE_CANAL = { BANQUE: Landmark, ESPECES: Wallet, MOBILE: Smartphone };
const C_REC = COULEURS[0];
const C_DEP = COULEURS[1];

export default function Finances() {
  const { peut } = useAuth();
  const notifier = useToast();
  const [vue, setVue] = useState("anomalies");
  const [sens, setSens] = useState("");
  const [page, setPage] = useState(1);
  const [ajout, setAjout] = useState(false);
  const [verif, setVerif] = useState(null);
  const synthese = useApi("transactions/synthese/");
  const anomalies = useApi("transactions/?est_anomalie=true&verifiee=false&ordering=-score_anomalie");
  const liste = useApi(`transactions/?page=${page}${sens ? `&sens=${sens}` : ""}`);

  const hist = synthese.donnees?.prevision.historique || [];
  const rec = hist.reduce((s, h) => s + h.recettes, 0);
  const dep = hist.reduce((s, h) => s + h.depenses, 0);

  async function verifier(t) {
    setVerif(t.id);
    try {
      await api(`transactions/${t.id}/verifier/`, { methode: "POST" });
      notifier(`Transaction du ${date(t.date)} marquée comme vérifiée.`);
      anomalies.recharger();
    } catch (e) {
      notifier(e.message, "erreur");
    }
    setVerif(null);
  }

  return (
    <>
      <EnTete titre="Finances" sousTitre="Recettes et dépenses de toutes les institutions de l'Église, contrôlées en continu par la détection d'anomalies.">
        {peut("analyses") && <button className="bouton" onClick={() => telecharger("export/transactions/", "umurage_transactions.csv")}><Download />Exporter pour l'audit</button>}
        {peut("finances") && <button className="bouton principal" onClick={() => setAjout(true)}><Plus />Enregistrer une transaction</button>}
      </EnTete>

      <div className="pile">
        <div className="kpis">
          <Kpi libelle="Recettes" icone={ArrowDownLeft} ton="bon" valeur={bif(rec, true).replace(` ${devise()}`, "")} unite={devise()} note={`Sur ${hist.length} mois`}
            serie={hist.slice(-12).map((h) => h.recettes)} couleurSerie={C_REC} />
          <Kpi libelle="Dépenses" icone={ArrowUpRight} valeur={bif(dep, true).replace(` ${devise()}`, "")} unite={devise()} note={`Sur ${hist.length} mois`}
            serie={hist.slice(-12).map((h) => h.depenses)} couleurSerie={C_DEP} />
          <Kpi libelle="Solde" icone={Wallet} ton={rec >= dep ? "bon" : "critique"} valeur={bif(rec - dep, true).replace(` ${devise()}`, "")} unite={devise()}
            note={rec >= dep ? "Excédent sur la période" : "Déficit sur la période"} />
          <Kpi libelle="À vérifier" icone={TriangleAlert} ton={anomalies.donnees?.count ? "attention" : "bon"} valeur={anomalies.donnees?.count ?? "…"}
            note="Transactions signalées par l'IA" />
        </div>

        <Carte titre="Évolution et prévision sur six mois" description={`Montants mensuels en millions de ${devise()}. La zone claire indique la fourchette probable de la prévision.`}
          actions={<div className="legende">
            <span><i className="pastille" style={{ background: C_REC }} />Recettes</span>
            <span><i className="pastille" style={{ background: C_DEP }} />Dépenses</span>
            <span><i className="trait-legende" />Réel</span>
            <span><i className="trait-legende pointille" />Prévision</span>
          </div>}>
          <Etat chargement={synthese.chargement && !synthese.donnees} erreur={synthese.erreur}>
            {synthese.donnees && <Prevision p={synthese.donnees.prevision} />}
          </Etat>
        </Carte>

        <Carte brut
          titre={vue === "anomalies" ? "Transactions signalées" : "Journal des transactions"}
          description={vue === "anomalies" ? "Chaque signalement est expliqué. C'est une opération à contrôler, pas une accusation." : "Toutes les recettes et dépenses, de la plus récente à la plus ancienne."}
          actions={<Segments label="Vue" valeur={vue} onChange={setVue} options={[
            { id: "anomalies", libelle: "À vérifier", nb: anomalies.donnees?.count },
            { id: "toutes", libelle: "Toutes" },
          ]} />}
          pied={vue === "toutes" && liste.donnees && <Pagination page={page} total={liste.donnees.count} onChange={setPage} unite="transactions" />}
        >
          <div style={{ height: 12 }} />
          {vue === "anomalies" ? (
            <Etat chargement={anomalies.chargement && !anomalies.donnees} erreur={anomalies.erreur}>
              {anomalies.donnees?.results.length === 0 ? (
                <Vide icone={ShieldCheck} titre="Tout est vérifié" texte="Aucune transaction signalée n'attend de contrôle." />
              ) : (
                <div className="defilement">
                  <table className="tableau">
                    <thead><tr><th>Opération</th><th className="num">Montant</th><th>Motifs du signalement</th><th /></tr></thead>
                    <tbody>
                      {anomalies.donnees?.results.map((t) => (
                        <tr key={t.id}>
                          <td style={{ minWidth: 220 }}>
                            <div className="principal-cell">{t.categorie_libelle}, {t.tiers}</div>
                            <div className="secondaire">{date(t.date)}, {t.district_nom}, {t.canal_libelle.toLowerCase()}</div>
                          </td>
                          <td className="num chiffre" style={{ fontWeight: 600 }}>{bif(t.montant_bif)}</td>
                          <td style={{ minWidth: 280 }}>
                            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                              {t.motifs_anomalie.map((m) => (
                                <span key={m} className="petit" style={{ display: "flex", gap: 7, alignItems: "flex-start", color: m.includes("Isolation") ? "var(--encre-3)" : "var(--encre-2)" }}>
                                  <i className="puce" style={{ background: m.includes("Isolation") ? "var(--lac)" : "var(--sorgho)", marginTop: 7 }} />{m}
                                </span>
                              ))}
                            </div>
                          </td>
                          <td className="num">
                            {peut("finances") && (
                              <button className="bouton petit" onClick={() => verifier(t)} disabled={verif === t.id}>
                                {verif === t.id ? <Loader2 className="tourne" /> : <CheckCircle2 />}Vérifiée
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Etat>
          ) : (
            <>
              <div className="barre-filtres" style={{ borderTop: "1px solid var(--trait)" }}>
                <Segments label="Sens" valeur={sens} onChange={(s) => { setSens(s); setPage(1); }}
                  options={[{ id: "", libelle: "Toutes" }, { id: "RECETTE", libelle: "Recettes" }, { id: "DEPENSE", libelle: "Dépenses" }]} />
              </div>
              <Etat chargement={liste.chargement && !liste.donnees} erreur={liste.erreur} lignes={8}>
                <div className="defilement" style={{ opacity: liste.chargement ? 0.6 : 1 }}>
                  <table className="tableau">
                    <thead><tr><th>Date</th><th>Opération</th><th className="masquer-mobile">District</th><th className="masquer-mobile">Canal</th><th className="num">Montant</th></tr></thead>
                    <tbody>
                      {liste.donnees?.results.map((t) => {
                        const Ic = ICONE_CANAL[t.canal];
                        return (
                          <tr key={t.id}>
                            <td style={{ whiteSpace: "nowrap" }}>{date(t.date)}</td>
                            <td>
                              <div className="principal-cell" style={{ display: "flex", gap: 8, alignItems: "center" }}>
                                {t.categorie_libelle}
                                {t.est_anomalie && !t.verifiee && <span className="badge attention">Signalée</span>}
                              </div>
                              <div className="secondaire">{t.tiers}{t.description ? `, ${t.description}` : ""}</div>
                            </td>
                            <td className="masquer-mobile">{t.district_nom}</td>
                            <td className="masquer-mobile"><span style={{ display: "inline-flex", gap: 6, alignItems: "center" }}><Ic size={14} className="muet" />{t.canal_libelle}</span></td>
                            <td className="num chiffre" style={{ fontWeight: 600, color: t.sens === "DEPENSE" ? "var(--encre)" : "var(--marque-texte)" }}>
                              {t.sens === "DEPENSE" ? "−" : "+"}{bif(t.montant_bif)}
                              {t.devise === "USD" && <div className="secondaire">{Number(t.montant).toLocaleString("fr-FR")} USD</div>}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </Etat>
            </>
          )}
        </Carte>
      </div>

      {ajout && (
        <NouvelleTransaction onFermer={() => setAjout(false)}
          onEnregistre={() => { setAjout(false); notifier("Transaction enregistrée."); liste.recharger(); synthese.recharger(); }} />
      )}
    </>
  );
}

function Prevision({ p }) {
  const c = useCouleurs();
  const M = 1e6;
  const hist = p.historique.slice(-18).map((h) => ({ mois: h.mois, recettes: h.recettes / M, depenses: h.depenses / M }));
  const dernier = hist[hist.length - 1];
  const prev = p.prevision.map((x) => ({
    mois: x.mois,
    recettes_prev: x.recettes / M,
    depenses_prev: x.depenses / M,
    bande_rec: [x.recettes_bas / M, x.recettes_haut / M],
    bande_dep: [x.depenses_bas / M, x.depenses_haut / M],
  }));
  // La prévision part du dernier mois réel, pour une ligne continue
  if (dernier) Object.assign(dernier, { recettes_prev: dernier.recettes, depenses_prev: dernier.depenses });
  const data = [...hist, ...prev];
  const f1 = (v) => v.toLocaleString("fr-FR", { maximumFractionDigits: 1 });
  const fmt = (v) => (Array.isArray(v) ? `${f1(v[0])} à ${f1(v[1])} M` : `${f1(v)} M ${devise()}`);
  const filtre = (pl) => (pl.some((x) => x.dataKey === "recettes") ? pl.filter((x) => !String(x.dataKey).endsWith("_prev")) : pl);
  return (
    <ResponsiveContainer width="100%" height={290}>
      <ComposedChart data={data} margin={{ top: 8, right: 8, left: -8 }}>
        <CartesianGrid vertical={false} stroke={c.grille} />
        <XAxis dataKey="mois" tickFormatter={moisCourt} tick={{ fontSize: 12, fill: c.axe }} axisLine={false} tickLine={false} minTickGap={16} />
        <YAxis tick={{ fontSize: 12, fill: c.axe }} axisLine={false} tickLine={false} width={44} />
        <Tooltip cursor={{ stroke: c.axe, strokeDasharray: "3 3" }} content={<InfoBulle format={fmt} titre={(l) => moisCourt(l)} filtre={filtre} />} />
        <Area dataKey="bande_rec" name="Fourchette des recettes" stroke="none" fill={C_REC} fillOpacity={0.14} isAnimationActive={false} />
        <Area dataKey="bande_dep" name="Fourchette des dépenses" stroke="none" fill={C_DEP} fillOpacity={0.14} isAnimationActive={false} />
        <Line dataKey="recettes" name="Recettes" stroke={C_REC} strokeWidth={2} dot={false} activeDot={{ r: 4, stroke: c.surface, strokeWidth: 2 }} isAnimationActive={false} />
        <Line dataKey="depenses" name="Dépenses" stroke={C_DEP} strokeWidth={2} dot={false} activeDot={{ r: 4, stroke: c.surface, strokeWidth: 2 }} isAnimationActive={false} />
        <Line dataKey="recettes_prev" name="Recettes prévues" stroke={C_REC} strokeWidth={2} strokeDasharray="5 4" dot={false} isAnimationActive={false} />
        <Line dataKey="depenses_prev" name="Dépenses prévues" stroke={C_DEP} strokeWidth={2} strokeDasharray="5 4" dot={false} isAnimationActive={false} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

function NouvelleTransaction({ onFermer, onEnregistre }) {
  const { donnees: districts } = useApi("districts/");
  const [f, setF] = useState({
    date: new Date().toISOString().slice(0, 10), sens: "RECETTE", categorie: "DIME", montant: "", devise: devise(),
    canal: "BANQUE", reference_externe: "", district: "", tiers: "", description: "",
  });
  const [erreur, setErreur] = useState("");
  const [encours, setEncours] = useState(false);
  const maj = (k) => (e) => setF({ ...f, [k]: e.target.value });
  async function enregistrer() {
    setEncours(true);
    try {
      await api("transactions/", { methode: "POST", corps: f });
      onEnregistre();
    } catch (e) {
      setErreur(e.message);
    }
    setEncours(false);
  }
  return (
    <Modale titre="Enregistrer une transaction" description={`Les montants en USD sont convertis en ${devise()} au taux de référence. L'IA contrôlera l'opération.`}
      onFermer={onFermer}
      pied={<><button className="bouton" onClick={onFermer}>Annuler</button><button className="bouton principal" onClick={enregistrer} disabled={!f.montant || !f.district || encours}>{encours && <Loader2 className="tourne" />}Enregistrer la transaction</button></>}>
      {erreur && <Bandeau type="erreur" style={{ marginBottom: 14 }}>{erreur}</Bandeau>}
      <div className="formulaire">
        <Champ libelle="Sens">
          <select value={f.sens} onChange={maj("sens")}><option value="RECETTE">Recette</option><option value="DEPENSE">Dépense</option></select>
        </Champ>
        <Champ libelle="Catégorie">
          <select value={f.categorie} onChange={maj("categorie")}>{Object.entries(CATS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
        </Champ>
        <Champ libelle="Montant"><input type="number" min="0" step="any" value={f.montant} onChange={maj("montant")} /></Champ>
        <Champ libelle="Devise">
          <select value={f.devise} onChange={maj("devise")}><option>{devise()}</option><option>USD</option></select>
        </Champ>
        <Champ libelle="Date"><input type="date" value={f.date} onChange={maj("date")} /></Champ>
        <Champ libelle="District">
          <select value={f.district} onChange={maj("district")}><option value="">Choisir…</option>{districts?.map((d) => <option key={d.id} value={d.id}>{d.nom}</option>)}</select>
        </Champ>
        <Champ libelle="Canal">
          <select value={f.canal} onChange={maj("canal")}><option value="BANQUE">Banque</option><option value="ESPECES">Espèces</option><option value="MOBILE">Mobile Money</option></select>
        </Champ>
        <Champ libelle="Référence" aide="Numéro Lumicash, EcoCash ou bancaire.">
          <input value={f.reference_externe} onChange={maj("reference_externe")} />
        </Champ>
        <Champ libelle="Tiers" aide="Donateur ou bénéficiaire." large><input value={f.tiers} onChange={maj("tiers")} /></Champ>
        <Champ libelle="Description" large><input value={f.description} onChange={maj("description")} /></Champ>
      </div>
    </Modale>
  );
}
