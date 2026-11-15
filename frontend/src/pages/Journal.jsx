import { useState } from "react";
import { Fingerprint, Loader2, ScrollText, ShieldCheck, ShieldX } from "lucide-react";
import { api } from "../api";
import { Bandeau, Carte, EnTete, Etat, Pagination, Segments, useApi, Vide } from "../components/ui";
import { dateHeure } from "../format";

const TON = { CREATION: "bon", MODIFICATION: "info", SUPPRESSION: "critique" };
const LIBELLE = { CREATION: "Création", MODIFICATION: "Modification", SUPPRESSION: "Suppression" };

export default function Journal() {
  const [page, setPage] = useState(1);
  const [action, setAction] = useState("");
  const { donnees, erreur, chargement } = useApi(`journal/?page=${page}${action ? `&action=${action}` : ""}`);
  const [verif, setVerif] = useState(null);

  async function verifier() {
    setVerif({ encours: true });
    try {
      setVerif(await api("journal/verifier/"));
    } catch (e) {
      setVerif({ erreur: e.message });
    }
  }

  return (
    <>
      <EnTete titre="Journal d'audit" sousTitre="Toutes les créations, modifications et suppressions, avec leur auteur. Chaque entrée est scellée par l'empreinte SHA-256 de la précédente : une falsification après coup casse la chaîne et se voit.">
        <button className="bouton principal" onClick={verifier} disabled={verif?.encours}>
          {verif?.encours ? <Loader2 className="tourne" /> : <Fingerprint />}Vérifier l'intégrité
        </button>
      </EnTete>

      <div className="pile">
        {verif && !verif.encours && (
          verif.erreur ? <Bandeau type="erreur">{verif.erreur}</Bandeau>
            : verif.intact ? (
              <Bandeau type="succes"><b>Journal intact.</b> Les {verif.entrees} entrées sont authentiques et dans leur ordre d'origine.</Bandeau>
            ) : (
              <Bandeau type="erreur"><b>Journal altéré.</b> L'entrée n° {verif.premiere_entree_alteree} a été modifiée, ou une entrée a été supprimée.</Bandeau>
            )
        )}

        <Carte brut titre="Historique des actions"
          actions={<Segments label="Action" valeur={action} onChange={(a) => { setAction(a); setPage(1); }}
            options={[{ id: "", libelle: "Toutes" }, { id: "CREATION", libelle: "Créations" }, { id: "MODIFICATION", libelle: "Modifications" }, { id: "SUPPRESSION", libelle: "Suppressions" }]} />}
          pied={donnees?.count > 0 && <Pagination page={page} total={donnees.count} onChange={setPage} unite="entrées" />}>
          <div style={{ height: 12 }} />
          <Etat chargement={chargement && !donnees} erreur={erreur} lignes={8}>
            {donnees?.results.length === 0 ? (
              <Vide icone={ScrollText} titre="Aucune action enregistrée" texte="Chaque modification de l'inventaire, des projets ou des finances apparaîtra ici." />
            ) : (
              <div className="defilement">
                <table className="tableau">
                  <thead><tr><th>Date</th><th>Utilisateur</th><th>Action</th><th>Élément</th><th className="masquer-mobile">Changements</th><th className="masquer-mobile">Empreinte</th></tr></thead>
                  <tbody>
                    {donnees?.results.map((j) => (
                      <tr key={j.id}>
                        <td style={{ whiteSpace: "nowrap" }}>{dateHeure(j.date)}</td>
                        <td>{j.utilisateur || <span className="muet">Système</span>}</td>
                        <td><span className={`badge ${TON[j.action]}`}>{LIBELLE[j.action] || j.action}</span></td>
                        <td><div className="principal-cell">{j.objet_libelle}</div><div className="secondaire">{j.objet_type}</div></td>
                        <td className="masquer-mobile petit" style={{ color: "var(--encre-2)" }}>
                          {Object.entries(j.details || {}).map(([k, v]) => (
                            <div key={k}><b style={{ fontWeight: 600 }}>{k}</b> : {v.avant || "vide"} → {v.apres || "vide"}</div>
                          ))}
                        </td>
                        <td className="masquer-mobile"><span className="code" title={j.empreinte}>{j.empreinte?.slice(0, 12)}…</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Etat>
        </Carte>
        <p className="petit muet" style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {verif?.intact === false ? <ShieldX size={15} /> : <ShieldCheck size={15} />}
          Cette chaîne d'empreintes est la première brique d'un registre infalsifiable, qui pourra évoluer vers une blockchain de consortium.
        </p>
      </div>
    </>
  );
}
