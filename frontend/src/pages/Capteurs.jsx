import { useEffect, useState } from "react";
import { Area, CartesianGrid, ComposedChart, Line, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CheckCircle2, Droplets, Gauge, Loader2, Radio, Thermometer, Zap } from "lucide-react";
import { api } from "../api";
import { useCouleurs } from "../theme";
import { Bandeau, Carte, EnTete, Etat, InfoBulle, Segments, Squelette, useApi, useToast, Vide } from "../components/ui";
import { dateHeure } from "../format";

const ICONES = { NIVEAU_EAU: Droplets, DEBIT: Gauge, TEMPERATURE: Thermometer, ENERGIE: Zap };

export default function Capteurs() {
  const notifier = useToast();
  const capteurs = useApi("capteurs/");
  const alertes = useApi("alertes/?resolue=false");
  const [choisiId, setChoisiId] = useState(null);
  const [resolution, setResolution] = useState(null);

  useEffect(() => {
    const t = setInterval(() => { capteurs.recharger(); alertes.recharger(); }, 30000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    if (!choisiId && capteurs.donnees?.length) setChoisiId((capteurs.donnees.find((c) => c.en_alerte) || capteurs.donnees[0]).id);
  }, [capteurs.donnees, choisiId]);
  const choisi = capteurs.donnees?.find((c) => c.id === choisiId);

  async function resoudre(a) {
    setResolution(a.id);
    try {
      await api(`alertes/${a.id}/resoudre/`, { methode: "POST" });
      notifier("Alerte marquée comme résolue.");
      alertes.recharger();
      capteurs.recharger();
    } catch (e) {
      notifier(e.message, "erreur");
    }
    setResolution(null);
  }

  const nbAlerte = capteurs.donnees?.filter((c) => c.en_alerte).length || 0;
  const aucun = Array.isArray(capteurs.donnees) && capteurs.donnees.length === 0;
  return (
    <>
      <EnTete titre="Capteurs connectés" sousTitre="Forages, chaîne du froid des centres de santé et consommation d'énergie, mesurés en continu par des boîtiers ESP32. Actualisation toutes les 30 secondes." />

      <div className="pile">
        {alertes.donnees?.length > 0 && (
          <Carte titre="Alertes ouvertes" description="Un seuil a été franchi : une intervention est nécessaire." plein style={{ borderColor: "color-mix(in srgb, var(--critique) 35%, var(--trait))" }}>
            <table className="tableau">
              <tbody>
                {alertes.donnees.map((a) => (
                  <tr key={a.id}>
                    <td style={{ width: 130 }}><span className={`badge ${a.niveau === "CRITIQUE" ? "critique" : "attention"}`}>{a.niveau_libelle}</span></td>
                    <td><div className="principal-cell">{a.message}</div><div className="secondaire">{a.district_nom}, {dateHeure(a.date)}</div></td>
                    <td className="num">
                      <button className="bouton petit" onClick={() => resoudre(a)} disabled={resolution === a.id}>
                        {resolution === a.id ? <Loader2 className="tourne" /> : <CheckCircle2 />}Marquer comme résolue
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Carte>
        )}

        <Etat chargement={capteurs.chargement && !capteurs.donnees} erreur={capteurs.erreur}>
          {aucun ? (
            <Vide icone={Radio} titre="Aucun capteur connecté pour le moment"
              texte="Dès qu'un boîtier ESP32 envoie ses mesures (niveau d'un forage, température d'un réfrigérateur de vaccins, énergie), il apparaît ici avec son historique et ses alertes. Le programme du boîtier est fourni dans docs/esp32/umurage_capteur.ino ; il utilise la clé IOT_API_KEY du serveur." />
          ) : (
          <>
            {nbAlerte === 0 && <Bandeau type="succes">{`Les ${capteurs.donnees?.length || 0} capteurs sont dans leurs seuils normaux.`}</Bandeau>}
            <div className="grille g4" role="list">
              {capteurs.donnees?.map((c) => {
                const Ic = ICONES[c.type];
                return (
                  <button key={c.id} role="listitem" aria-pressed={c.id === choisiId} onClick={() => setChoisiId(c.id)} className="kpi"
                    style={{ textAlign: "left", cursor: "pointer", font: "inherit", outline: c.id === choisiId ? "2px solid var(--marque)" : undefined, outlineOffset: -1 }}>
                    <div className="kpi-tete">
                      <span style={{ lineHeight: 1.3 }}>{c.bien_nom}</span>
                      <div className={`kpi-icone ${c.en_alerte ? "critique" : "info"}`}><Ic /></div>
                    </div>
                    <div className="kpi-valeur" style={{ fontSize: "1.55rem" }}>
                      {c.derniere_valeur?.toLocaleString("fr-FR", { maximumFractionDigits: 1 })}<small>{c.unite}</small>
                    </div>
                    <div className="kpi-bas">
                      <span className="kpi-note">{c.type_libelle}</span>
                      {c.en_alerte ? <span className="badge critique">En alerte</span> : <span className="badge bon">Normal</span>}
                    </div>
                  </button>
                );
              })}
            </div>
            {choisi && <Historique capteur={choisi} />}
          </>
          )}
        </Etat>
      </div>
    </>
  );
}

function Historique({ capteur: c }) {
  const coul = useCouleurs();
  const [jours, setJours] = useState(7);
  const { donnees, chargement } = useApi(`capteurs/${c.id}/mesures/?jours=${jours}`, [c.id, c.derniere_mesure]);
  const data = (donnees || []).map((m) => ({ t: new Date(m.horodatage).getTime(), valeur: m.valeur }));
  const valeurs = data.map((d) => d.valeur);
  const min = Math.min(...valeurs, c.seuil_min ?? Infinity);
  const max = Math.max(...valeurs, c.seuil_max ?? -Infinity);
  const marge = (max - min) * 0.12 || 1;
  const domaine = [Math.floor(min - marge), Math.ceil(max + marge)];
  // Graduations : chaque minuit sur 7 jours, toutes les 4 heures sur 24 heures
  const graduations = [];
  if (data.length) {
    const pas = jours === 1 ? 4 * 3600e3 : 24 * 3600e3;
    const debut = new Date(data[0].t);
    debut.setMinutes(0, 0, 0);
    if (jours === 1) debut.setHours(Math.ceil(debut.getHours() / 4) * 4); else { debut.setHours(0); debut.setDate(debut.getDate() + 1); }
    for (let t = debut.getTime(); t <= data[data.length - 1].t; t += pas) graduations.push(t);
  }
  const fmtAxe = (t) => new Date(t).toLocaleString("fr-FR", jours === 1 ? { hour: "2-digit", minute: "2-digit" } : { day: "2-digit", month: "short" });

  return (
    <Carte titre={c.bien_nom}
      description={`${c.type_libelle} en ${c.unite}, capteur ${c.code}. Zone rouge : hors des seuils autorisés.`}
      actions={<Segments label="Période" valeur={jours} onChange={setJours} options={[{ id: 1, libelle: "24 heures" }, { id: 7, libelle: "7 jours" }]} />}>
      {chargement && !donnees ? <Squelette lignes={1} hauteur={300} /> : (
        <ResponsiveContainer width="100%" height={320}>
          <ComposedChart data={data} margin={{ top: 10, right: 8, left: -8 }}>
            <defs>
              <linearGradient id="degCapteur" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0" stopColor={coul.lac} stopOpacity={0.2} />
                <stop offset="1" stopColor={coul.lac} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid vertical={false} stroke={coul.grille} />
            {c.seuil_min != null && <ReferenceArea y1={domaine[0]} y2={c.seuil_min} fill={coul.critique} fillOpacity={0.07} />}
            {c.seuil_max != null && <ReferenceArea y1={c.seuil_max} y2={domaine[1]} fill={coul.critique} fillOpacity={0.07} />}
            <XAxis dataKey="t" type="number" scale="time" domain={["dataMin", "dataMax"]} ticks={graduations} tickFormatter={fmtAxe} tick={{ fontSize: 12, fill: coul.axe }} axisLine={false} tickLine={false} minTickGap={50} />
            <YAxis domain={domaine} allowDecimals={false} tick={{ fontSize: 12, fill: coul.axe }} axisLine={false} tickLine={false} width={44} />
            <Tooltip cursor={{ stroke: coul.axe, strokeDasharray: "3 3" }} content={<InfoBulle format={(v) => `${v.toLocaleString("fr-FR")} ${c.unite}`} titre={(l) => dateHeure(l)} />} />
            {c.seuil_min != null && <ReferenceLine y={c.seuil_min} stroke={coul.critique} strokeDasharray="4 4" label={{ value: `Seuil minimal ${c.seuil_min}`, position: "insideBottomLeft", fontSize: 11, fill: coul.critique }} />}
            {c.seuil_max != null && <ReferenceLine y={c.seuil_max} stroke={coul.critique} strokeDasharray="4 4" label={{ value: `Seuil maximal ${c.seuil_max}`, position: "insideTopLeft", fontSize: 11, fill: coul.critique }} />}
            <Area dataKey="valeur" stroke="none" fill="url(#degCapteur)" isAnimationActive={false} legendType="none" tooltipType="none" />
            <Line dataKey="valeur" name={c.type_libelle} stroke={coul.lac} strokeWidth={2} dot={false} activeDot={{ r: 4, stroke: coul.surface, strokeWidth: 2 }} isAnimationActive={false} />
          </ComposedChart>
        </ResponsiveContainer>
      )}
    </Carte>
  );
}
