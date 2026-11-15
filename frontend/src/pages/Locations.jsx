import { useState } from "react";
import { Banknote, FileSignature, HandCoins, KeyRound, Plus, TriangleAlert } from "lucide-react";
import { api } from "../api";
import { useAuth } from "../auth";
import { Carte, EnTete, Etat, Kpi, Modale, useApi, useToast, Vide } from "../components/ui";
import { FormModale, optionsBiens, useBiens } from "../components/metier";
import { bif, date } from "../format";

const STATUT = { PAYE: ["bon", "Payé"], PARTIEL: ["attention", "Partiel"], IMPAYE: ["critique", "Impayé"], A_VENIR: ["", "À venir"] };
const mois = (p) => new Date(p).toLocaleDateString("fr-FR", { month: "long", year: "numeric" });

export default function Locations() {
  const { peut } = useAuth();
  const notifier = useToast();
  const [ajout, setAjout] = useState(false);
  const [bail, setBail] = useState(null);
  const { donnees, erreur, chargement, recharger } = useApi("baux/");
  const biens = useBiens();
  const baux = donnees || [];
  const actifs = baux.filter((b) => b.statut === "ACTIF");
  const mensuel = actifs.reduce((s, b) => s + Number(b.loyer_mensuel), 0);
  const impayes = baux.reduce((s, b) => s + b.impayes, 0);
  const encaisse = baux.reduce((s, b) => s + b.encaisse_annee, 0);
  const ecrire = peut("finances") || peut("projets");

  return (
    <>
      <EnTete titre="Locations et loyers" sousTitre="Boutiques, salles et terrains loués : les loyers de chaque mois sont générés automatiquement, chaque encaissement entre dans les finances, rattaché au bien.">
        {ecrire && <button className="bouton principal" onClick={() => setAjout(true)}><Plus />Nouveau bail</button>}
      </EnTete>
      <Etat chargement={chargement && !donnees} erreur={erreur}>
        <div className="pile">
          <div className="kpis">
            <Kpi libelle="Baux en cours" icone={KeyRound} valeur={actifs.length} />
            <Kpi libelle="Loyers attendus par mois" icone={Banknote} ton="info" valeur={bif(mensuel, true)} />
            <Kpi libelle="Encaissé cette année" icone={HandCoins} ton="bon" valeur={bif(encaisse, true)} />
            <Kpi libelle="Impayés" icone={TriangleAlert} ton={impayes ? "critique" : "bon"} valeur={bif(impayes, true)} note="Loyers échus non réglés" />
          </div>
          <Carte brut titre="Baux">
            {baux.length === 0 ? <Vide titre="Aucun bail enregistré" texte="Enregistrez les biens loués pour suivre les loyers." /> : (
              <div className="defilement"><table className="tableau">
                <thead><tr><th>Locataire</th><th>Bien</th><th className="num">Loyer mensuel</th><th>Période</th><th className="num">Impayés</th><th>Statut</th></tr></thead>
                <tbody>{baux.map((b) => (
                  <tr key={b.id} onClick={() => setBail(b)} style={{ cursor: "pointer" }}>
                    <td><div className="principal-cell">{b.locataire}</div><div className="secondaire">{b.objet}{b.telephone ? ` · ${b.telephone}` : ""}</div></td>
                    <td>{b.bien_code} · {b.bien_nom}<div className="secondaire">{b.district_nom}</div></td>
                    <td className="num chiffre">{bif(b.loyer_mensuel)}</td>
                    <td>{date(b.date_debut)} → {b.date_fin ? date(b.date_fin) : "sans fin"}</td>
                    <td className="num chiffre">{b.impayes ? <span className="badge critique">{bif(b.impayes, true)}</span> : "—"}</td>
                    <td><span className={`badge ${b.statut === "ACTIF" ? "bon" : ""}`}>{b.statut_libelle}</span></td>
                  </tr>
                ))}</tbody>
              </table></div>
            )}
          </Carte>
        </div>
      </Etat>
      {ajout && (
        <FormModale titre="Nouveau bail" description="Les loyers sont créés pour chaque mois depuis la date de début." onFermer={() => setAjout(false)}
          onFait={() => { notifier("Bail enregistré"); recharger(); }} envoyer={(c) => api("baux/", { methode: "POST", corps: c })}
          initial={{ jour_echeance: 5 }}
          champs={[
            { k: "bien", libelle: "Bien loué", type: "select", options: optionsBiens(biens), requis: true, large: true },
            { k: "locataire", libelle: "Locataire", requis: true },
            { k: "telephone", libelle: "Téléphone (rappels WhatsApp)", exemple: "+257…" },
            { k: "objet", libelle: "Objet", exemple: "Boutique n°2, salle de réception…" },
            { k: "loyer_mensuel", libelle: "Loyer mensuel", type: "nombre", requis: true },
            { k: "caution", libelle: "Caution", type: "nombre" },
            { k: "date_debut", libelle: "Début", type: "date", requis: true },
            { k: "date_fin", libelle: "Fin (facultatif)", type: "date" },
            { k: "jour_echeance", libelle: "Jour d'échéance du mois", type: "nombre" },
          ]} />
      )}
      {bail && <Loyers bail={bail} ecrire={ecrire} onFermer={() => { setBail(null); recharger(); }} />}
    </>
  );
}

function Loyers({ bail, ecrire, onFermer }) {
  const notifier = useToast();
  const { donnees, recharger } = useApi(`loyers/?bail=${bail.id}`);
  const [paiement, setPaiement] = useState(null);
  return (
    <Modale titre={bail.locataire} description={`${bail.bien_code} · ${bail.objet || bail.bien_nom} · ${bif(bail.loyer_mensuel)} par mois`} onFermer={onFermer} largeur={720}>
      {!donnees ? null : (
        <table className="tableau">
          <thead><tr><th>Mois</th><th>Échéance</th><th className="num">Dû</th><th className="num">Payé</th><th>Statut</th><th /></tr></thead>
          <tbody>{donnees.map((l) => (
            <tr key={l.id}>
              <td style={{ textTransform: "capitalize" }}>{mois(l.periode)}</td>
              <td>{date(l.echeance)}</td>
              <td className="num chiffre">{bif(l.montant_du)}</td>
              <td className="num chiffre">{Number(l.montant_paye) ? bif(l.montant_paye) : "—"}{l.paye_le && <div className="secondaire">{date(l.paye_le)}</div>}</td>
              <td><span className={`badge ${STATUT[l.statut][0]}`}>{STATUT[l.statut][1]}</span></td>
              <td>{ecrire && Number(l.reste) > 0 && <button className="bouton petit" onClick={() => setPaiement(l)}><FileSignature />Encaisser</button>}</td>
            </tr>
          ))}</tbody>
        </table>
      )}
      {paiement && (
        <FormModale titre={`Encaisser le loyer de ${mois(paiement.periode)}`} description="Une recette « Loyers perçus » est enregistrée dans les finances."
          onFermer={() => setPaiement(null)} onFait={() => { notifier("Paiement enregistré"); recharger(); }} bouton="Enregistrer le paiement"
          envoyer={(c) => api(`loyers/${paiement.id}/payer/`, { methode: "POST", corps: c })}
          initial={{ montant: Number(paiement.reste), canal: "MOBILE", date: new Date().toISOString().slice(0, 10) }}
          champs={[
            { k: "montant", libelle: "Montant reçu", type: "nombre", requis: true },
            { k: "date", libelle: "Date", type: "date" },
            { k: "canal", libelle: "Canal", type: "select", options: [{ v: "MOBILE", l: "Mobile Money" }, { v: "BANQUE", l: "Banque" }, { v: "ESPECES", l: "Espèces" }] },
            { k: "reference", libelle: "Référence (Lumicash, EcoCash, virement)" },
          ]} />
      )}
    </Modale>
  );
}
