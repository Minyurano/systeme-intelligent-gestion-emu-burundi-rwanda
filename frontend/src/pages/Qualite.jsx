import { Link } from "react-router-dom";
import { Trophy } from "lucide-react";
import { Carte, EnTete, Etat, Progres, useApi, Vide } from "../components/ui";

const couleur = (s) => (s >= 85 ? "var(--succes)" : s >= 65 ? "var(--sorgho)" : "var(--critique)");

function JaugeRonde({ valeur }) {
  const r = 56;
  const c = 2 * Math.PI * r;
  return (
    <div className="jauge-ronde" role="img" aria-label={`Score de qualité : ${valeur} sur 100`}>
      <svg width="132" height="132" viewBox="0 0 132 132">
        <circle cx="66" cy="66" r={r} fill="none" stroke="var(--surface-3)" strokeWidth="12" />
        <circle cx="66" cy="66" r={r} fill="none" stroke={couleur(valeur)} strokeWidth="12" strokeLinecap="round"
          strokeDasharray={`${(c * valeur) / 100} ${c}`} />
      </svg>
      <b className="chiffre">{valeur}</b>
    </div>
  );
}

// Des données fiables sont la condition d'une IA utile : cette page rend la qualité visible et motive les districts.
export default function Qualite() {
  const { donnees: d, erreur, chargement } = useApi("qualite/");
  return (
    <>
      <EnTete titre="Qualité des données"
        sousTitre="Un inventaire n'est utile que s'il est complet et à jour. Chaque district est noté sur la complétude de ses fiches : position GPS, valeur, responsable, photo, titre foncier et entretien récent." />
      <Etat chargement={chargement && !d} erreur={erreur} lignes={8}>
        {d && (
          <div className="pile">
            <div className="grille g-2-1">
              <Carte titre="Score de l'organisation" description="Moyenne des fiches, de 0 à 100">
                <div style={{ display: "flex", gap: 28, alignItems: "center", flexWrap: "wrap" }}>
                  <JaugeRonde valeur={d.score_global} />
                  <div style={{ flex: 1, minWidth: 240, display: "grid", gap: 10 }}>
                    {d.criteres.filter((c) => c.taux !== null).map((c) => (
                      <div key={c.id} style={{ display: "grid", gridTemplateColumns: "minmax(0, 46%) 1fr", gap: 12, alignItems: "center" }}>
                        <span className="petit">{c.libelle}</span>
                        <Progres valeur={c.taux} couleur={couleur(c.taux)} />
                      </div>
                    ))}
                  </div>
                </div>
              </Carte>
              <Carte titre="Comment progresser">
                <ul className="petit" style={{ margin: 0, paddingLeft: 18, display: "grid", gap: 8, color: "var(--encre-2)" }}>
                  <li>Ajoutez une <b>photo</b> à chaque bien : depuis WhatsApp, elle est jointe automatiquement.</li>
                  <li>Enregistrez chaque <b>entretien</b> dans l'historique du bien.</li>
                  <li>Lancez les démarches de <b>titre foncier</b> pour les terrains qui n'en ont pas.</li>
                  <li>Nommez un <b>responsable</b> pour chaque bien.</li>
                </ul>
              </Carte>
            </div>

            <Carte titre="Classement des districts" description="Mis à jour en temps réel. Le district le mieux tenu est mis à l'honneur à la Conférence Annuelle." plein>
              <div className="defilement">
                <table className="tableau">
                  <thead>
                    <tr><th style={{ width: 56 }}>Rang</th><th>District</th><th style={{ minWidth: 180 }}>Score</th><th className="num">Biens</th>
                      <th className="num masquer-mobile">GPS</th><th className="num masquer-mobile">Photo</th><th className="num masquer-mobile">Entretien</th>
                      <th className="num masquer-mobile">Titres</th><th className="num">Déclarations (30 j)</th></tr>
                  </thead>
                  <tbody>
                    {d.classement.map((c) => (
                      <tr key={c.district}>
                        <td><span className={`rang r${c.rang}`}>{c.rang === 1 ? <Trophy size={15} /> : c.rang}</span></td>
                        <td className="principal-cell">{c.district}</td>
                        <td><Progres valeur={c.score} couleur={couleur(c.score)} /></td>
                        <td className="num">{c.biens}</td>
                        {["gps", "photo", "entretien", "titre"].map((k) => (
                          <td key={k} className="num masquer-mobile chiffre" style={{ color: c.criteres[k] === null ? "var(--encre-3)" : couleur(c.criteres[k]) }}>
                            {c.criteres[k] === null ? "—" : `${c.criteres[k]} %`}
                          </td>
                        ))}
                        <td className="num">{c.declarations_30j}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Carte>

            <Carte titre="Fiches à compléter en priorité" description="Les biens dont le score est inférieur à 75" plein>
              {d.a_completer.length === 0 ? <Vide titre="Toutes les fiches sont complètes" /> : (
                <table className="tableau">
                  <tbody>
                    {d.a_completer.map((b) => (
                      <tr key={b.id}>
                        <td><Link to={`/biens/${b.id}`} className="principal-cell" style={{ color: "inherit" }}>{b.nom}</Link><div className="secondaire">{b.code}, {b.district}</div></td>
                        <td className="masquer-mobile"><div className="actions" style={{ gap: 4 }}>{b.manque.map((m) => <span key={m} className="badge attention">{m}</span>)}</div></td>
                        <td className="num" style={{ width: 160 }}><Progres valeur={b.score} couleur={couleur(b.score)} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Carte>
          </div>
        )}
      </Etat>
    </>
  );
}
