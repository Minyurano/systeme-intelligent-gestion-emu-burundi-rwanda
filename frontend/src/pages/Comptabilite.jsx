import { useRef, useState } from "react";
import { BookLock, Download, FileSpreadsheet, Landmark, Lock, Plus, Scale, Upload } from "lucide-react";
import { api, telecharger } from "../api";
import { useAuth } from "../auth";
import { Bandeau, Carte, EnTete, Etat, Kpi, Onglets, Progres, useApi, useToast, Vide } from "../components/ui";
import { FormModale } from "../components/metier";
import { bif, date, dateHeure } from "../format";

const CATEGORIES = {
  DIME: "Dîmes et offrandes", DON: "Don", SUBVENTION: "Subvention partenaire", REVENU_PROJET: "Revenu de projet", LOYER: "Loyers perçus",
  CESSION: "Produit de cession", SALAIRE: "Salaires", MAINTENANCE: "Maintenance", CONSTRUCTION: "Construction",
  FONCTIONNEMENT: "Fonctionnement", ACHAT: "Achat de matériel",
};
const anneeCourante = new Date().getFullYear();

export default function Comptabilite() {
  const { peut } = useAuth();
  const [onglet, setOnglet] = useState("budget");
  const [annee, setAnnee] = useState(anneeCourante);
  const choixAnnee = (
    <select className="saisie-ui" value={annee} onChange={(e) => setAnnee(Number(e.target.value))} aria-label="Exercice">
      {[0, 1, 2, 3].map((i) => <option key={i} value={anneeCourante - i}>{anneeCourante - i}</option>)}
    </select>
  );
  return (
    <>
      <EnTete titre="Comptabilité du patrimoine" sousTitre="Budget comparé au réalisé, registre des immobilisations et amortissements, rapprochement bancaire et clôture des exercices.">
        {choixAnnee}
      </EnTete>
      <div className="pile">
        <Onglets actif={onglet} onChange={setOnglet} onglets={[
          { id: "budget", libelle: "Budget et réalisé", icone: Scale }, { id: "registre", libelle: "Registre des immobilisations", icone: Landmark },
          { id: "rapprochement", libelle: "Rapprochement bancaire", icone: FileSpreadsheet }, { id: "clotures", libelle: "Clôture des exercices", icone: BookLock },
        ]} />
        {onglet === "budget" && <Budget annee={annee} ecrire={peut("finances")} />}
        {onglet === "registre" && <Registre annee={annee} />}
        {onglet === "rapprochement" && <Rapprochement ecrire={peut("finances")} />}
        {onglet === "clotures" && <Clotures ecrire={peut("finances")} />}
      </div>
    </>
  );
}

function Budget({ annee, ecrire }) {
  const notifier = useToast();
  const [ajout, setAjout] = useState(false);
  const { donnees: s, erreur, chargement, recharger } = useApi(`budgets/suivi/?annee=${annee}`, [annee]);
  return (
    <Etat chargement={chargement && !s} erreur={erreur}>
      {s && (
        <>
          <div className="kpis">
            <Kpi libelle="Dépenses / budget" icone={Scale} ton={s.total_realise_depenses > s.total_prevu_depenses && s.total_prevu_depenses ? "critique" : "info"}
              valeur={s.total_prevu_depenses ? `${Math.round((100 * s.total_realise_depenses) / s.total_prevu_depenses)} %` : "—"}
              note={`${bif(s.total_realise_depenses, true)} sur ${bif(s.total_prevu_depenses, true)}`} />
            <Kpi libelle="Recettes / budget" icone={Landmark} ton="bon"
              valeur={s.total_prevu_recettes ? `${Math.round((100 * s.total_realise_recettes) / s.total_prevu_recettes)} %` : "—"}
              note={`${bif(s.total_realise_recettes, true)} sur ${bif(s.total_prevu_recettes, true)}`} />
            <Kpi libelle="Dépenses sans pièce justificative" icone={FileSpreadsheet} ton={s.depenses_sans_piece.nombre ? "attention" : "bon"}
              valeur={s.depenses_sans_piece.nombre} note={`Au-delà de ${bif(s.depenses_sans_piece.seuil, true)}`} />
            <Kpi libelle="Transactions non rapprochées" icone={Upload} valeur={s.non_rapprochees} note="Banque et Mobile Money" />
          </div>
          <Carte brut titre={`Budget ${annee}`} actions={ecrire && <button className="bouton" onClick={() => setAjout(true)}><Plus />Ligne de budget</button>}>
            {s.lignes.length === 0 ? <Vide titre="Aucun budget pour cet exercice" texte="Ajoutez les lignes votées par le conseil." /> : (
              <div className="defilement"><table className="tableau">
                <thead><tr><th>Poste</th><th>Périmètre</th><th className="num">Prévu</th><th className="num">Réalisé</th><th style={{ minWidth: 150 }}>Exécution</th></tr></thead>
                <tbody>{s.lignes.map((l) => (
                  <tr key={l.id}>
                    <td><div className="principal-cell">{l.categorie_libelle}</div><div className="secondaire">{l.sens === "DEPENSE" ? "Dépense" : "Recette"}</div></td>
                    <td>{l.district}{l.projet ? ` · ${l.projet}` : ""}</td>
                    <td className="num chiffre">{bif(l.prevu, true)}</td>
                    <td className="num chiffre">{bif(l.realise, true)}{l.alerte && <div><span className="badge critique">dépassement</span></div>}</td>
                    <td><Progres valeur={Math.min(100, l.taux ?? 0)} couleur={l.alerte ? "var(--critique)" : undefined} />{(l.taux ?? 0) > 100 && <span className="secondaire">{l.taux} % du budget</span>}</td>
                  </tr>
                ))}</tbody>
              </table></div>
            )}
          </Carte>
          {s.hors_budget.length > 0 && (
            <Carte brut titre="Mouvements hors budget" description="Catégories qui ont des transactions mais aucune ligne de budget.">
              <table className="tableau"><tbody>{s.hors_budget.map((h, i) => (
                <tr key={i}><td>{h.categorie_libelle}</td><td>{h.sens === "DEPENSE" ? "Dépense" : "Recette"}</td><td className="num chiffre">{bif(h.realise, true)}</td></tr>
              ))}</tbody></table>
            </Carte>
          )}
          {s.depenses_sans_piece.exemples.length > 0 && (
            <Carte brut titre="Dépenses importantes sans pièce justificative" description="Joignez la facture depuis la fiche du bien ou la rubrique Documents.">
              <table className="tableau"><tbody>{s.depenses_sans_piece.exemples.map((t) => (
                <tr key={t.id}><td>{date(t.date)}</td><td>{t.tiers || t.description}</td><td className="num chiffre">{bif(t.montant_bif)}</td></tr>
              ))}</tbody></table>
            </Carte>
          )}
          {ajout && (
            <FormModale titre="Ligne de budget" onFermer={() => setAjout(false)} onFait={() => { notifier("Ligne ajoutée"); recharger(); }}
              envoyer={(c) => api("budgets/", { methode: "POST", corps: { ...c, annee } })} initial={{ sens: "DEPENSE", categorie: "MAINTENANCE" }}
              champs={[
                { k: "sens", libelle: "Sens", type: "select", options: [{ v: "DEPENSE", l: "Dépense" }, { v: "RECETTE", l: "Recette" }] },
                { k: "categorie", libelle: "Catégorie", type: "select", options: Object.entries(CATEGORIES).map(([v, l]) => ({ v, l })) },
                { k: "montant", libelle: "Montant voté", type: "nombre", requis: true },
              ]} />
          )}
        </>
      )}
    </Etat>
  );
}

function Registre({ annee }) {
  const { donnees: r, erreur, chargement } = useApi(`compta/registre/?annee=${annee}`, [annee]);
  return (
    <Etat chargement={chargement && !r} erreur={erreur}>
      {r && (
        <>
          <div className="kpis">
            <Kpi libelle="Valeur d'origine" icone={Landmark} valeur={bif(r.totaux.valeur_origine, true)} />
            <Kpi libelle={`Dotation ${annee}`} icone={Scale} ton="info" valeur={bif(r.totaux.dotation_exercice, true)} note="Amortissement de l'exercice" />
            <Kpi libelle="Amortissements cumulés" icone={BookLock} valeur={bif(r.totaux.amortissements_cumules, true)} />
            <Kpi libelle="Valeur nette comptable" icone={Landmark} ton="bon" valeur={bif(r.totaux.valeur_nette_comptable, true)} note={`${r.non_amortissables} bien(s) non amortissable(s)`} />
          </div>
          <Carte brut titre={`Registre des immobilisations ${annee}`} description="Amortissement linéaire au prorata des mois de détention. Les terrains ne s'amortissent pas. Durées à valider par l'expert-comptable."
            actions={<button className="bouton" onClick={() => telecharger(`compta/registre/?annee=${annee}&export=csv`, `registre_immobilisations_${annee}.csv`)}><Download />Exporter (Excel)</button>}>
            <div className="defilement"><table className="tableau">
              <thead><tr><th>Bien</th><th>Acquis le</th><th className="num">Valeur d'origine</th><th className="num">Durée</th><th className="num">Dotation</th><th className="num">Cumul</th><th className="num">VNC</th></tr></thead>
              <tbody>{r.lignes.map((l) => (
                <tr key={l.id}>
                  <td><div className="principal-cell">{l.code}</div><div className="secondaire">{l.nom}{l.sorti_le ? ` · sorti le ${date(l.sorti_le)}` : ""}</div></td>
                  <td>{date(l.date_acquisition)}</td>
                  <td className="num chiffre">{bif(l.valeur_origine, true)}</td>
                  <td className="num">{l.duree_ans ? `${l.duree_ans} ans` : <span className="muet">—</span>}</td>
                  <td className="num chiffre">{l.amortissable ? bif(l.dotation_exercice, true) : "—"}</td>
                  <td className="num chiffre">{l.amortissable ? bif(l.amortissements_cumules, true) : "—"}</td>
                  <td className="num chiffre">{bif(l.valeur_nette_comptable, true)}</td>
                </tr>
              ))}</tbody>
            </table></div>
          </Carte>
        </>
      )}
    </Etat>
  );
}

function Rapprochement({ ecrire }) {
  const notifier = useToast();
  const champ = useRef(null);
  const [res, setRes] = useState(null);
  async function envoyer(fichier) {
    const fd = new FormData();
    fd.append("fichier", fichier);
    try {
      setRes(await api("compta/rapprochement/", { methode: "POST", corps: fd }));
      notifier("Relevé analysé");
    } catch (e) { notifier(e.message, "erreur"); }
  }
  return (
    <Carte titre="Rapprochement avec le relevé bancaire ou Mobile Money"
      description="Exportez le relevé en CSV (colonnes date, montant, référence). Chaque ligne est associée à la transaction de même référence, ou de même montant à 3 jours près.">
      {ecrire ? (
        <>
          <input ref={champ} type="file" accept=".csv,text/csv" hidden onChange={(e) => e.target.files[0] && envoyer(e.target.files[0])} />
          <button className="bouton principal" onClick={() => champ.current.click()}><Upload />Importer un relevé CSV</button>
        </>
      ) : <Bandeau>Réservé à la trésorerie.</Bandeau>}
      {res && (
        <div className="pile" style={{ marginTop: 16 }}>
          <Bandeau type={res.lignes_sans_correspondance.length ? "attention" : "succes"}>
            {res.rapprochees} ligne(s) rapprochée(s), {res.lignes_sans_correspondance.length} sans correspondance dans UMURAGE.
          </Bandeau>
          {res.lignes_sans_correspondance.length > 0 && (
            <table className="tableau"><thead><tr><th>Date</th><th className="num">Montant</th><th>Référence</th><th>Libellé</th></tr></thead>
              <tbody>{res.lignes_sans_correspondance.map((l, i) => (
                <tr key={i}><td>{date(l.date)}</td><td className="num chiffre">{bif(l.montant)}</td><td>{l.reference}</td><td>{l.libelle}</td></tr>
              ))}</tbody></table>
          )}
        </div>
      )}
    </Carte>
  );
}

function Clotures({ ecrire }) {
  const notifier = useToast();
  const { donnees, recharger } = useApi("clotures/");
  const [ajout, setAjout] = useState(false);
  return (
    <Carte brut titre="Exercices clôturés" description="Après clôture, aucune transaction de l'année ne peut plus être créée, modifiée ni supprimée. Les totaux sont figés dans le journal d'audit."
      actions={ecrire && <button className="bouton" onClick={() => setAjout(true)}><Lock />Clôturer un exercice</button>}>
      {!donnees?.length ? <Vide titre="Aucun exercice clôturé" /> : (
        <table className="tableau"><thead><tr><th>Exercice</th><th className="num">Recettes</th><th className="num">Dépenses</th><th className="num">VNC du patrimoine</th><th>Clôturé par</th></tr></thead>
          <tbody>{donnees.map((c) => (
            <tr key={c.id}><td><b>{c.annee}</b></td><td className="num chiffre">{bif(c.totaux.recettes, true)}</td><td className="num chiffre">{bif(c.totaux.depenses, true)}</td>
              <td className="num chiffre">{bif(c.totaux.valeur_nette_comptable, true)}</td><td>{c.cloture_par_nom}<div className="secondaire">{dateHeure(c.date)}</div></td></tr>
          ))}</tbody></table>
      )}
      {ajout && (
        <FormModale titre="Clôturer un exercice" description="Action définitive : vérifiez que toutes les transactions de l'année sont saisies et contrôlées."
          onFermer={() => setAjout(false)} onFait={() => { notifier("Exercice clôturé"); recharger(); }} bouton="Clôturer définitivement"
          envoyer={(c) => api("clotures/", { methode: "POST", corps: c })} initial={{ annee: anneeCourante - 1 }}
          champs={[{ k: "annee", libelle: "Exercice", type: "nombre", requis: true }]} />
      )}
    </Carte>
  );
}
