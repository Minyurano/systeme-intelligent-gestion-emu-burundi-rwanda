import { useMemo, useState } from "react";
import { ArrowDownRight, ArrowUpRight, Award, BrainCircuit, Church, Info, ListOrdered, Trophy, X } from "lucide-react";
import AnalyseIA from "../components/AnalyseIA";
import { Carte, EnTete, Etat, Kpi, Onglets, Progres, Segments, useApi, Vide } from "../components/ui";
import { bif, nombre } from "../format";

const anneeCourante = new Date().getFullYear();
const MAX = 4;

function valeur(v, unite) {
  if (v === null || v === undefined) return <span className="muet">—</span>;
  if (unite === "monnaie") return bif(v, true);
  if (unite === "%") return `${v} %`;
  if (unite === "/100") return `${v}/100`;
  return nombre(v);
}

// Une valeur est « meilleure » si elle va dans le sens souhaité de l'indicateur
const meilleur = (sens, a, b) => (sens > 0 ? a > b : a < b);

export default function Comparaison() {
  const [niveau, setNiveau] = useState("paroisse");
  const [annee, setAnnee] = useState(anneeCourante);
  const [tri, setTri] = useState("indice");
  const [choix, setChoix] = useState([]);
  const [vue, setVue] = useState(() => {
    try { return localStorage.getItem("umurage.comparaison.vue") || "classement"; } catch { return "classement"; }
  });
  const changerVue = (v) => { setVue(v); try { localStorage.setItem("umurage.comparaison.vue", v); } catch { /* indisponible */ } };
  const { donnees: d, erreur, chargement } = useApi(`comparaison/?niveau=${niveau}&annee=${annee}`, [niveau, annee]);

  const indic = useMemo(() => Object.fromEntries((d?.indicateurs || []).map((i) => [i.cle, i])), [d]);
  const lignes = useMemo(() => {
    if (!d) return [];
    const i = indic[tri];
    return [...d.lignes].sort((a, b) => {
      if (a[tri] == null) return 1;
      if (b[tri] == null) return -1;
      return (i?.sens < 0 ? 1 : -1) * (a[tri] - b[tri]);
    });
  }, [d, tri, indic]);
  const selection = (d?.lignes || []).filter((l) => choix.includes(l.id));
  const basculer = (id) => setChoix((c) => (c.includes(id) ? c.filter((x) => x !== id) : c.length >= MAX ? c : [...c, id]));
  const changerNiveau = (n) => { setNiveau(n); setChoix([]); setTri("indice"); };
  const nomEntite = niveau === "paroisse" ? "église locale" : "district";
  const premier = d?.lignes?.[0];
  const dernier = d?.lignes?.filter((l) => l.indice != null).slice(-1)[0];

  return (
    <>
      <EnTete titre="Comparaison des églises" sousTitre="Les églises locales (paroisses) ou les districts de l'organisation, comparés sur les mêmes indicateurs. Cochez jusqu'à 4 lignes pour les mettre côte à côte.">
        <Segments label="Niveau" valeur={niveau} onChange={changerNiveau} options={[{ id: "paroisse", libelle: "Églises locales" }, { id: "district", libelle: "Districts" }]} />
        <select className="saisie-ui" value={annee} onChange={(e) => setAnnee(Number(e.target.value))} aria-label="Année">
          {[0, 1, 2].map((i) => <option key={i} value={anneeCourante - i}>{anneeCourante - i}</option>)}
        </select>
      </EnTete>
      <Onglets actif={vue} onChange={changerVue} onglets={[
        { id: "classement", libelle: "Classement", icone: ListOrdered },
        { id: "analyse", libelle: "Analyse intelligente (IA)", icone: BrainCircuit },
      ]} />
      {vue === "analyse" ? <AnalyseIA niveau={niveau} annee={annee} /> : (
      <Etat chargement={chargement && !d} erreur={erreur}>
        {d && (d.lignes.length === 0 ? <Vide titre="Rien à comparer" texte="Aucune entité dans votre périmètre." /> : (
          <div className="pile">
            <div className="kpis">
              <Kpi libelle={niveau === "paroisse" ? "Églises locales comparées" : "Districts comparés"} icone={Church} valeur={d.lignes.length} />
              <Kpi libelle="Meilleur indice" icone={Trophy} ton="bon" valeur={premier?.indice != null ? `${premier.indice}/100` : "—"} note={premier?.nom} />
              <Kpi libelle="Indice moyen" icone={Award} ton="info" valeur={d.moyennes.indice != null ? `${Math.round(d.moyennes.indice)}/100` : "—"} />
              <Kpi libelle="À accompagner en priorité" icone={ArrowDownRight} ton="attention" valeur={dernier?.indice != null ? `${dernier.indice}/100` : "—"} note={dernier?.nom} />
            </div>

            {selection.length > 0 && (
              <Carte brut titre={`Comparaison côte à côte (${selection.length}/${MAX})`} description="En vert la meilleure valeur, en rouge la plus faible, pour les indicateurs où un sens est souhaitable."
                actions={<button className="bouton" onClick={() => setChoix([])}><X />Vider</button>}>
                <div className="defilement"><table className="tableau">
                  <thead><tr><th>Indicateur</th>{selection.map((l) => <th key={l.id} className="num">{l.nom}{l.district && <div className="secondaire">{l.district}</div>}</th>)}<th className="num">Moyenne</th></tr></thead>
                  <tbody>{d.indicateurs.map((i) => {
                    const vals = selection.map((l) => l[i.cle]).filter((v) => v != null);
                    const best = i.sens && vals.length > 1 ? vals.reduce((a, b) => (meilleur(i.sens, b, a) ? b : a)) : null;
                    const worst = i.sens && vals.length > 1 ? vals.reduce((a, b) => (meilleur(i.sens, a, b) ? b : a)) : null;
                    return (
                      <tr key={i.cle}>
                        <td>{i.libelle}</td>
                        {selection.map((l) => {
                          const v = l[i.cle];
                          const ton = v != null && best !== worst ? (v === best ? "bon" : v === worst ? "critique" : "") : "";
                          return <td key={l.id} className="num chiffre">{ton ? <span className={`badge ${ton}`}>{valeur(v, i.unite)}</span> : valeur(v, i.unite)}</td>;
                        })}
                        <td className="num chiffre muet">{valeur(d.moyennes[i.cle] != null ? Math.round(d.moyennes[i.cle]) : null, i.unite)}</td>
                      </tr>
                    );
                  })}</tbody>
                </table></div>
              </Carte>
            )}

            <Carte brut titre="Classement" description={`Cliquez sur une ${nomEntite} pour l'ajouter à la comparaison.`}
              actions={
                <label className="petit" style={{ display: "flex", alignItems: "center", gap: 8 }}>Trier par
                  <select className="saisie-ui" value={tri} onChange={(e) => setTri(e.target.value)}>
                    {d.indicateurs.map((i) => <option key={i.cle} value={i.cle}>{i.libelle}</option>)}
                  </select>
                </label>
              }>
              <div className="defilement"><table className="tableau">
                <thead><tr>
                  <th style={{ width: 34 }} /><th>#</th><th>{niveau === "paroisse" ? "Église locale" : "District"}</th>
                  <th style={{ minWidth: 150 }}>Indice de bonne gestion</th>
                  {tri !== "indice" && <th className="num">{indic[tri]?.libelle}</th>}
                  <th className="num">Biens</th><th className="num">Valeur</th><th className="num">Fiches complètes</th><th className="num">Terrains titrés</th><th className="num">À risque</th>
                  {niveau === "district" && <th className="num">Solde de l'année</th>}
                </tr></thead>
                <tbody>{lignes.map((l, idx) => {
                  const coche = choix.includes(l.id);
                  const ecart = (k) => {
                    const m = d.moyennes[k]; const v = l[k]; const s = indic[k]?.sens;
                    if (m == null || v == null || !s || Math.abs(v - m) < 5) return null;
                    return meilleur(s, v, m) ? <ArrowUpRight size={13} style={{ color: "var(--succes)", verticalAlign: -2 }} /> : <ArrowDownRight size={13} style={{ color: "var(--critique)", verticalAlign: -2 }} />;
                  };
                  return (
                    <tr key={l.id} onClick={() => basculer(l.id)} style={{ cursor: "pointer", background: coche ? "var(--survol)" : undefined }}>
                      <td><input type="checkbox" checked={coche} readOnly disabled={!coche && choix.length >= MAX} aria-label={`Comparer ${l.nom}`} /></td>
                      <td className="chiffre">{idx + 1}</td>
                      <td><div className="principal-cell">{l.nom}</div><div className="secondaire">{[l.district, l.responsable, l.membres ? `${nombre(l.membres)} membres` : null].filter(Boolean).join(" · ")}</div></td>
                      <td>{l.indice != null ? <><Progres valeur={l.indice} couleur={l.indice >= 75 ? "var(--succes)" : l.indice >= 50 ? "var(--sorgho)" : "var(--critique)"} /></> : <span className="muet">—</span>}</td>
                      {tri !== "indice" && <td className="num chiffre" style={{ whiteSpace: "nowrap" }}><b>{valeur(l[tri], indic[tri]?.unite)}</b> {ecart(tri)}</td>}
                      <td className="num chiffre">{nombre(l.biens)}</td>
                      <td className="num chiffre">{bif(l.valeur, true)}</td>
                      <td className="num chiffre" style={{ whiteSpace: "nowrap" }}>{valeur(l.qualite, "%")} {ecart("qualite")}</td>
                      <td className="num chiffre" style={{ whiteSpace: "nowrap" }}>{valeur(l.pct_titres, "%")} {ecart("pct_titres")}</td>
                      <td className="num chiffre" style={{ whiteSpace: "nowrap" }}>{valeur(l.pct_a_risque, "%")} {ecart("pct_a_risque")}</td>
                      {niveau === "district" && <td className="num chiffre">{bif(l.solde, true)}</td>}
                    </tr>
                  );
                })}</tbody>
              </table></div>
            </Carte>
            <p className="petit muet" style={{ display: "flex", gap: 6, alignItems: "flex-start" }}><Info size={14} style={{ flex: "none", marginTop: 2 }} />{d.methode} Les flèches signalent un écart de plus de 5 points avec la moyenne. La comparaison reste limitée à votre organisation.</p>
          </div>
        ))}
      </Etat>
      )}
    </>
  );
}
