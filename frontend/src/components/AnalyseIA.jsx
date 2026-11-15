import { useMemo, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell, LabelList, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis,
} from "recharts";
import { AlertTriangle, BrainCircuit, CheckCircle2, ChevronRight, Handshake, Info, Lightbulb, Sparkles, Target } from "lucide-react";
import { Bandeau, Carte, Etat, useApi, Vide } from "./ui";
import { useCouleurs } from "../theme";
import { couleurProfil, donneesEcarts, etiquettesVisibles, ficheEglise, niveauEcart, signe } from "../analyse";

const TON_FIABILITE = { faible: "attention", indicative: "info", bonne: "bon" };

function Lecture({ children }) {
  return (
    <div className="ia-lecture">
      <Lightbulb size={16} aria-hidden />
      <div>{children}</div>
    </div>
  );
}

// ---------------------------------------------------------------------------- 1. carte des profils
function PointProfil({ cx, cy, fill, selection, payload, surface, texte, nomme }) {
  const actif = selection === payload.id;
  return (
    <g>
      <circle cx={cx} cy={cy} r={actif ? 9 : 6} fill={fill} stroke={actif ? "var(--encre)" : surface} strokeWidth={actif ? 2.5 : 2} />
      {nomme && <text x={cx} y={cy - (actif ? 14 : 11)} textAnchor="middle" fontSize={11.5} fontWeight={actif ? 700 : 500} fill={texte}
        stroke={surface} strokeWidth={3} paintOrder="stroke">{payload.nom}</text>}
    </g>
  );
}

function CarteProfils({ d, selection, choisir }) {
  const c = useCouleurs();
  const parProfil = useMemo(() => d.profils.map((p) => ({ ...p, points: d.carte.points.filter((pt) => pt.profil === p.id) })), [d]);
  const { axes } = d.carte;
  const effectifs = useMemo(() => Object.fromEntries(d.profils.map((p) => [p.id, p.effectif])), [d]);
  // Sur un écran étroit, un nom occupe une plus grande part du graphique : on en affiche moins
  const largeurEcran = typeof window !== "undefined" ? window.innerWidth : 1280;
  const parLettre = 0.015 * Math.max(1, 900 / Math.max(320, largeurEcran));
  const nommes = useMemo(() => etiquettesVisibles(d.carte.points, effectifs, selection, { parLettre }), [d, effectifs, selection, parLettre]);
  return (
    <Carte titre="Carte des églises" description="Chaque point est une église ; la couleur indique son profil. Survolez un point pour son nom, cliquez pour voir sa fiche.">
      <div className="ia-legende" aria-label="Légende des profils">
        {d.profils.map((p) => (
          <span key={p.id}><i style={{ background: couleurProfil(p.id) }} />{p.nom} ({p.effectif})</span>
        ))}
      </div>
      <ResponsiveContainer width="100%" height={380}>
        <ScatterChart margin={{ top: 20, right: 24, bottom: 34, left: 8 }}>
          <CartesianGrid stroke={c.grille} />
          <XAxis type="number" dataKey="x" name={axes.x.libelle} tick={false} axisLine={{ stroke: c.grille }} tickLine={false}
            label={{ value: `${axes.x.libelle} (${axes.x.variance} %) →`, position: "insideBottom", offset: -18, fill: c.texte, fontSize: 12 }} />
          <YAxis type="number" dataKey="y" name={axes.y.libelle} tick={false} axisLine={{ stroke: c.grille }} tickLine={false} width={28}
            label={{ value: `${axes.y.libelle} (${axes.y.variance} %) →`, angle: -90, position: "insideLeft", offset: 14, fill: c.texte, fontSize: 12, style: { textAnchor: "middle" } }} />
          <ZAxis range={[90, 90]} />
          <ReferenceLine x={0} stroke={c.axe} strokeDasharray="3 4" />
          <ReferenceLine y={0} stroke={c.axe} strokeDasharray="3 4" />
          <Tooltip cursor={false} content={({ active, payload }) => {
            const p = active && payload?.[0]?.payload;
            if (!p) return null;
            const profil = d.profils.find((x) => x.id === p.profil);
            return (
              <div className="infobulle">
                <strong>{p.nom}</strong>
                <div className="ligne"><span><i className="pastille" style={{ background: couleurProfil(p.profil) }} />{profil?.nom}</span></div>
                <div className="ligne"><span>Indice de bonne gestion</span><b>{p.indice ?? "—"}/100</b></div>
              </div>
            );
          }} />
          {parProfil.map((p) => (
            <Scatter key={p.id} name={p.nom} data={p.points} fill={couleurProfil(p.id)} onClick={(pt) => choisir(pt.id)} style={{ cursor: "pointer" }}
              isAnimationActive={false}
              shape={(props) => <PointProfil {...props} selection={selection} surface={c.surface} texte={c.texte} nomme={nommes.has(props.payload.id)} />} />
          ))}
        </ScatterChart>
      </ResponsiveContainer>
      <Lecture>
        <p><b>Comment lire :</b> {d.carte.lecture}</p>
        <p><b>Axe horizontal.</b> {axes.x.texte}</p>
        <p><b>Axe vertical.</b> {axes.y.texte}</p>
      </Lecture>
    </Carte>
  );
}

// ---------------------------------------------------------------------------- 2. profils types
function BarresProfil({ traits }) {
  const c = useCouleurs();
  const gestion = traits.filter((t) => t.z_oriente !== null).map((t) => ({ ...t, v: Math.max(-2.5, Math.min(2.5, t.z_oriente)) }));
  return (
    <ResponsiveContainer width="100%" height={Math.max(150, gestion.length * 30)}>
      <BarChart data={gestion} layout="vertical" margin={{ top: 4, right: 16, left: 4, bottom: 4 }} barCategoryGap={6}>
        <XAxis type="number" domain={[-2.5, 2.5]} hide />
        <YAxis type="category" dataKey="libelle" width={150} tick={{ fontSize: 11.5, fill: c.texte }} axisLine={false} tickLine={false} />
        <ReferenceLine x={0} stroke={c.axe} />
        <Tooltip cursor={{ fill: c.curseur }} content={({ active, payload }) => {
          const t = active && payload?.[0]?.payload;
          if (!t) return null;
          return (
            <div className="infobulle">
              <strong>{t.libelle}</strong>
              <div>{t.z_oriente >= 0 ? "Mieux" : "Moins bien"} que la moyenne ({niveauEcart(t.z_oriente)}).</div>
            </div>
          );
        }} />
        <Bar dataKey="v" radius={4} maxBarSize={14}>
          {gestion.map((t) => <Cell key={t.cle} fill={t.v >= 0 ? c.marque : c.critique} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

function Profils({ d }) {
  return (
    <Carte titre="Profils d'églises" description={`Groupes formés automatiquement par l'ordinateur. ${d.qualite_profils.texte}`}>
      <div className="ia-profils">
        {d.profils.map((p) => {
          const contexte = p.traits.filter((t) => t.groupe === "contexte" && Math.abs(t.z) >= 0.5);
          return (
            <article key={p.id} className="ia-profil" style={{ borderTopColor: couleurProfil(p.id) }}>
              <header>
                <h3><i style={{ background: couleurProfil(p.id) }} />{p.nom}</h3>
                <span className="badge">{p.effectif} · indice moyen {p.indice_moyen ?? "—"}/100</span>
              </header>
              <p className="petit">{p.description}</p>
              {contexte.length > 0 && <p className="petit muet">Contexte : {contexte.map((t) => `${t.libelle.toLowerCase()} ${niveauEcart(t.z)}`).join(" ; ")}.</p>}
              <div className="petit ia-echelle"><span>← moins bien que la moyenne</span><span>mieux que la moyenne →</span></div>
              <BarresProfil traits={p.traits} />
              {p.forces.length > 0 && <ul className="ia-liste bon">{p.forces.map((f) => <li key={f}><CheckCircle2 size={14} aria-hidden />{f}</li>)}</ul>}
              {p.faiblesses.length > 0 && <ul className="ia-liste alerte">{p.faiblesses.map((f) => <li key={f}><AlertTriangle size={14} aria-hidden />À renforcer — {f}</li>)}</ul>}
              <p className="petit muet">Églises : {p.membres.join(", ")}.</p>
            </article>
          );
        })}
      </div>
    </Carte>
  );
}

// ---------------------------------------------------------------------------- 3. indice réel / attendu
function Ecarts({ attendu, choisir }) {
  const c = useCouleurs();
  if (!attendu?.disponible) return <Carte titre="Indice réel et indice attendu"><p className="muet">{attendu?.raison}</p></Carte>;
  const data = donneesEcarts(attendu);
  const titre = attendu.reference === "contexte" ? "Mieux ou moins bien qu'attendu, à contexte égal" : "Écart à la moyenne des autres églises";
  return (
    <Carte titre={titre} description="Barre verte vers la droite : l'église fait mieux que prévu. Barre rouge vers la gauche : marge de progrès.">
      <ResponsiveContainer width="100%" height={Math.max(220, data.length * 28)}>
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 40, left: 4, bottom: 4 }} barCategoryGap={6}>
          <CartesianGrid horizontal={false} stroke={c.grille} />
          <XAxis type="number" tick={{ fontSize: 11, fill: c.axe }} axisLine={false} tickLine={false} tickFormatter={signe} />
          <YAxis type="category" dataKey="nom_court" width={130} tick={{ fontSize: 11.5, fill: c.texte }} axisLine={false} tickLine={false} />
          <ReferenceLine x={0} stroke={c.axe} />
          <Tooltip cursor={{ fill: c.curseur }} content={({ active, payload }) => {
            const l = active && payload?.[0]?.payload;
            if (!l) return null;
            return (
              <div className="infobulle" style={{ maxWidth: 280 }}>
                <strong>{l.nom}</strong>
                <div className="ligne"><span>Indice réel</span><b>{l.reel}/100</b></div>
                <div className="ligne"><span>{attendu.reference === "contexte" ? "Indice attendu" : "Moyenne des autres"}</span><b>{l.attendu}/100</b></div>
                <div className="ligne"><span>Écart</span><b>{signe(l.ecart)}</b></div>
                <p className="petit" style={{ margin: "6px 0 0" }}>{l.texte}</p>
              </div>
            );
          }} />
          <Bar dataKey="ecart" radius={4} maxBarSize={14} onClick={(l) => choisir(l.id)} style={{ cursor: "pointer" }}>
            {data.map((l) => <Cell key={l.id} fill={l.ecart >= 0 ? c.marque : c.critique} />)}
            <LabelList dataKey="ecart" position="right" formatter={signe} style={{ fontSize: 11, fill: c.texte }} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <Lecture>
        <p>{attendu.lecture}</p>
        {attendu.reference === "contexte" && <p className="muet">Le contexte explique {Math.round(100 * attendu.r2)} % des différences d'indice (validation croisée).</p>}
      </Lecture>
    </Carte>
  );
}

// ---------------------------------------------------------------------------- 4. atypiques
function Atypiques({ atypiques, choisir }) {
  const c = useCouleurs();
  if (!atypiques?.disponible) return <Carte titre="Profils atypiques (réseau de neurones)"><p className="muet">{atypiques?.raison}</p></Carte>;
  const data = atypiques.lignes.slice(0, 12).map((l) => ({ ...l, nom_court: l.nom.length > 16 ? `${l.nom.slice(0, 15)}…` : l.nom }));
  return (
    <Carte titre="Profils atypiques (réseau de neurones)" description="Plus la barre est longue, moins l'église ressemble aux autres. Au-delà de la ligne pointillée : profil atypique à vérifier.">
      <ResponsiveContainer width="100%" height={Math.max(200, data.length * 28)}>
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 36, left: 4, bottom: 4 }} barCategoryGap={6}>
          <XAxis type="number" domain={[0, Math.max(100, atypiques.seuil_score + 5)]} hide />
          <YAxis type="category" dataKey="nom_court" width={130} tick={{ fontSize: 11.5, fill: c.texte }} axisLine={false} tickLine={false} />
          {atypiques.seuil_score <= 100 && <ReferenceLine x={atypiques.seuil_score} stroke={c.critique} strokeDasharray="4 4" label={{ value: "seuil", position: "top", fill: c.critique, fontSize: 11 }} />}
          <Tooltip cursor={{ fill: c.curseur }} content={({ active, payload }) => {
            const l = active && payload?.[0]?.payload;
            if (!l) return null;
            return (
              <div className="infobulle" style={{ maxWidth: 300 }}>
                <strong>{l.nom}</strong>
                <div className="ligne"><span>Singularité</span><b>{l.score}/100</b></div>
                <p className="petit" style={{ margin: "6px 0 0" }}>{l.atypique ? "Atypique : " : "Ce qui la distingue le plus : "}{l.raisons.join(" ; ")}.</p>
              </div>
            );
          }} />
          <Bar dataKey="score" radius={4} maxBarSize={14} onClick={(l) => choisir(l.id)} style={{ cursor: "pointer" }}>
            {data.map((l) => <Cell key={l.id} fill={l.atypique ? c.critique : c.axe} />)}
            <LabelList dataKey="score" position="right" style={{ fontSize: 11, fill: c.texte }} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <Lecture>
        <p>{atypiques.lecture}</p>
        {atypiques.note && <p className="muet">{atypiques.note}</p>}
        {atypiques.lignes.filter((l) => l.atypique).map((l) => <p key={l.id}><b>{l.nom}</b> : {l.raisons.join(" ; ")}.</p>)}
      </Lecture>
    </Carte>
  );
}

// ---------------------------------------------------------------------------- 5. jumelles
function Jumelles({ jumelles, choisir }) {
  return (
    <Carte brut titre="Églises jumelles : qui peut apprendre de qui ?" description="Pour chaque église, une église de contexte comparable (taille, patrimoine, bénéficiaires) qui fait mieux, et les points précis où elle fait mieux.">
      {jumelles.length === 0 ? <p className="muet" style={{ padding: "0 20px 16px" }}>Aucune paire utile : les églises comparables ont des résultats proches.</p> : (
        <div className="defilement"><table className="tableau">
          <thead><tr><th>Église</th><th /><th>Peut s'inspirer de</th><th className="num">Ressemblance</th><th>Points à travailler (elle → modèle)</th></tr></thead>
          <tbody>{jumelles.map((j) => (
            <tr key={j.id} onClick={() => choisir(j.id)} style={{ cursor: "pointer" }}>
              <td><div className="principal-cell">{j.nom}</div><div className="secondaire">indice {j.indice}/100</div></td>
              <td><ChevronRight size={16} className="muet" aria-hidden /></td>
              <td><div className="principal-cell">{j.modele.nom}</div><div className="secondaire">indice {j.modele.indice}/100 ({signe(j.modele.indice - j.indice)})</div></td>
              <td className="num chiffre">{j.modele.similarite} %</td>
              <td><ul className="ia-liste compact">{j.lecons.map((l) => <li key={l}>{l}</li>)}</ul></td>
            </tr>
          ))}</tbody>
        </table></div>
      )}
    </Carte>
  );
}

// ---------------------------------------------------------------------------- fiche d'une église
function FicheEglise({ d, id, choisir }) {
  const fiche = ficheEglise(d, id);
  const options = [...(d.carte?.points || [])].sort((a, b) => a.nom.localeCompare(b.nom));
  const icones = { bon: CheckCircle2, alerte: AlertTriangle, piste: Handshake, profil: Target, neutre: Info };
  return (
    <Carte titre="Fiche d'analyse d'une église" description="Ce que disent les cinq méthodes au sujet d'une église, en quelques phrases.">
      <select className="saisie-ui" style={{ width: "100%", marginBottom: 14 }} value={id ?? ""} onChange={(e) => choisir(e.target.value ? Number(e.target.value) : null)} aria-label="Choisir une église">
        <option value="">Choisir une église…</option>
        {options.map((p) => <option key={p.id} value={p.id}>{p.nom}</option>)}
      </select>
      {!fiche ? <p className="muet">Choisissez une église dans la liste, ou cliquez sur un point de la carte ou une barre d'un graphique.</p> : (
        <div className="ia-fiche">
          <h3>{fiche.nom} <span className="badge">{fiche.indice ?? "—"}/100</span></h3>
          <ul>
            {fiche.phrases.map((p, i) => {
              const Ic = icones[p.type] || Info;
              return <li key={i} className={`ia-phrase ${p.type}`}><Ic size={15} aria-hidden /><span>{p.texte}</span></li>;
            })}
          </ul>
        </div>
      )}
    </Carte>
  );
}

// ---------------------------------------------------------------------------- page
export default function AnalyseIA({ niveau, annee }) {
  const { donnees: d, erreur, chargement } = useApi(`comparaison/analyse/?niveau=${niveau}&annee=${annee}`, [niveau, annee]);
  const [selection, setSelection] = useState(null);
  const nom = niveau === "paroisse" ? "églises" : "districts";
  return (
    <Etat chargement={chargement && !d} erreur={erreur} lignes={6}>
      {d && (!d.disponible ? <Vide icone={BrainCircuit} titre="Analyse indisponible" texte={d.raison} /> : (
        <div className="pile">
          <Carte titre={<span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}><Sparkles size={18} aria-hidden />Ce qu'il faut retenir</span>}
            description={`Analyse automatique de ${d.n} ${nom} par apprentissage automatique, pour l'année ${d.annee}.`}
            actions={<span className={`badge ${TON_FIABILITE[d.fiabilite.niveau]}`}>Fiabilité {d.fiabilite.niveau}</span>}>
            <ul className="ia-resume">{d.resume.map((r) => <li key={r}>{r}</li>)}</ul>
            <p className="petit muet" style={{ marginBottom: 0 }}>{d.fiabilite.texte}</p>
          </Carte>

          <div className="grille g-3-2">
            {d.carte && d.profils ? <CarteProfils d={d} selection={selection} choisir={setSelection} /> : <Bandeau>Il faut au moins 4 {nom} pour dessiner les profils.</Bandeau>}
            <FicheEglise d={d} id={selection} choisir={setSelection} />
          </div>
          {d.profils && <Profils d={d} />}
          <div className="grille g2">
            <Ecarts attendu={d.attendu} choisir={setSelection} />
            <Atypiques atypiques={d.atypiques} choisir={setSelection} />
          </div>
          <Jumelles jumelles={d.jumelles} choisir={setSelection} />

          <details className="ia-methode">
            <summary><BrainCircuit size={16} aria-hidden />Comment fonctionne l'analyse ?</summary>
            <dl>{d.methode.map((m) => <div key={m.titre}><dt>{m.titre}</dt><dd>{m.texte}</dd></div>)}</dl>
            <p className="petit">Indicateurs utilisés : {d.variables.map((v) => v.libelle).join(", ")}.
              {d.variables_ecartees.length > 0 && <> Écartés : {d.variables_ecartees.map((v) => `${v.libelle} (${v.raison})`).join(" ; ")}.</>}</p>
            <p className="petit muet">Les données restent dans votre organisation. Ces résultats aident à décider : ils ne remplacent pas la connaissance du terrain.</p>
          </details>
        </div>
      ))}
    </Etat>
  );
}
