import { useState } from "react";
import { Link } from "react-router-dom";
import { AlarmClock, CalendarCheck2, CalendarClock, Check, FileWarning, Plus } from "lucide-react";
import { api } from "../api";
import { useAuth } from "../auth";
import { Carte, EnTete, Etat, Kpi, Onglets, useApi, useToast, Vide } from "../components/ui";
import { agir, FormModale, joursRestants, optionsBiens, useBiens } from "../components/metier";
import { bif, date } from "../format";

const TYPES = {
  ASSURANCE: "Assurance", IMPOT: "Impôt foncier / taxe", TITRE: "Titre de propriété", CONTROLE: "Contrôle technique",
  FIN_BAIL: "Fin de bail", MAINTENANCE: "Maintenance prévue", DOCUMENT: "Document qui expire", AUTRE: "Autre",
};

export default function Echeancier() {
  const { peut } = useAuth();
  const notifier = useToast();
  const [onglet, setOnglet] = useState("echeances");
  const [ajout, setAjout] = useState(false);
  const { donnees, erreur, chargement, recharger } = useApi("echeances/?statut=A_FAIRE");
  const { donnees: docs } = useApi("documents-manquants/");
  const { donnees: districts } = useApi("districts/");
  const biens = useBiens();
  const liste = donnees || [];
  const retard = liste.filter((e) => e.jours_restants < 0);
  const semaine = liste.filter((e) => e.jours_restants >= 0 && e.jours_restants <= 7);
  const mois = liste.filter((e) => e.jours_restants > 7 && e.jours_restants <= 30);
  const plusTard = liste.filter((e) => e.jours_restants > 30);
  const peutEcrire = peut("projets") || peut("finances") || peut("declarations");

  async function faite(e) {
    const r = await agir(`echeances/${e.id}/faite/`, {}, notifier, "Échéance marquée comme faite");
    if (r?.suivante) notifier(`Prochaine échéance créée pour le ${date(r.suivante.date)}`);
    recharger();
  }

  const Groupe = ({ titre, items, ton }) => items.length > 0 && (
    <Carte brut titre={titre} description={`${items.length} échéance(s)`}>
      <div className="defilement"><table className="tableau">
        <thead><tr><th>Échéance</th><th>Date</th><th>Concerne</th><th className="num">Montant</th><th>Rappels</th><th /></tr></thead>
        <tbody>{items.map((e) => (
          <tr key={e.id}>
            <td><div className="principal-cell">{e.libelle}</div><div className="secondaire">{e.type_libelle}{e.periodicite_mois ? ` · tous les ${e.periodicite_mois} mois` : ""}{e.responsable_nom ? ` · ${e.responsable_nom}` : ""}</div></td>
            <td><div>{date(e.date)}</div><span className={`badge ${ton}`}>{joursRestants(e.jours_restants)}</span></td>
            <td>{e.bien_code ? `${e.bien_code} · ${e.bien_nom}` : e.district_nom || "Toute l'organisation"}</td>
            <td className="num chiffre">{Number(e.montant) ? bif(e.montant, true) : "—"}</td>
            <td className="secondaire">{[e.rappel_j30 && "J-30", e.rappel_j7 && "J-7", e.rappel_retard && "retard"].filter(Boolean).join(", ") || "—"}</td>
            <td>{peutEcrire && <button className="bouton petit" onClick={() => faite(e)}><Check />Fait</button>}</td>
          </tr>
        ))}</tbody>
      </table></div>
    </Carte>
  );

  return (
    <>
      <EnTete titre="Échéancier" sousTitre="Assurances, impôts, titres, contrôles, fins de bail, documents qui expirent : les rappels partent automatiquement par WhatsApp 30 jours puis 7 jours avant, au bon responsable.">
        {peutEcrire && <button className="bouton principal" onClick={() => setAjout(true)}><Plus />Nouvelle échéance</button>}
      </EnTete>
      <Etat chargement={chargement && !donnees} erreur={erreur}>
        <div className="pile">
          <div className="kpis">
            <Kpi libelle="En retard" icone={AlarmClock} ton={retard.length ? "critique" : "bon"} valeur={retard.length} />
            <Kpi libelle="Cette semaine" icone={CalendarClock} ton={semaine.length ? "attention" : ""} valeur={semaine.length} />
            <Kpi libelle="Dans les 30 jours" icone={CalendarCheck2} ton="info" valeur={mois.length} />
            <Kpi libelle="Documents manquants" icone={FileWarning} ton={docs?.manquants?.length ? "attention" : "bon"} valeur={docs?.manquants?.length ?? "…"} note="Titres, cartes grises, assurances" />
          </div>
          <Onglets actif={onglet} onChange={setOnglet} onglets={[
            { id: "echeances", libelle: "Échéances", nb: liste.length }, { id: "documents", libelle: "Documents obligatoires", nb: docs?.manquants?.length },
          ]} />
          {onglet === "echeances" ? (
            liste.length === 0 ? <Vide titre="Aucune échéance à venir" /> : (
              <>
                <Groupe titre="En retard" items={retard} ton="critique" />
                <Groupe titre="Cette semaine" items={semaine} ton="attention" />
                <Groupe titre="Dans les 30 jours" items={mois} ton="info" />
                <Groupe titre="Plus tard" items={plusTard} ton="" />
              </>
            )
          ) : (
            <>
              <Carte brut titre="Pièces exigées absentes du dossier" description="Titre foncier pour un terrain titré, carte grise et assurance pour un véhicule, assurance pour un bâtiment de grande valeur.">
                {!docs?.manquants?.length ? <Vide titre="Tous les dossiers sont complets" /> : (
                  <div className="defilement"><table className="tableau">
                    <thead><tr><th>Bien</th><th>District</th><th>Pièce manquante</th></tr></thead>
                    <tbody>{docs.manquants.map((m, i) => (
                      <tr key={i}><td><Link to={`/biens/${m.bien}`}>{m.code}</Link> · {m.nom}</td><td>{m.district}</td><td><span className="badge attention">{m.libelle}</span></td></tr>
                    ))}</tbody>
                  </table></div>
                )}
              </Carte>
              <Carte brut titre="Documents qui expirent dans les 60 jours">
                {!docs?.expirent_bientot?.length ? <Vide titre="Aucun document n'expire bientôt" /> : (
                  <table className="tableau"><tbody>{docs.expirent_bientot.map((d) => (
                    <tr key={d.id}><td>{d.titre}</td><td>{d.type}</td><td>{date(d.date_expiration)}</td></tr>
                  ))}</tbody></table>
                )}
              </Carte>
            </>
          )}
        </div>
      </Etat>
      {ajout && (
        <FormModale titre="Nouvelle échéance" onFermer={() => setAjout(false)} onFait={() => { notifier("Échéance enregistrée"); recharger(); }}
          envoyer={(c) => api("echeances/", { methode: "POST", corps: c })} initial={{ type: "ASSURANCE", periodicite_mois: 12 }}
          champs={[
            { k: "libelle", libelle: "Libellé", requis: true, large: true, exemple: "Assurance incendie du centre de santé" },
            { k: "type", libelle: "Type", type: "select", options: Object.entries(TYPES).map(([v, l]) => ({ v, l })) },
            { k: "date", libelle: "Date", type: "date", requis: true },
            { k: "periodicite_mois", libelle: "Se répète tous les … mois", type: "nombre", aide: "0 = une seule fois" },
            { k: "montant", libelle: "Montant prévu", type: "nombre" },
            { k: "bien", libelle: "Bien concerné", type: "select", options: optionsBiens(biens) },
            { k: "district", libelle: "District", type: "select", options: [{ v: "", l: "Toute l'organisation" }, ...(districts || []).map((x) => ({ v: x.id, l: x.nom }))] },
          ]} />
      )}
    </>
  );
}
