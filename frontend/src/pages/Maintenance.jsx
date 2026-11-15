import { useState } from "react";
import { BrainCircuit, CalendarSync, CircleCheckBig, Hammer, Plus, Siren, Truck, Wrench } from "lucide-react";
import { api } from "../api";
import { useAuth } from "../auth";
import { Carte, EnTete, Etat, Kpi, Onglets, Segments, useApi, useToast, Vide } from "../components/ui";
import { agir, FormModale, optionsBiens, useBiens } from "../components/metier";
import { bif, date } from "../format";

const TON_PRIO = { URGENTE: "critique", HAUTE: "attention", NORMALE: "info", BASSE: "" };
const TON_STATUT = { DEMANDE: "", PLANIFIE: "info", EN_COURS: "attention", TERMINE: "bon", ANNULE: "" };
const STATUTS = [["DEMANDE", "Demandé"], ["PLANIFIE", "Planifié"], ["EN_COURS", "En cours"], ["TERMINE", "Terminé"], ["ANNULE", "Annulé"]];

export default function Maintenance() {
  const { peut, moi } = useAuth();
  const notifier = useToast();
  const [onglet, setOnglet] = useState("ordres");
  const [filtre, setFiltre] = useState("ouverts");
  const [form, setForm] = useState(null);
  const [aTerminer, setATerminer] = useState(null);
  const ordres = useApi("ordres-travail/");
  const plans = useApi("plans-maintenance/");
  const fournisseurs = useApi("fournisseurs/");
  const biens = useBiens();
  const ot = ordres.donnees || [];
  const ouverts = ot.filter((o) => ["DEMANDE", "PLANIFIE", "EN_COURS"].includes(o.statut));
  const affiches = filtre === "ouverts" ? ouverts : filtre === "ia" ? ouverts.filter((o) => o.origine === "RISQUE") : ot;
  const ecrire = peut("projets") || moi.role === "AGENT";
  const coutAnnee = ot.filter((o) => o.statut === "TERMINE" && o.termine_le?.startsWith(String(new Date().getFullYear())))
    .reduce((s, o) => s + Number(o.cout_reel || 0), 0);
  const optFournisseurs = [{ v: "", l: "—" }, ...(fournisseurs.donnees || []).map((f) => ({ v: f.id, l: `${f.nom} (${f.specialite})` }))];

  async function statut(o, s) {
    try {
      await api(`ordres-travail/${o.id}/`, { methode: "PATCH", corps: { statut: s } });
      ordres.recharger();
    } catch (e) { notifier(e.message, "erreur"); }
  }

  async function depuisRisques() {
    const r = await agir("ordres-travail/depuis_risques/", {}, notifier);
    if (r) { notifier(r.crees ? `${r.crees} inspection(s) ouverte(s) pour les biens à risque` : "Tous les biens à risque ont déjà un ordre ouvert"); ordres.recharger(); }
  }

  return (
    <>
      <EnTete titre="Maintenance" sousTitre="Ordres de travail, entretiens préventifs et fournisseurs. Les biens que l'IA juge à risque reçoivent automatiquement une inspection prioritaire.">
        {peut("projets") && <button className="bouton" onClick={depuisRisques}><BrainCircuit />Inspecter les biens à risque</button>}
        {ecrire && <button className="bouton principal" onClick={() => setForm(onglet === "plans" ? "plan" : onglet === "fournisseurs" ? "fournisseur" : "ordre")}><Plus />
          {onglet === "plans" ? "Nouveau plan" : onglet === "fournisseurs" ? "Nouveau fournisseur" : "Nouvel ordre de travail"}</button>}
      </EnTete>
      <Etat chargement={ordres.chargement && !ordres.donnees} erreur={ordres.erreur}>
        <div className="pile">
          <div className="kpis">
            <Kpi libelle="Ordres ouverts" icone={Wrench} valeur={ouverts.length} />
            <Kpi libelle="Urgents ou prioritaires" icone={Siren} ton={ouverts.some((o) => o.priorite === "URGENTE") ? "critique" : "attention"}
              valeur={ouverts.filter((o) => ["URGENTE", "HAUTE"].includes(o.priorite)).length} />
            <Kpi libelle="Ouverts par l'IA" icone={BrainCircuit} ton="info" valeur={ouverts.filter((o) => o.origine === "RISQUE").length} note="Score de risque ≥ 70" />
            <Kpi libelle="Coût réel cette année" icone={Hammer} valeur={bif(coutAnnee, true)} />
          </div>
          <Onglets actif={onglet} onChange={setOnglet} onglets={[
            { id: "ordres", libelle: "Ordres de travail", icone: Wrench, nb: ouverts.length },
            { id: "plans", libelle: "Entretien préventif", icone: CalendarSync, nb: plans.donnees?.length },
            { id: "fournisseurs", libelle: "Fournisseurs", icone: Truck, nb: fournisseurs.donnees?.length },
          ]} />
          {onglet === "ordres" && (
            <Carte brut titre="Ordres de travail" actions={<Segments label="Filtre" valeur={filtre} onChange={setFiltre} options={[
              { id: "ouverts", libelle: "Ouverts" }, { id: "ia", libelle: "Ouverts par l'IA" }, { id: "tous", libelle: "Tous" }]} />}>
              <div style={{ height: 12 }} />
              {affiches.length === 0 ? <Vide titre="Aucun ordre de travail" /> : (
                <div className="defilement"><table className="tableau">
                  <thead><tr><th>Travail</th><th>Bien</th><th>Priorité</th><th>Statut</th><th className="num">Coût</th><th /></tr></thead>
                  <tbody>{affiches.map((o) => (
                    <tr key={o.id}>
                      <td><div className="principal-cell">OT-{o.id} · {o.titre}</div><div className="secondaire">{o.type_libelle} · {o.origine_libelle}{o.fournisseur_nom ? ` · ${o.fournisseur_nom}` : ""}{o.date_prevue ? ` · prévu le ${date(o.date_prevue)}` : ""}</div></td>
                      <td>{o.bien_code}<div className="secondaire">{o.bien_nom}</div></td>
                      <td><span className={`badge ${TON_PRIO[o.priorite]}`}>{o.priorite_libelle}</span></td>
                      <td>{ecrire && !["TERMINE", "ANNULE"].includes(o.statut) ? (
                        <select className="saisie-ui" style={{ height: 32 }} value={o.statut} onChange={(e) => (e.target.value === "TERMINE" ? setATerminer(o) : statut(o, e.target.value))} aria-label="Statut">
                          {STATUTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                        </select>
                      ) : <span className={`badge ${TON_STATUT[o.statut]}`}>{o.statut_libelle}</span>}</td>
                      <td className="num chiffre">{o.cout_reel != null ? bif(o.cout_reel, true) : Number(o.cout_estime) ? <span className="muet">~{bif(o.cout_estime, true)}</span> : "—"}</td>
                      <td>{ecrire && !["TERMINE", "ANNULE"].includes(o.statut) && <button className="bouton petit" onClick={() => setATerminer(o)}><CircleCheckBig />Terminer</button>}</td>
                    </tr>
                  ))}</tbody>
                </table></div>
              )}
            </Carte>
          )}
          {onglet === "plans" && (
            <Carte brut titre="Plans d'entretien préventif" description="Un ordre de travail est créé automatiquement 15 jours avant chaque échéance.">
              {!plans.donnees?.length ? <Vide titre="Aucun plan" /> : (
                <table className="tableau"><thead><tr><th>Entretien</th><th>Bien</th><th>Fréquence</th><th>Prochaine date</th><th className="num">Coût estimé</th></tr></thead>
                  <tbody>{plans.donnees.map((p) => (
                    <tr key={p.id}><td>{p.libelle}<div className="secondaire">{p.fournisseur_nom || "—"}</div></td><td>{p.bien_code} · {p.bien_nom}</td>
                      <td>tous les {p.periodicite_mois} mois</td><td>{date(p.prochaine_date)}</td><td className="num chiffre">{bif(p.cout_estime, true)}</td></tr>
                  ))}</tbody></table>
              )}
            </Carte>
          )}
          {onglet === "fournisseurs" && (
            <Carte brut titre="Fournisseurs et artisans">
              {!fournisseurs.donnees?.length ? <Vide titre="Aucun fournisseur" /> : (
                <table className="tableau"><thead><tr><th>Nom</th><th>Spécialité</th><th>Téléphone</th><th className="num">Ordres</th></tr></thead>
                  <tbody>{fournisseurs.donnees.map((f) => (
                    <tr key={f.id}><td>{f.nom}</td><td>{f.specialite}</td><td>{f.telephone}</td><td className="num">{f.nb_ordres}</td></tr>
                  ))}</tbody></table>
              )}
            </Carte>
          )}
        </div>
      </Etat>

      {form === "ordre" && (
        <FormModale titre="Nouvel ordre de travail" onFermer={() => setForm(null)} onFait={() => { notifier("Ordre de travail créé"); ordres.recharger(); }}
          envoyer={(c) => api("ordres-travail/", { methode: "POST", corps: c })} initial={{ type: "REPARATION", priorite: "NORMALE", statut: "DEMANDE" }}
          champs={[
            { k: "bien", libelle: "Bien", type: "select", options: optionsBiens(biens), requis: true, large: true },
            { k: "titre", libelle: "Travail à faire", requis: true, large: true, exemple: "Remplacer la pompe du forage" },
            { k: "type", libelle: "Type", type: "select", options: [{ v: "REPARATION", l: "Réparation" }, { v: "MAINTENANCE", l: "Maintenance" }, { v: "INSPECTION", l: "Inspection" }] },
            { k: "priorite", libelle: "Priorité", type: "select", options: [["BASSE", "Basse"], ["NORMALE", "Normale"], ["HAUTE", "Haute"], ["URGENTE", "Urgente"]].map(([v, l]) => ({ v, l })) },
            { k: "fournisseur", libelle: "Fournisseur", type: "select", options: optFournisseurs },
            { k: "cout_estime", libelle: "Coût estimé (devis)", type: "nombre" },
            { k: "date_prevue", libelle: "Date prévue", type: "date" },
            { k: "description", libelle: "Détails", type: "zone" },
          ]} />
      )}
      {form === "plan" && (
        <FormModale titre="Nouveau plan d'entretien" onFermer={() => setForm(null)} onFait={() => { notifier("Plan enregistré"); plans.recharger(); }}
          envoyer={(c) => api("plans-maintenance/", { methode: "POST", corps: c })} initial={{ periodicite_mois: 6 }}
          champs={[
            { k: "bien", libelle: "Bien", type: "select", options: optionsBiens(biens), requis: true, large: true },
            { k: "libelle", libelle: "Entretien", requis: true, large: true, exemple: "Vidange de la pompe et analyse de l'eau" },
            { k: "periodicite_mois", libelle: "Tous les … mois", type: "nombre", requis: true },
            { k: "prochaine_date", libelle: "Prochaine date", type: "date", requis: true },
            { k: "fournisseur", libelle: "Fournisseur", type: "select", options: optFournisseurs },
            { k: "cout_estime", libelle: "Coût estimé", type: "nombre" },
          ]} />
      )}
      {form === "fournisseur" && (
        <FormModale titre="Nouveau fournisseur" onFermer={() => setForm(null)} onFait={() => { notifier("Fournisseur enregistré"); fournisseurs.recharger(); }}
          envoyer={(c) => api("fournisseurs/", { methode: "POST", corps: c })}
          champs={[
            { k: "nom", libelle: "Nom", requis: true }, { k: "specialite", libelle: "Spécialité", exemple: "Forages, toiture, mécanique…" },
            { k: "telephone", libelle: "Téléphone" }, { k: "email", libelle: "E-mail" }, { k: "note", libelle: "Remarques", type: "zone" },
          ]} />
      )}
      {aTerminer && (
        <FormModale titre={`Terminer OT-${aTerminer.id}`} description="Le travail entre dans l'historique du bien. La dépense peut être enregistrée dans les finances."
          onFermer={() => setATerminer(null)} onFait={() => { notifier("Ordre de travail terminé"); ordres.recharger(); }} bouton="Clore l'ordre"
          envoyer={(c) => api(`ordres-travail/${aTerminer.id}/terminer/`, { methode: "POST", corps: c })}
          initial={{ cout_reel: Number(aTerminer.cout_estime) || "", enregistrer_depense: peut("finances"), date: new Date().toISOString().slice(0, 10) }}
          champs={[
            { k: "cout_reel", libelle: "Coût réel", type: "nombre" },
            { k: "date", libelle: "Date de fin", type: "date" },
            { k: "rapport", libelle: "Ce qui a été fait", type: "zone" },
            { k: "enregistrer_depense", libelle: "Enregistrer la dépense dans les finances", type: "case", cache: () => !peut("finances") },
          ]} />
      )}
    </>
  );
}
