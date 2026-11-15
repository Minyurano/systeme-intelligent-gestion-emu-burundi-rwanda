import { useState } from "react";
import { AlertTriangle, Coins, FileCode2, FolderKanban, HandHeart, Percent } from "lucide-react";
import { telecharger } from "../api";
import { Carte, EnTete, Etat, Kpi, Progres, Segments, useApi, Vide } from "../components/ui";
import { bif, nombre, devise } from "../format";

const DOMAINES = {
  SANTE: "Santé", EDUCATION: "Éducation", EAU: "Eau potable", AGRICULTURE: "Agriculture",
  FEMMES: "Femmes", HUMANITAIRE: "Humanitaire", INCLUSION: "Inclusion",
};
const TON = { EN_COURS: "info", TERMINE: "bon", PREVU: "", SUSPENDU: "critique" };

export default function Projets() {
  const [domaine, setDomaine] = useState("");
  const { donnees: tous, erreur, chargement } = useApi("projets/");
  const donnees = tous?.filter((p) => !domaine || p.domaine === domaine);
  const totalBudget = donnees?.reduce((s, p) => s + Number(p.budget), 0) || 0;
  const totalDep = donnees?.reduce((s, p) => s + Number(p.depense), 0) || 0;
  const benef = donnees?.reduce((s, p) => s + p.beneficiaires, 0) || 0;
  const enAvance = donnees?.filter((p) => p.taux_execution != null && p.taux_execution > p.avancement + 15).length || 0;
  const domainesPresents = Object.entries(DOMAINES).filter(([k]) => tous?.some((p) => p.domaine === k));

  return (
    <>
      <EnTete titre="Projets et impact" sousTitre="Chantiers et programmes de l'Église : avancement, budget consommé, bénéficiaires et contribution aux Objectifs de Développement Durable.">
        <button className="bouton" onClick={() => telecharger("export/iati/", "projets_iati.xml")} title="Format standard de transparence de l'aide internationale, lu par les bailleurs">
          <FileCode2 />Exporter au format IATI
        </button>
      </EnTete>
      <Etat chargement={chargement && !tous} erreur={erreur} lignes={8}>
        {donnees && (
          <div className="pile">
            <div className="kpis">
              <Kpi libelle="Projets" icone={FolderKanban} valeur={donnees.length} note={`${donnees.filter((p) => p.statut === "EN_COURS").length} en cours`} />
              <Kpi libelle="Budget total" icone={Coins} valeur={bif(totalBudget, true).replace(` ${devise()}`, "")} unite={devise()} note={`${bif(totalDep, true)} dépensés`} />
              <Kpi libelle="Budget consommé" icone={Percent} ton="info" valeur={`${totalBudget ? Math.round((100 * totalDep) / totalBudget) : 0} %`} note="Dépenses sur budget" />
              <Kpi libelle="Bénéficiaires visés" icone={HandHeart} ton="bon" valeur={nombre(benef)} note="Personnes touchées par les projets" />
            </div>

            <Carte brut titre="Portefeuille de projets" description={enAvance ? `${enAvance} projet(s) consomment leur budget plus vite que les travaux n'avancent.` : "Les dépenses suivent l'avancement des travaux."}
              actions={<Segments label="Domaine" valeur={domaine} onChange={setDomaine} options={[{ id: "", libelle: "Tous" }, ...domainesPresents.map(([k, v]) => ({ id: k, libelle: v }))]} />}>
              <div style={{ height: 12 }} />
              {donnees.length === 0 ? <Vide titre="Aucun projet dans ce domaine" /> : (
                <div className="defilement">
                  <table className="tableau">
                    <thead>
                      <tr><th>Projet</th><th>Statut</th><th style={{ minWidth: 160 }}>Avancement</th><th className="num">Budget</th><th className="num">Dépensé</th><th className="num masquer-mobile">Bénéficiaires</th><th className="masquer-mobile">Financeur</th></tr>
                    </thead>
                    <tbody>
                      {donnees.map((p) => {
                        const ecart = p.taux_execution != null && p.taux_execution > p.avancement + 15;
                        return (
                          <tr key={p.id}>
                            <td><div className="principal-cell">{p.nom}</div><div className="secondaire">{p.domaine_libelle}, {p.district_nom}</div></td>
                            <td><span className={`badge ${TON[p.statut]}`}>{p.statut_libelle}</span></td>
                            <td><Progres valeur={p.avancement} /></td>
                            <td className="num chiffre">{bif(p.budget, true)}</td>
                            <td className="num chiffre">
                              {bif(p.depense, true)}
                              <div className="secondaire" style={ecart ? { color: "var(--sorgho)", fontWeight: 600 } : undefined}>
                                {ecart && <AlertTriangle size={12} style={{ display: "inline", verticalAlign: -1, marginRight: 4 }} />}
                                {p.taux_execution ?? 0} % du budget
                              </div>
                            </td>
                            <td className="num chiffre masquer-mobile">{nombre(p.beneficiaires)}</td>
                            <td className="masquer-mobile">{p.financeur || <span className="muet">—</span>}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </Carte>
          </div>
        )}
      </Etat>
    </>
  );
}
