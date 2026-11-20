import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import {
  Activity, AlertTriangle, BrainCircuit, CheckCircle2, CircleDashed, FileWarning, HeartPulse, Loader2, Printer,
  Radio, ShieldAlert, Wallet, Wrench, XCircle,
} from "lucide-react";
import { api } from "../api";
import { useAuth } from "../auth";
import { useCouleurs } from "../theme";
import { Carte, EnTete, Etat, InfoBulle, Kpi, Risque, Squelette, useApi, useToast } from "../components/ui";
import { bif, COULEURS, devise, moisCourt, nombre } from "../format";
import { useLangue } from "../i18n";

const ICONE_ACTIVITE = {
  mouvement: [Wrench, "var(--lac-pale)", "var(--lac)"],
  alerte: [Radio, "var(--critique-pale)", "var(--critique)"],
  anomalie: [AlertTriangle, "var(--sorgho-pale)", "var(--sorgho)"],
};

export default function TableauDeBord() {
  const { moi, peut } = useAuth();
  const { t, langue } = useLangue();
  const aujourdhui = new Date().toLocaleDateString(langue === "en" ? "en-GB" : "fr-FR", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
  const dv = devise();
  const c = useCouleurs();
  const notifier = useToast();
  const nav = useNavigate();
  const [district, setDistrict] = useState("");
  const { donnees: d, erreur, chargement, recharger } = useApi(`tableau-de-bord/${district ? `?district=${district}` : ""}`);
  const { donnees: districts } = useApi("districts/");
  const [analyse, setAnalyse] = useState(false);

  async function relancer() {
    setAnalyse(true);
    try {
      const r = await api("ia/analyses/", { methode: "POST" });
      notifier(`Analyses terminées : ${r.valorisation.biens_valorises} biens valorisés, ${r.anomalies.anomalies} anomalies signalées.`);
      recharger();
    } catch (e) {
      notifier(e.message, "erreur");
    }
    setAnalyse(false);
  }

  return (
    <>
      <EnTete
        titre={t("tb.titre")}
        sousTitre={`${moi.voit_tout ? moi.organisation?.nom : moi.district_nom}. ${t("tb.sous", { date: aujourdhui })}`}
      >
        {moi.voit_tout && (
          <select className="saisie-ui" value={district} onChange={(e) => setDistrict(e.target.value)} aria-label="District">
            <option value="">{t("tb.tous_districts")}</option>
            {districts?.map((x) => <option key={x.id} value={x.id}>{x.nom}</option>)}
          </select>
        )}
        <Link className="bouton" to="/rapport"><Printer />{t("tb.rapport")}</Link>
        {peut("analyses") && (
          <button className="bouton principal" onClick={relancer} disabled={analyse}>
            {analyse ? <Loader2 className="tourne" /> : <BrainCircuit />}
            {analyse ? t("tb.analyse") : t("tb.relancer")}
          </button>
        )}
      </EnTete>

      {erreur && <Etat erreur={erreur} />}
      {!d ? (
        <div className="pile">
          <div className="squelette" style={{ height: 230, borderRadius: 18 }} />
          <div className="kpis">{[0, 1, 2, 3].map((i) => <div key={i} className="squelette" style={{ height: 128, borderRadius: 14 }} />)}</div>
          <Squelette lignes={5} hauteur={22} />
        </div>
      ) : (
        <div className="pile" style={{ opacity: chargement ? 0.6 : 1, transition: "opacity .2s" }}>
          <Heros d={d} />

          <div className="kpis">
            <Kpi libelle={t("tb.k_titre")} icone={FileWarning} ton={d.kpi.sans_titre ? "critique" : "bon"}
              valeur={d.kpi.sans_titre} unite={`/ ${d.kpi.terrains}`} note={d.kpi.sans_titre ? t("tb.k_titre_n") : t("tb.k_titre_ok")}
              noteTon={d.kpi.sans_titre ? "critique" : ""} lien="/biens?categorie=FON" />
            <Kpi libelle={t("tb.k_risque")} icone={ShieldAlert} ton={d.kpi.risque_eleve ? "attention" : "bon"}
              valeur={d.kpi.risque_eleve} note={t("tb.k_risque_n")} lien="/biens?tri=-score_risque" />
            <Kpi libelle={t("tb.k_alertes")} icone={Radio} ton={d.kpi.alertes ? "critique" : "bon"}
              valeur={d.kpi.alertes} note={d.kpi.alertes ? t("tb.k_alertes_n") : t("tb.k_alertes_ok")}
              noteTon={d.kpi.alertes ? "critique" : ""} lien="/capteurs" />
            <Kpi libelle={t("tb.k_anomalies")} icone={Wallet} ton={d.kpi.anomalies ? "attention" : "bon"}
              valeur={d.kpi.anomalies} note={t("tb.k_anomalies_n")} lien="/finances" />
          </div>

          <div className="grille g-2-1">
            <Carte titre={t("tb.finances")} description={t("tb.finances_sous", { devise: dv })}
              actions={<div className="legende">
                <span><i className="pastille" style={{ background: COULEURS[0] }} />{t("tb.recettes")}</span>
                <span><i className="pastille" style={{ background: COULEURS[1] }} />{t("tb.depenses")}</span>
              </div>}>
              <div className="kpis" style={{ gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 0, marginBottom: 8 }}>
                {[[t("tb.recettes_cum"), d.kpi.recettes], [t("tb.depenses_cum"), d.kpi.depenses], [t("tb.solde"), d.kpi.recettes - d.kpi.depenses]].map(([l, v], i) => (
                  <div key={l} style={{ paddingLeft: i ? 16 : 0, borderLeft: i ? "1px solid var(--trait)" : 0 }}>
                    <div className="petit muet">{l}</div>
                    <div className="chiffre" style={{ fontFamily: "var(--titre)", fontSize: "1.25rem", fontWeight: 700 }}>{bif(v, true)}</div>
                  </div>
                ))}
              </div>
              <ResponsiveContainer width="100%" height={290}>
                <AreaChart data={d.tendance.map((t) => ({ mois: t.mois, recettes: t.recettes / 1e6, depenses: t.depenses / 1e6 }))} margin={{ top: 8, right: 6, left: -12, bottom: 0 }}>
                  <defs>
                    {[0, 1].map((i) => (
                      <linearGradient key={i} id={`deg${i}`} x1="0" x2="0" y1="0" y2="1">
                        <stop offset="0" stopColor={COULEURS[i]} stopOpacity={0.22} />
                        <stop offset="1" stopColor={COULEURS[i]} stopOpacity={0} />
                      </linearGradient>
                    ))}
                  </defs>
                  <CartesianGrid vertical={false} stroke={c.grille} />
                  <XAxis dataKey="mois" tickFormatter={moisCourt} tick={{ fontSize: 12, fill: c.axe }} axisLine={false} tickLine={false} minTickGap={20} />
                  <YAxis tick={{ fontSize: 12, fill: c.axe }} axisLine={false} tickLine={false} width={44} />
                  <Tooltip cursor={{ stroke: c.axe, strokeDasharray: "3 3" }} content={<InfoBulle titre={(l) => moisCourt(l)} format={(v) => `${v.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} M ${dv}`} />} />
                  <Area dataKey="recettes" name={t("tb.recettes")} stroke={COULEURS[0]} strokeWidth={2} fill="url(#deg0)" activeDot={{ r: 4, strokeWidth: 2, stroke: c.surface }} />
                  <Area dataKey="depenses" name={t("tb.depenses")} stroke={COULEURS[1]} strokeWidth={2} fill="url(#deg1)" activeDot={{ r: 4, strokeWidth: 2, stroke: c.surface }} />
                </AreaChart>
              </ResponsiveContainer>
              {d.tendance_mois_incomplets?.length > 0 && (
                <p className="secondaire" style={{ marginTop: 6 }}>{t("tb.mois_incomplet", { mois: d.tendance_mois_incomplets.map(moisCourt).join(", ") })}</p>
              )}
            </Carte>

            <Carte titre={t("tb.activite")} description={t("tb.activite_sous")} plein>
              <ul className="fil-activite">
                {d.activite.slice(0, 5).map((a, i) => {
                  const [Ic, fond, coul] = ICONE_ACTIVITE[a.type];
                  return (
                    <li key={i}>
                      <span className="icone" style={{ background: fond, color: coul }}><Ic /></span>
                      <Link to={a.lien}>
                        <div className="titre">{a.titre}</div>
                        <div className="meta">{new Date(a.date).toLocaleDateString("fr-FR", { day: "numeric", month: "short", year: "numeric" })}{a.detail ? `, ${a.detail}` : ""}</div>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </Carte>
          </div>

          <div className="grille g2">
            <Carte titre={t("tb.par_type")} description={t("tb.par_type_sous", { devise: dv })}>
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={d.par_categorie} layout="vertical" margin={{ left: 0, right: 16 }} barCategoryGap={8}>
                  <CartesianGrid horizontal={false} stroke={c.grille} />
                  <XAxis type="number" tickFormatter={(v) => nombre(v / 1e6)} tick={{ fontSize: 12, fill: c.axe }} axisLine={false} tickLine={false} />
                  <YAxis type="category" dataKey="categorie" width={186} tick={{ fontSize: 12, fill: c.texte }} axisLine={false} tickLine={false} />
                  <Tooltip cursor={{ fill: c.curseur }} content={<InfoBulle format={(v) => bif(v)} />} />
                  <Bar dataKey="valeur" name="Valeur estimée" fill={COULEURS[0]} radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </Carte>

            <Carte titre={t("tb.par_district")} plein>
              <div className="defilement">
                <table className="tableau">
                  <thead>
                    <tr><th>{t("tb.district")}</th><th className="num">{t("tb.biens")}</th><th className="num">{t("tb.valeur_col")}</th><th className="num">{t("tb.a_risque")}</th><th className="num">{t("tb.sans_titre")}</th></tr>
                  </thead>
                  <tbody>
                    {d.par_district.map((x, i) => (
                      <tr key={x.district}>
                        <td className="principal-cell"><span style={{ display: "inline-flex", gap: 8, alignItems: "center" }}><i className="pastille" style={{ background: COULEURS[i % COULEURS.length] }} />{x.district}</span></td>
                        <td className="num">{x.nombre}</td>
                        <td className="num">{bif(x.valeur, true)}</td>
                        <td className="num">{x.a_risque ? <span className="badge attention">{x.a_risque}</span> : <span className="muet">0</span>}</td>
                        <td className="num">{x.sans_titre ? <span className="badge critique">{x.sans_titre}</span> : <span className="muet">0</span>}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Carte>
          </div>

          <div className="grille g-3-2">
            <Carte titre={t("tb.intervention")} description={t("tb.intervention_sous")} plein
              pied={<><span>{t("tb.au_dessus", { n: d.kpi.risque_eleve })}</span><Link to="/biens?tri=-score_risque">{t("tb.voir_inventaire")}</Link></>}>
              <table className="tableau">
                <tbody>
                  {d.biens_a_risque.map((b) => (
                    <tr key={b.id} className="cliquable" onClick={() => nav(`/biens/${b.id}`)}>
                      <td>
                        <div className="principal-cell">{b.nom}</div>
                        <div className="secondaire">{b.code}, {b.district_nom}</div>
                      </td>
                      <td className="masquer-mobile">{b.sous_type}</td>
                      <td className="num"><Risque score={b.score_risque} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Carte>

            <div className="pile">
              <Carte titre={t("tb.sante")} description={t("tb.sante_sous")} plein>
                <table className="tableau">
                  <tbody>
                    {d.objectif_sante_2030.map((o) => (
                      <tr key={o.district}>
                        <td className="principal-cell"><HeartPulse size={15} style={{ display: "inline", verticalAlign: -2, marginRight: 8, color: "var(--encre-3)" }} />{o.district}</td>
                        <td className="num">
                          {o.operationnels > 0 ? <span className="badge bon"><CheckCircle2 />{t("tb.atteint")}</span>
                            : o.en_construction ? <span className="badge info"><CircleDashed />{t("tb.construction")}</span>
                              : <span className="badge critique"><XCircle />{t("tb.planifier")}</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Carte>
              <Carte titre={t("tb.odd")} plein>
                <table className="tableau compact">
                  <thead><tr><th>{t("tb.objectif")}</th><th className="num">{t("pt.benef")}</th></tr></thead>
                  <tbody>
                    {d.impact_odd.map((o) => (
                      <tr key={o.odd}>
                        <td>{o.libelle}<div className="secondaire">{t("tb.projets_biens", { p: o.projets, b: o.biens })}</div></td>
                        <td className="num chiffre">{nombre(o.beneficiaires)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Carte>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function Heros({ d }) {
  const { t } = useLangue();
  const dv = devise();
  const total = d.kpi.valeur_totale || 1;
  const enMilliards = d.kpi.valeur_totale >= 1e9;
  const [survol, setSurvol] = useState(null);
  const titres = d.kpi.terrains ? Math.round((100 * (d.kpi.terrains - d.kpi.sans_titre)) / d.kpi.terrains) : 100;
  return (
    <section className="heros" aria-label="Valeur du patrimoine">
      <div>
        <div className="heros-etiquette"><Activity size={16} />{t("tb.valeur")}</div>
        <div className="heros-montant">
          {(d.kpi.valeur_totale / (enMilliards ? 1e9 : 1e6)).toLocaleString("fr-FR", { minimumFractionDigits: enMilliards ? 2 : 0, maximumFractionDigits: enMilliards ? 2 : 0 })}
          <small>{t(enMilliards ? "tb.milliards" : "tb.millions", { devise: dv })}</small>
        </div>
        <p className="heros-phrase">
          {survol
            ? `${survol.district} : ${bif(survol.valeur, true)} pour ${survol.nombre} biens, soit ${Math.round((100 * survol.valeur) / total)} % du total.`
            : t("tb.phrase", { n: nombre(d.kpi.nb_biens) })}
        </p>
      </div>
      <div className="heros-cote">
        <div><b>{nombre(d.kpi.nb_biens)}</b><span>{t("tb.biens_recenses")}</span></div>
        <div><b>{titres} %</b><span>{t("tb.terrains_titres")}</span></div>
        <div><b>{nombre(d.kpi.beneficiaires)}</b><span>{t("tb.beneficiaires")}</span></div>
      </div>
      {d.par_district.length > 1 && (
        <>
          <div className="bande" role="group" aria-label="Répartition de la valeur par district">
            {d.par_district.map((x, i) => (
              <button
                key={x.district}
                style={{ flexGrow: x.valeur, background: COULEURS[i % COULEURS.length], opacity: survol && survol.district !== x.district ? 0.35 : 1 }}
                onMouseEnter={() => setSurvol(x)} onMouseLeave={() => setSurvol(null)}
                onFocus={() => setSurvol(x)} onBlur={() => setSurvol(null)}
                aria-label={`${x.district} : ${bif(x.valeur)}`}
              />
            ))}
          </div>
          <div className="bande-legende">
            {d.par_district.map((x, i) => (
              <span key={x.district}>
                <i className="pastille" style={{ background: COULEURS[i % COULEURS.length] }} />
                {x.district} <b>{Math.round((100 * x.valeur) / total)} %</b>
              </span>
            ))}
          </div>
        </>
      )}
    </section>
  );
}
