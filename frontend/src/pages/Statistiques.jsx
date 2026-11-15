import { useMemo, useState } from "react";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, LabelList, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import {
  ArrowDownRight, ArrowUpRight, Building2, CalendarClock, Church, Droplets, Gavel, IdCard, KeyRound, Minus, Printer, Users, Wallet, Wrench,
} from "lucide-react";
import { useAuth } from "../auth";
import { Carte, EnTete, Etat, InfoBulle, useApi } from "../components/ui";
import { bif, COULEURS, moisCourt, nombre } from "../format";
import { useCouleurs } from "../theme";

// Couleurs fixes par entité (jamais par rang) : palette validée (daltonisme, contraste)
const C_STATUT = { CONFESSANT: COULEURS[0], BAPTISE: COULEURS[3], CATECHUMENE: COULEURS[2], SYMPATHISANT: COULEURS[1], TRANSFERE: "#8b9690", DECEDE: "#5d6862" };
const C_CAT = { FON: COULEURS[0], IMM: COULEURS[1], INF: COULEURS[2], EQP: COULEURS[3], VEH: COULEURS[4], AGR: COULEURS[5] };
const C_ETAT = { BON: "#1e8a57", MOYEN: "#c98a12", MAUVAIS: "#c0392b", CONSTRUCTION: "#2766b0" };
const FEMMES = COULEURS[1];
const HOMMES = COULEURS[3];

// Libellé court pour les étiquettes de barres (l'unité est dans le titre)
const court = (v) => (v == null ? "—" : Math.abs(v) >= 1e9 ? `${(v / 1e9).toLocaleString("fr-FR", { maximumFractionDigits: 2 })} Md`
  : Math.abs(v) >= 1e6 ? `${(v / 1e6).toLocaleString("fr-FR", { maximumFractionDigits: 1 })} M` : nombre(Math.round(v)));
const fmt = (v, unite) => (unite === "monnaie" ? bif(v, true) : nombre(v));
const pct = (v) => (v == null ? "—" : `${v.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} %`);

export default function Statistiques() {
  const { moi } = useAuth();
  const c = useCouleurs();
  const [district, setDistrict] = useState("");
  const voitTout = ["ADMIN", "EVEQUE", "TRESORIER"].includes(moi?.role);
  const { donnees: districts } = useApi(voitTout ? "districts/" : null);
  const { donnees: d, erreur, chargement } = useApi(`statistiques-eglise/${district ? `?district=${district}` : ""}`, [district]);
  const listeDistricts = Array.isArray(districts) ? districts : districts?.results || [];

  return (
    <>
      <EnTete titre="Statistiques de l'Église"
        sousTitre="Les chiffres clés en un coup d'œil : membres, comparaison avec l'an dernier à la même date, districts côte à côte, patrimoine et finances.">
        {voitTout && (
          <select className="saisie-ui" value={district} onChange={(e) => setDistrict(e.target.value)} aria-label="District">
            <option value="">Toute l'Église</option>
            {listeDistricts.map((x) => <option key={x.id} value={x.id}>{x.nom}</option>)}
          </select>
        )}
        <button className="bouton" onClick={() => window.print()}><Printer />Imprimer</button>
      </EnTete>

      <Etat chargement={chargement && !d} erreur={erreur}>
        {d && (
          <div className="pile">
            <SalleControle d={d} />
            <BandeFinanciere d={d} />
            <div className="grille g2">
              <Croissance d={d} c={c} />
              <FinancesMois d={d} c={c} />
            </div>
            <Projections d={d} />
            <AnneeComparee d={d} />
            <div className="grille g2">
              <Repartition titre="D'où viennent les recettes" lignes={d.repartition.recettes} couleur={COULEURS[0]} annee={d.annee} />
              <Repartition titre="Où vont les dépenses" lignes={d.repartition.depenses} couleur={COULEURS[4]} annee={d.annee} />
            </div>
            {d.districts.length > 1 && <Districts d={d} c={c} />}
            <MatriceEglises d={d} />
            <TableauMensuel d={d} />
            <div className="grille g3">
              <Statuts d={d} />
              <Ages d={d} c={c} />
              <Ministeres d={d} c={c} />
            </div>
            <div className="grille g2">
              <Patrimoine d={d} />
              <Etats d={d} />
            </div>
          </div>
        )}
      </Etat>
    </>
  );
}

/* ------------------------------------------------------------------ 1. Salle de contrôle (bandeau sombre) */
function SalleControle({ d }) {
  const m = d.membres;
  const serie = m.croissance.map((x) => ({ mois: x.mois, total: x.total }));
  const t = d.a_traiter;
  const urgent = t.echeances_retard + t.travaux_urgents > 0;
  return (
    <section className="salle-controle" aria-label="Indicateurs principaux">
      <div className="sc-tuiles">
        <Tuile icone={Users} libelle="Membres actifs" valeur={nombre(m.actifs)} note={`${nombre(m.femmes)} femmes · ${nombre(m.hommes)} hommes`}>
          <ResponsiveContainer width="100%" height={42}>
            <AreaChart data={serie} margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
              <defs><linearGradient id="sc-g" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="#4fd1a1" stopOpacity=".55" /><stop offset="100%" stopColor="#4fd1a1" stopOpacity="0" /></linearGradient></defs>
              <Area type="monotone" dataKey="total" stroke="#4fd1a1" strokeWidth={2} fill="url(#sc-g)" isAnimationActive={false} />
            </AreaChart>
          </ResponsiveContainer>
        </Tuile>
        <Tuile icone={Droplets} libelle="Baptisés et confessants" valeur={nombre(m.baptises)} note={m.actifs ? `${Math.round((100 * m.baptises) / m.actifs)} % des membres actifs` : "—"} />
        <Tuile icone={Church} libelle="Églises locales" valeur={nombre(m.eglises)} note={`${nombre(m.declares)} membres déclarés`} />
        <Tuile icone={IdCard} libelle="Taux d'enregistrement" valeur={pct(m.taux_enregistrement)} note="fiches officielles / effectif déclaré">
          <div className="sc-jauge"><span style={{ width: `${Math.min(100, Math.max(2, m.taux_enregistrement || 0))}%` }} /></div>
        </Tuile>
        <Tuile icone={Building2} libelle="Valeur du patrimoine" valeur={bif(d.patrimoine.valeur, true)} note={`${nombre(d.patrimoine.total)} biens recensés`} />
      </div>
      <div className={`sc-attente${urgent ? " urgent" : ""}`}>
        <div className="sc-attente-tete"><span className={`point ${urgent ? "v-urgence" : "v-attention"}`} />Dossiers en attente</div>
        <div className="sc-gros">{t.total}</div>
        <ul>
          <li><Gavel size={14} />{t.demandes} demande(s) d'approbation</li>
          <li><CalendarClock size={14} />{t.echeances_30j} échéance(s) sous 30 jours{t.echeances_retard ? <b> · {t.echeances_retard} en retard</b> : null}</li>
          <li><Wrench size={14} />{t.travaux} travaux ouverts{t.travaux_urgents ? <b> · {t.travaux_urgents} urgent(s)</b> : null}</li>
          <li><KeyRound size={14} />{t.loyers_impayes} loyer(s) impayé(s){t.montant_impayes ? ` · ${bif(t.montant_impayes, true)}` : ""}</li>
        </ul>
      </div>
    </section>
  );
}

function Tuile({ icone: Ic, libelle, valeur, note, children }) {
  return (
    <div className="sc-tuile">
      <div className="sc-tuile-tete"><span>{libelle}</span><Ic size={16} /></div>
      <div className="sc-valeur">{valeur}</div>
      {children}
      <div className="sc-note">{note}</div>
    </div>
  );
}

/* ------------------------------------------------------------------ 2. Croissance et finances */
function Croissance({ d, c }) {
  const data = d.membres.croissance;
  const total12 = data.reduce((s, x) => s + x.nouveaux, 0);
  return (
    <Carte titre="Nouveaux membres par mois" description={`${nombre(total12)} adhésions sur les 12 derniers mois (date d'adhésion).`}>
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={data} margin={{ top: 18, right: 4, left: -18, bottom: 0 }} barCategoryGap="28%">
          <CartesianGrid vertical={false} stroke={c.grille} />
          <XAxis dataKey="mois" tickFormatter={moisCourt} tick={{ fontSize: 12, fill: c.axe }} axisLine={false} tickLine={false} />
          <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: c.axe }} axisLine={false} tickLine={false} width={40} />
          <Tooltip cursor={{ fill: c.curseur }} content={<InfoBulle titre={(l) => moisCourt(l)} format={(v) => `${nombre(v)} membre(s)`} />} />
          <Bar dataKey="nouveaux" name="Nouveaux membres" fill={COULEURS[0]} radius={[4, 4, 0, 0]}>
            <LabelList dataKey="nouveaux" position="top" fontSize={11} fill={c.texte} formatter={(v) => (v ? v : "")} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </Carte>
  );
}

function FinancesMois({ d, c }) {
  const data = d.finances.map((x) => ({ ...x, recettes: x.recettes / 1e6, depenses: x.depenses / 1e6 }));
  const r = d.finances.reduce((s, x) => s + x.recettes, 0);
  const dp = d.finances.reduce((s, x) => s + x.depenses, 0);
  return (
    <Carte titre="Recettes et dépenses" description={`12 derniers mois, en millions (le mois en cours n'est pas terminé). Solde : ${bif(r - dp, true)}.`}
      actions={<div className="legende"><span><i className="pastille" style={{ background: COULEURS[0] }} />Recettes</span><span><i className="pastille" style={{ background: COULEURS[4] }} />Dépenses</span></div>}>
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={data} margin={{ top: 10, right: 8, left: -12, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke={c.grille} />
          <XAxis dataKey="mois" tickFormatter={moisCourt} tick={{ fontSize: 12, fill: c.axe }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fontSize: 12, fill: c.axe }} axisLine={false} tickLine={false} width={44} />
          <Tooltip cursor={{ stroke: c.axe, strokeDasharray: "3 3" }} content={<InfoBulle titre={(l) => moisCourt(l)} format={(v) => `${v.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} M`} />} />
          <Line type="monotone" dataKey="recettes" name="Recettes" stroke={COULEURS[0]} strokeWidth={2} dot={false} activeDot={{ r: 5, strokeWidth: 2, stroke: c.surface }} />
          <Line type="monotone" dataKey="depenses" name="Dépenses" stroke={COULEURS[4]} strokeWidth={2} dot={false} activeDot={{ r: 5, strokeWidth: 2, stroke: c.surface }} />
        </LineChart>
      </ResponsiveContainer>
    </Carte>
  );
}

/* ------------------------------------------------------------------ 3. Cette année / l'an dernier */
function AnneeComparee({ d }) {
  const date = new Date(d.date);
  const jour = date.toLocaleDateString("fr-FR", { day: "numeric", month: "long" });
  return (
    <Carte brut titre={`${d.annee} comparé à ${d.annee - 1}`}
      description={`Du 1er janvier au ${jour} de chaque année : on compare des périodes de même durée. En vert ce qui s'améliore, en rouge ce qui se dégrade.`}>
      <div className="comparaison-annee">
        <div className="ca-entete"><span>Indicateur</span><span className="num">{d.annee - 1}</span><span className="num">{d.annee}</span><span>Comparaison</span><span className="num">Évolution</span></div>
        {d.annee_comparee.map((x) => {
          const max = Math.max(Math.abs(x.actuel), Math.abs(x.precedent), 1);
          const mieux = x.ecart === 0 ? null : (x.ecart > 0) === (x.sens > 0);
          const ton = mieux === null ? "" : mieux ? "bon" : "critique";
          const Fl = x.ecart > 0 ? ArrowUpRight : x.ecart < 0 ? ArrowDownRight : Minus;
          return (
            <div className="ca-ligne" key={x.cle}>
              <span className="ca-lib">{x.libelle}</span>
              <span className="num chiffre muet">{fmt(x.precedent, x.unite)}</span>
              <span className="num chiffre"><b>{fmt(x.actuel, x.unite)}</b></span>
              <span className="ca-barres" aria-hidden="true">
                <i className="prec" style={{ width: `${(100 * Math.abs(x.precedent)) / max}%` }} />
                <i className={`act ${x.actuel < 0 ? "neg" : ""}`} style={{ width: `${(100 * Math.abs(x.actuel)) / max}%` }} />
              </span>
              <span className="num">
                <span className={`evolution ${ton}`}>
                  <Fl size={14} />
                  {x.evolution != null ? `${x.evolution > 0 ? "+" : ""}${x.evolution.toLocaleString("fr-FR")} %` : `${x.ecart > 0 ? "+" : ""}${fmt(x.ecart, x.unite)}`}
                </span>
              </span>
            </div>
          );
        })}
        <div className="ca-legende"><span><i className="prec" />{d.annee - 1}</span><span><i className="act" />{d.annee}</span></div>
      </div>
    </Carte>
  );
}

/* ------------------------------------------------------------------ 4. Districts côte à côte (petits multiples) */
const MESURES = [
  { cle: "membres_inscrits", titre: "Membres enregistrés", f: (v) => nombre(v) },
  { cle: "valeur", titre: "Valeur du patrimoine (BIF)", f: court },
  { cle: "recettes", titre: "Recettes de l'année (BIF)", f: court },
  { cle: "dimes_par_membre", titre: "Dîmes par membre déclaré (BIF)", f: court },
];

function Districts({ d, c }) {
  const [vue, setVue] = useState("graphes");
  const meilleurs = useMemo(() => {
    const cles = ["membres_declares", "membres_inscrits", "taux_enregistrement", "biens", "valeur", "recettes", "solde", "dimes_par_membre"];
    return Object.fromEntries(cles.map((k) => {
      const v = d.districts.map((x) => x[k]).filter((x) => x != null);
      return [k, { max: Math.max(...v), min: Math.min(...v) }];
    }));
  }, [d]);
  const ton = (k, v) => (v == null || meilleurs[k].max === meilleurs[k].min ? "" : v === meilleurs[k].max ? "bon" : v === meilleurs[k].min ? "critique" : "");
  return (
    <Carte brut titre="Les districts comparés" description="Chaque graphique est trié du plus grand au plus petit. Le premier de chaque mesure est mis en valeur."
      actions={
        <div className="segments" role="tablist">
          <button role="tab" aria-selected={vue === "graphes"} onClick={() => setVue("graphes")}>Graphiques</button>
          <button role="tab" aria-selected={vue === "tableau"} onClick={() => setVue("tableau")}>Tableau</button>
        </div>
      }>
      {vue === "graphes" ? (
        <div className="multiples">
          {MESURES.map((m) => {
            const data = [...d.districts].filter((x) => x[m.cle] != null).sort((a, b) => b[m.cle] - a[m.cle]);
            return (
              <div className="multiple" key={m.cle}>
                <h3>{m.titre}</h3>
                <ResponsiveContainer width="100%" height={36 * data.length + 10}>
                  <BarChart data={data} layout="vertical" margin={{ top: 0, right: 58, left: 0, bottom: 0 }} barCategoryGap={8}>
                    <XAxis type="number" hide domain={[0, "dataMax"]} />
                    <YAxis type="category" dataKey="nom" width={92} tick={{ fontSize: 12, fill: c.texte }} axisLine={false} tickLine={false} />
                    <Tooltip cursor={{ fill: c.curseur }} content={<InfoBulle format={m.f} />} />
                    <Bar dataKey={m.cle} name={m.titre} radius={[0, 4, 4, 0]} isAnimationActive={false}>
                      {data.map((x, i) => <Cell key={x.id} fill={i === 0 ? COULEURS[0] : "#9fb8aa"} />)}
                      <LabelList dataKey={m.cle} position="right" fontSize={12} fill={c.texte} formatter={m.f} />
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="defilement"><table className="tableau">
          <thead><tr><th>District</th><th className="num">Églises</th><th className="num">Membres déclarés</th><th className="num">Enregistrés</th>
            <th className="num">Taux</th><th className="num">Biens</th><th className="num">Valeur</th><th className="num">Recettes</th><th className="num">Solde</th><th className="num">Dîmes / membre</th></tr></thead>
          <tbody>{d.districts.map((x) => (
            <tr key={x.id}>
              <td className="principal-cell">{x.nom}</td>
              <td className="num chiffre">{x.eglises}</td>
              {[["membres_declares", nombre], ["membres_inscrits", nombre], ["taux_enregistrement", pct], ["biens", nombre], ["valeur", (v) => bif(v, true)],
                ["recettes", (v) => bif(v, true)], ["solde", (v) => bif(v, true)], ["dimes_par_membre", (v) => bif(v, true)]].map(([k, f]) => {
                const t = ton(k, x[k]);
                return <td key={k} className="num chiffre">{t ? <span className={`badge ${t}`}>{f(x[k])}</span> : f(x[k])}</td>;
              })}
            </tr>
          ))}</tbody>
        </table></div>
      )}
    </Carte>
  );
}

/* ------------------------------------------------------------------ 5. Membres : statuts, âges, ministères */
function Anneau({ data, couleurs, centre, sousCentre, format = nombre, vertical }) {
  const total = data.reduce((s, x) => s + x.n, 0);
  return (
    <div className={`anneau${vertical ? " vertical" : ""}`}>
      <div className="anneau-graphe">
        <ResponsiveContainer width="100%" height={190}>
          <PieChart>
            <Pie data={data.filter((x) => x.n > 0)} dataKey="n" nameKey="libelle" innerRadius={58} outerRadius={84} paddingAngle={1.5} stroke="var(--surface)" strokeWidth={2} isAnimationActive={false}>
              {data.filter((x) => x.n > 0).map((x) => <Cell key={x.cle} fill={couleurs[x.cle]} />)}
            </Pie>
            <Tooltip content={<InfoBulle format={(v) => `${format(v)} (${total ? Math.round((100 * v) / total) : 0} %)`} />} />
          </PieChart>
        </ResponsiveContainer>
        <div className="anneau-centre"><b>{centre}</b><span>{sousCentre}</span></div>
      </div>
      <ul className="anneau-legende">
        {data.map((x) => (
          <li key={x.cle}><i style={{ background: couleurs[x.cle] }} /><span>{x.libelle}</span><b>{format(x.n)}</b><small>{total ? Math.round((100 * x.n) / total) : 0} %</small></li>
        ))}
      </ul>
    </div>
  );
}

function Statuts({ d }) {
  return (
    <Carte titre="Membres par statut" description="Toutes les fiches du registre.">
      <Anneau vertical data={d.membres.par_statut} couleurs={C_STATUT} centre={nombre(d.membres.inscrits)} sousCentre="fiches" />
    </Carte>
  );
}

function Ages({ d, c }) {
  const data = d.membres.ages.map((x) => ({ ...x, femmes_g: -x.femmes }));
  const max = Math.max(1, ...d.membres.ages.map((x) => Math.max(x.femmes, x.hommes)));
  return (
    <Carte titre="Pyramide des âges" description={`Membres actifs.${d.membres.sans_age ? ` ${d.membres.sans_age} sans date de naissance.` : ""}`}
      actions={<div className="legende"><span><i className="pastille" style={{ background: FEMMES }} />Femmes</span><span><i className="pastille" style={{ background: HOMMES }} />Hommes</span></div>}>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} layout="vertical" stackOffset="sign" margin={{ top: 4, right: 26, left: 26, bottom: 0 }} barCategoryGap={6}>
          <CartesianGrid horizontal={false} stroke={c.grille} />
          <XAxis type="number" domain={[-max, max]} ticks={[-max, -Math.round(max / 2), 0, Math.round(max / 2), max]} tickFormatter={(v) => Math.abs(v)} tick={{ fontSize: 11, fill: c.axe }} axisLine={false} tickLine={false} allowDecimals={false} />
          <YAxis type="category" dataKey="tranche" width={78} tick={{ fontSize: 12, fill: c.texte }} axisLine={false} tickLine={false} />
          <Tooltip cursor={{ fill: c.curseur }} content={<InfoBulle format={(v) => `${Math.abs(v)} membre(s)`} />} />
          <Bar dataKey="femmes_g" name="Femmes" stackId="a" fill={FEMMES} radius={[4, 0, 0, 4]}>
            <LabelList dataKey="femmes" position="left" fontSize={11} fill={c.texte} formatter={(v) => (v ? v : "")} />
          </Bar>
          <Bar dataKey="hommes" name="Hommes" stackId="a" fill={HOMMES} radius={[0, 4, 4, 0]}>
            <LabelList dataKey="hommes" position="right" fontSize={11} fill={c.texte} formatter={(v) => (v ? v : "")} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </Carte>
  );
}

function Ministeres({ d, c }) {
  const data = d.membres.ministeres;
  return (
    <Carte titre="Engagement dans les ministères" description="Membres actifs par groupe.">
      {data.length === 0 ? <p className="muet petit">Aucun ministère renseigné.</p> : (
        <ResponsiveContainer width="100%" height={34 * data.length + 10}>
          <BarChart data={data} layout="vertical" margin={{ top: 0, right: 34, left: 0, bottom: 0 }} barCategoryGap={8}>
            <XAxis type="number" hide />
            <YAxis type="category" dataKey="ministere" width={140} tick={{ fontSize: 12, fill: c.texte }} axisLine={false} tickLine={false} />
            <Tooltip cursor={{ fill: c.curseur }} content={<InfoBulle format={(v) => `${v} membre(s)`} />} />
            <Bar dataKey="n" name="Membres" fill={COULEURS[3]} radius={[0, 4, 4, 0]} isAnimationActive={false}>
              <LabelList dataKey="n" position="right" fontSize={12} fill={c.texte} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </Carte>
  );
}

/* ------------------------------------------------------------------ 6. Patrimoine */
function Patrimoine({ d }) {
  const data = d.patrimoine.categories.map((x) => ({ ...x, n: x.valeur }));
  return (
    <Carte titre="Patrimoine par catégorie" description="Part de la valeur estimée.">
      <Anneau data={data} couleurs={C_CAT} centre={bif(d.patrimoine.valeur, true)} sousCentre="valeur totale" format={(v) => bif(v, true)} />
    </Carte>
  );
}

function Etats({ d }) {
  const total = d.patrimoine.etats.reduce((s, x) => s + x.n, 0) || 1;
  return (
    <Carte titre="État des biens" description="Nombre de biens actifs par état constaté.">
      <div className="etats-barres">
        <div className="etats-piste">
          {d.patrimoine.etats.filter((x) => x.n).map((x) => (
            <span key={x.cle} style={{ width: `${(100 * x.n) / total}%`, background: C_ETAT[x.cle] }} title={`${x.libelle} : ${x.n}`} />
          ))}
        </div>
        <ul>
          {d.patrimoine.etats.map((x) => (
            <li key={x.cle}>
              <span className={`badge ${{ BON: "bon", MOYEN: "attention", MAUVAIS: "critique", CONSTRUCTION: "info" }[x.cle]}`}>{x.libelle}</span>
              <b className="chiffre">{nombre(x.n)}</b><small className="muet">{Math.round((100 * x.n) / total)} %</small>
            </li>
          ))}
        </ul>
        <p className="petit muet" style={{ display: "flex", gap: 6, alignItems: "center" }}><Wallet size={14} />Les biens en mauvais état apparaissent aussi dans Maintenance, avec leur ordre de travail.</p>
      </div>
    </Carte>
  );
}

/* ------------------------------------------------------------------ Bande financière : cartes chiffrées avec mini-courbe */
const CARTES_FIN = [
  { cle: "recettes", libelle: "Recettes", couleur: COULEURS[0], sens: 1 },
  { cle: "depenses", libelle: "Dépenses", couleur: COULEURS[4], sens: -1 },
  { cle: "solde", libelle: "Solde", couleur: COULEURS[3], sens: 1 },
  { cle: "dimes", libelle: "Dîmes", couleur: COULEURS[2], sens: 1 },
  { cle: "loyers", libelle: "Loyers perçus", couleur: COULEURS[1], sens: 1 },
];

function BandeFinanciere({ d }) {
  const comp = Object.fromEntries(d.annee_comparee.map((x) => [x.cle, x]));
  return (
    <div className="bande-fin">
      {CARTES_FIN.map((k) => {
        const total = d.finances.reduce((s, m) => s + m[k.cle], 0);
        // Courbe sur les mois terminés : le mois en cours, incomplet, ferait croire à une chute
        const serie = d.finances.slice(0, -1).map((m) => ({ mois: m.mois, v: m[k.cle] }));
        const cmp = comp[k.cle];
        const mieux = cmp && cmp.ecart !== 0 ? (cmp.ecart > 0) === (k.sens > 0) : null;
        return (
          <div className="carte-fin" key={k.cle} style={{ "--teinte": k.couleur }}>
            <div className="cf-tete"><span className="cf-pastille" />{k.libelle}<small>12 mois</small></div>
            <div className={`cf-valeur${total < 0 ? " negatif" : ""}`}>{bif(total, true)}</div>
            <ResponsiveContainer width="100%" height={46}>
              <AreaChart data={serie} margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
                <defs><linearGradient id={`cf-${k.cle}`} x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor={k.couleur} stopOpacity=".35" /><stop offset="100%" stopColor={k.couleur} stopOpacity="0" /></linearGradient></defs>
                <Tooltip content={<InfoBulle titre={(l) => moisCourt(serie[l]?.mois)} format={(v) => bif(v, true)} />} />
                <Area type="monotone" dataKey="v" name={k.libelle} stroke={k.couleur} strokeWidth={2} fill={`url(#cf-${k.cle})`} isAnimationActive={false} />
              </AreaChart>
            </ResponsiveContainer>
            <div className="cf-pied">
              {cmp ? (
                <span className={`evolution ${mieux === null ? "" : mieux ? "bon" : "critique"}`}>
                  {cmp.ecart >= 0 ? <ArrowUpRight size={13} /> : <ArrowDownRight size={13} />}
                  {cmp.evolution != null ? `${cmp.evolution > 0 ? "+" : ""}${cmp.evolution.toLocaleString("fr-FR")} %` : bif(cmp.ecart, true)}
                </span>
              ) : <span className="muet">—</span>}
              <span className="muet">{cmp ? `depuis janvier vs ${d.annee - 1}` : "derniers mois"}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ------------------------------------------------------------------ Projections de fin d'année */
function Projections({ d }) {
  return (
    <Carte brut titre={`Projection à la fin de ${d.annee} (montants en BIF)`}
      description={`Au rythme actuel : ${d.avancement_annee.toLocaleString("fr-FR")} % de l'année est écoulé. La barre pleine montre le réalisé, la partie hachurée ce qui reste à venir si le rythme se maintient, le trait l'année ${d.annee - 1} complète.`}>
      <div className="projections">
        {d.projections.map((x) => {
          const max = Math.max(x.projection, x.annee_precedente, 1) * 1.08;
          const evo = x.annee_precedente ? Math.round((100 * (x.projection - x.annee_precedente)) / x.annee_precedente) : null;
          const mieux = evo == null || evo === 0 ? null : (evo > 0) === (x.sens > 0);
          return (
            <div className="projection" key={x.cle}>
              <div className="pj-lib">{x.libelle}</div>
              <div className="pj-chiffres">
                <div><small>Réalisé</small><b>{court(x.a_date)}</b></div>
                <div><small>Projection</small><b className="pj-proj">{court(x.projection)}</b></div>
                <div><small>{d.annee - 1}</small><b className="muet">{court(x.annee_precedente)}</b></div>
              </div>
              <div className="pj-barre" role="img" aria-label={`${x.libelle} : réalisé ${fmt(x.a_date, x.unite)}, projection ${fmt(x.projection, x.unite)}, ${d.annee - 1} : ${fmt(x.annee_precedente, x.unite)}`}>
                <span className="pj-reste" style={{ width: `${(100 * x.projection) / max}%` }} />
                <span className="pj-fait" style={{ width: `${(100 * x.a_date) / max}%` }} />
                <i className="pj-repere" style={{ left: `${(100 * x.annee_precedente) / max}%` }} />
              </div>
              {evo != null && <span className={`evolution ${mieux === null ? "" : mieux ? "bon" : "critique"}`}>{evo > 0 ? "+" : ""}{evo} % vs {d.annee - 1}</span>}
            </div>
          );
        })}
      </div>
    </Carte>
  );
}

/* ------------------------------------------------------------------ Répartition par catégorie (barres de données) */
function Repartition({ titre, lignes, couleur, annee }) {
  const total = lignes.reduce((s, x) => s + x.montant, 0);
  const max = Math.max(1, ...lignes.map((x) => x.montant));
  return (
    <Carte brut titre={titre} description={`Depuis le 1er janvier ${annee} · total ${bif(total, true)}`}>
      <div className="repartition">
        {lignes.length === 0 ? <p className="muet petit">Aucune opération cette année.</p> : lignes.map((x) => (
          <div className="rp-ligne" key={x.cle}>
            <span className="rp-lib">{x.libelle}<small>{x.operations} opération(s)</small></span>
            <span className="rp-barre"><i style={{ width: `${(100 * x.montant) / max}%`, background: couleur }} /></span>
            <b className="chiffre">{bif(x.montant, true)}</b>
            <span className="rp-part">{x.part.toLocaleString("fr-FR")} %</span>
          </div>
        ))}
      </div>
    </Carte>
  );
}

/* ------------------------------------------------------------------ Matrice des églises locales (mise en forme conditionnelle) */
const COLONNES_EGLISE = [
  { cle: "declares", titre: "Déclarés", f: nombre, ton: "neutre" },
  { cle: "inscrits", titre: "Enregistrés", f: nombre, ton: "bon" },
  { cle: "taux", titre: "Taux", f: pct, ton: "bon" },
  { cle: "pct_baptises", titre: "% baptisés", f: (v) => (v == null ? "—" : `${v} %`), ton: "bon" },
  { cle: "pct_femmes", titre: "% femmes", f: (v) => (v == null ? "—" : `${v} %`), ton: "neutre" },
  { cle: "nouveaux_12m", titre: "Nouveaux 12 m", f: nombre, ton: "bon" },
  { cle: "biens", titre: "Biens", f: nombre, ton: "neutre" },
  { cle: "biens_risque", titre: "Biens à risque", f: nombre, ton: "mauvais" },
  { cle: "valeur", titre: "Patrimoine", f: court, ton: "bon" },
];
const TEINTE = { bon: "var(--marque)", neutre: "var(--lac)", mauvais: "var(--critique)" };

function MatriceEglises({ d }) {
  const [tri, setTri] = useState({ cle: "inscrits", sens: -1 });
  const bornes = useMemo(() => Object.fromEntries(COLONNES_EGLISE.map((c) => {
    const v = d.eglises.map((e) => e[c.cle]).filter((x) => x != null);
    return [c.cle, { min: Math.min(...v), max: Math.max(...v) }];
  })), [d]);
  const lignes = [...d.eglises].sort((a, b) => ((a[tri.cle] ?? -1) - (b[tri.cle] ?? -1)) * tri.sens);
  const fond = (c, v) => {
    if (v == null) return undefined;
    const { min, max } = bornes[c.cle];
    const t = max === min ? 0.5 : (v - min) / (max - min);
    if (c.ton === "mauvais" && v === 0) return undefined;
    return `color-mix(in srgb, ${TEINTE[c.ton]} ${Math.round(6 + t * 46)}%, transparent)`;
  };
  return (
    <Carte brut titre="Tableau des églises locales"
      description="Plus la case est foncée, plus la valeur est élevée dans la colonne. Vert : plus c'est haut, mieux c'est. Rouge : à surveiller. Cliquez sur un titre pour trier."
      actions={<div className="legende">
        <span><i className="pastille" style={{ background: "var(--marque)" }} />Favorable</span>
        <span><i className="pastille" style={{ background: "var(--lac)" }} />Indicatif</span>
        <span><i className="pastille" style={{ background: "var(--critique)" }} />À surveiller</span>
      </div>}>
      <div className="defilement"><table className="tableau matrice">
        <thead><tr>
          <th>Église locale</th>
          {COLONNES_EGLISE.map((c) => (
            <th key={c.cle} className="num">
              <button className="tri" onClick={() => setTri((t) => ({ cle: c.cle, sens: t.cle === c.cle ? -t.sens : -1 }))}>
                {c.titre}{tri.cle === c.cle ? (tri.sens < 0 ? " ↓" : " ↑") : ""}
              </button>
            </th>
          ))}
        </tr></thead>
        <tbody>{lignes.map((e) => (
          <tr key={e.id}>
            <td><div className="principal-cell">{e.nom}</div><div className="secondaire">{e.district}</div></td>
            {COLONNES_EGLISE.map((c) => <td key={c.cle} className="num chiffre" style={{ background: fond(c, e[c.cle]) }}>{c.f(e[c.cle])}</td>)}
          </tr>
        ))}</tbody>
      </table></div>
    </Carte>
  );
}

/* ------------------------------------------------------------------ Tableau mensuel avec barres de données */
function TableauMensuel({ d }) {
  const mois = [...d.finances].reverse();
  const max = (k) => Math.max(1, ...d.finances.map((m) => Math.abs(m[k])));
  const mx = { recettes: max("recettes"), depenses: max("depenses"), dimes: max("dimes"), solde: max("solde") };
  const tot = (k) => d.finances.reduce((s, m) => s + m[k], 0);
  const cellule = (m, k, couleur) => (
    <td className="num chiffre barre-cellule">
      <i style={{ width: `${(100 * Math.abs(m[k])) / mx[k]}%`, background: couleur }} />
      <span>{court(m[k])}</span>
    </td>
  );
  return (
    <Carte brut titre="Tableau mensuel" description="Les 12 derniers mois, le plus récent en haut. Montants en BIF.">
      <div className="defilement"><table className="tableau mensuel">
        <thead><tr><th>Mois</th><th className="num">Recettes</th><th className="num">Dépenses</th><th className="num">Solde</th>
          <th className="num">Dîmes</th><th className="num">Loyers</th><th className="num">Nouveaux membres</th></tr></thead>
        <tbody>
          {mois.map((m) => (
            <tr key={m.mois}>
              <td style={{ textTransform: "capitalize" }}>{new Date(m.mois).toLocaleDateString("fr-FR", { month: "long", year: "numeric" })}</td>
              {cellule(m, "recettes", COULEURS[0])}
              {cellule(m, "depenses", COULEURS[4])}
              <td className="num chiffre"><span className={`badge ${m.solde > 0 ? "bon" : m.solde < 0 ? "critique" : ""}`}>{m.solde > 0 ? "+" : ""}{court(m.solde)}</span></td>
              {cellule(m, "dimes", COULEURS[2])}
              <td className="num chiffre">{court(m.loyers)}</td>
              <td className="num chiffre">{m.nouveaux_membres || "—"}</td>
            </tr>
          ))}
        </tbody>
        <tfoot><tr>
          <td>Total 12 mois</td><td className="num chiffre">{court(tot("recettes"))}</td><td className="num chiffre">{court(tot("depenses"))}</td>
          <td className="num chiffre"><b>{tot("solde") > 0 ? "+" : ""}{court(tot("solde"))}</b></td><td className="num chiffre">{court(tot("dimes"))}</td>
          <td className="num chiffre">{court(tot("loyers"))}</td><td className="num chiffre">{tot("nouveaux_membres")}</td>
        </tr></tfoot>
      </table></div>
    </Carte>
  );
}
