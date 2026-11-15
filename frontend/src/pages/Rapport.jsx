import { useEffect, useState } from "react";
import { Printer } from "lucide-react";
import { tout } from "../api";
import { useAuth } from "../auth";
import { Bandeau, EnTete, Squelette, useApi } from "../components/ui";
import { bif, nombre, devise } from "../format";

// Rapport officiel du patrimoine, mis en page pour l'impression A4 (ou « Enregistrer en PDF »).
export default function Rapport() {
  const { moi } = useAuth();
  // Le surintendant obtient le rapport de son district ; la direction choisit un district ou l'ensemble
  const [district, setDistrict] = useState(moi.voit_tout ? "" : String(moi.district || ""));
  const filtre = district ? `district=${district}` : "";
  const { donnees: districts } = useApi("districts/");
  const { donnees: d, erreur } = useApi(`tableau-de-bord/?${filtre}`);
  const projets = useApi(`projets/?${filtre}`);
  const [biens, setBiens] = useState(null);
  useEffect(() => {
    setBiens(null);
    tout(`biens/?ordering=code&${filtre}`).then(setBiens).catch(() => setBiens([]));
  }, [filtre]);
  const nomDistrict = districts?.find((x) => String(x.id) === district)?.nom;
  const jour = new Date().toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" });

  if (erreur) return <Bandeau type="erreur">{erreur}</Bandeau>;
  const pret = d && biens && projets.donnees;
  const sansTitre = biens?.filter((b) => b.categorie === "FON" && b.statut_juridique !== "TITRE") || [];

  return (
    <>
      <div className="ne-pas-imprimer">
        <EnTete titre="Rapport du patrimoine" sousTitre="Document de synthèse à présenter au comité exécutif ou à la Conférence Annuelle. Utilisez « Enregistrer en PDF » dans la fenêtre d'impression pour obtenir un fichier.">
          {moi.voit_tout && (
            <select className="saisie-ui" value={district} onChange={(e) => setDistrict(e.target.value)} aria-label="Périmètre du rapport">
              <option value="">Toute l'organisation</option>
              {districts?.map((x) => <option key={x.id} value={x.id}>Rapport du district de {x.nom}</option>)}
            </select>
          )}
          <button className="bouton principal" onClick={() => window.print()} disabled={!pret}><Printer />Imprimer ou enregistrer en PDF</button>
        </EnTete>
      </div>

      {!pret ? <Squelette lignes={12} hauteur={18} /> : (
        <article className="rapport">
          <header className="rapport-tete">
            <div style={{ display: "flex", gap: 14, alignItems: "center" }}>
              <img src="/logo.svg" alt="" />
              <div>
                <div style={{ fontSize: 12, color: "#47574e" }}>{moi.organisation?.nom}</div>
                <h1>Rapport du patrimoine{nomDistrict || (!moi.voit_tout && moi.district_nom) ? ` — district de ${nomDistrict || moi.district_nom}` : ""}</h1>
              </div>
            </div>
            <div style={{ textAlign: "right", fontSize: 12, color: "#47574e" }}>
              <div>Situation au {jour}</div>
              <div>Établi par : {moi.nom}</div>
              <div>Plateforme UMURAGE</div>
            </div>
          </header>

          <div className="chiffres">
            <div><b>{(d.kpi.valeur_totale / 1e9).toLocaleString("fr-FR", { maximumFractionDigits: 2 })} Md</b><span>Valeur estimée ({devise()})</span></div>
            <div><b>{d.kpi.nb_biens}</b><span>Biens recensés</span></div>
            <div><b>{d.kpi.sans_titre} / {d.kpi.terrains}</b><span>Terrains sans titre définitif</span></div>
            <div><b>{d.kpi.risque_eleve}</b><span>Biens à risque élevé</span></div>
          </div>

          <h2>1. Répartition par district</h2>
          <table>
            <thead><tr><th>District</th><th className="num">Biens</th><th className="num">Valeur estimée</th><th className="num">Part</th><th className="num">À risque</th><th className="num">Sans titre</th></tr></thead>
            <tbody>
              {d.par_district.map((x) => (
                <tr key={x.district}>
                  <td>{x.district}</td><td className="num">{x.nombre}</td><td className="num">{bif(x.valeur)}</td>
                  <td className="num">{Math.round((100 * x.valeur) / (d.kpi.valeur_totale || 1))} %</td>
                  <td className="num">{x.a_risque}</td><td className="num">{x.sans_titre}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <h2>2. Points d'attention</h2>
          <p style={{ marginBottom: 8 }}><b>Terrains à régulariser.</b> {sansTitre.length ? `${sansTitre.length} terrains n'ont pas de titre définitif :` : "Tous les terrains sont titrés."}</p>
          {sansTitre.length > 0 && (
            <table style={{ marginBottom: 14 }}>
              <tbody>
                {sansTitre.map((b) => <tr key={b.id}><td>{b.code}</td><td>{b.nom}</td><td>{b.district_nom}</td><td>{b.juridique_libelle}</td></tr>)}
              </tbody>
            </table>
          )}
          <p style={{ marginBottom: 8 }}><b>Biens qui demandent une intervention</b> (score de risque de 50 ou plus) :</p>
          <table>
            <tbody>
              {d.biens_a_risque.map((b) => <tr key={b.id}><td>{b.code}</td><td>{b.nom}</td><td>{b.district_nom}</td><td className="num">{Math.round(b.score_risque)} / 100</td></tr>)}
            </tbody>
          </table>
          <p style={{ marginTop: 10 }}>
            <b>Contrôle financier.</b> {d.kpi.anomalies} transaction(s) signalée(s) par la détection d'anomalies restent à vérifier.
            {" "}<b>Capteurs.</b> {d.kpi.alertes} alerte(s) ouverte(s).
          </p>

          <h2>3. Projets</h2>
          <table>
            <thead><tr><th>Projet</th><th>District</th><th>Statut</th><th className="num">Avancement</th><th className="num">Budget</th><th className="num">Dépensé</th></tr></thead>
            <tbody>
              {projets.donnees.map((p) => (
                <tr key={p.id}><td>{p.nom}</td><td>{p.district_nom}</td><td>{p.statut_libelle}</td><td className="num">{p.avancement} %</td><td className="num">{bif(p.budget, true)}</td><td className="num">{bif(p.depense, true)}</td></tr>
              ))}
            </tbody>
          </table>

          <h2>4. Contribution aux Objectifs de Développement Durable</h2>
          <table>
            <thead><tr><th>Objectif</th><th className="num">Biens</th><th className="num">Projets</th><th className="num">Bénéficiaires</th></tr></thead>
            <tbody>
              {d.impact_odd.map((o) => <tr key={o.odd}><td>{o.libelle}</td><td className="num">{o.biens}</td><td className="num">{o.projets}</td><td className="num">{nombre(o.beneficiaires)}</td></tr>)}
            </tbody>
          </table>

          <h2>5. Inventaire détaillé</h2>
          <table>
            <thead><tr><th>Code</th><th>Bien</th><th>District</th><th>État</th><th className="num">Valeur estimée</th></tr></thead>
            <tbody>
              {biens.map((b) => (
                <tr key={b.id}><td style={{ whiteSpace: "nowrap" }}>{b.code}</td><td>{b.nom}</td><td>{b.district_nom}</td><td>{b.etat_libelle}</td><td className="num">{bif(b.valeur_courante)}</td></tr>
              ))}
            </tbody>
          </table>

          <p className="note">
            Les valeurs sont des estimations produites par les modèles de valorisation d'UMURAGE (comparables du marché pour les terrains et
            bâtiments, amortissement pour les équipements). Version de démonstration : les montants, surfaces et transactions sont fictifs.
          </p>
        </article>
      )}
    </>
  );
}
