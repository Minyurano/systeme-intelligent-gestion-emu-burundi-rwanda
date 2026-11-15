import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Boxes, Download, Plus, Search, Upload, X } from "lucide-react";
import { telecharger } from "../api";
import { useAuth } from "../auth";
import BienFormulaire from "../components/BienFormulaire";
import ImportBiens from "../components/ImportBiens";
import { BadgeEtat, Carte, ColonneTri, EnTete, Etat, Pagination, Risque, useApi, useToast, Vide } from "../components/ui";
import { bif, CATEGORIES, COULEUR_CATEGORIE, ETATS, JURIDIQUE } from "../format";

const FILTRES = ["district", "categorie", "etat", "statut_juridique"];

export default function Inventaire() {
  const { moi, peut } = useAuth();
  const nav = useNavigate();
  const notifier = useToast();
  const [params, setParams] = useSearchParams();
  const [recherche, setRecherche] = useState(params.get("search") || "");
  const [ajout, setAjout] = useState(false);
  const [importer, setImporter] = useState(false);
  const { donnees: districts } = useApi("districts/");

  const page = Number(params.get("page") || 1);
  const tri = params.get("tri") || "code";

  // L'état des filtres vit dans l'adresse : un lien partagé ouvre la même vue.
  function maj(changes) {
    const p = new URLSearchParams(params);
    Object.entries(changes).forEach(([k, v]) => (v ? p.set(k, v) : p.delete(k)));
    if (!("page" in changes)) p.delete("page");
    setParams(p, { replace: true });
  }

  useEffect(() => {
    const t = setTimeout(() => (recherche !== (params.get("search") || "")) && maj({ search: recherche }), 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [recherche]);

  const requete = new URLSearchParams();
  [...FILTRES, "search"].forEach((k) => params.get(k) && requete.set(k, params.get(k)));
  requete.set("ordering", tri.replace("valeur", "valeur_estimee"));
  requete.set("page", page);
  const { donnees, erreur, chargement, recharger } = useApi(`biens/?${requete}`);
  const actifs = FILTRES.filter((k) => params.get(k)).length + (params.get("search") ? 1 : 0);

  return (
    <>
      <EnTete
        titre="Inventaire du patrimoine"
        sousTitre="Chaque bien a un code unique et un QR code à coller dessus. Sa valeur et son score de risque sont recalculés à chaque modification."
      >
        <button className="bouton" onClick={() => { requete.delete("page"); telecharger(`biens/export/?${requete}`, "umurage_inventaire.csv"); }}>
          <Download />Exporter en CSV
        </button>
        {peut("import") && <button className="bouton" onClick={() => setImporter(true)}><Upload />Importer depuis Excel</button>}
        {peut("inventaire") && <button className="bouton principal" onClick={() => setAjout(true)}><Plus />Enregistrer un bien</button>}
      </EnTete>

      <Carte brut pied={donnees && donnees.count > 0 && (
        <Pagination page={page} total={donnees.count} onChange={(p) => maj({ page: String(p) })} unite="biens" />
      )}>
        <div className="barre-filtres">
          <div className="avec-icone">
            <Search />
            <input className="saisie-ui" placeholder="Rechercher par nom, code, type ou financeur" value={recherche} onChange={(e) => setRecherche(e.target.value)} aria-label="Rechercher" />
          </div>
          {moi.voit_tout && (
            <select className="saisie-ui" value={params.get("district") || ""} onChange={(e) => maj({ district: e.target.value })} aria-label="District">
              <option value="">Tous les districts</option>
              {districts?.map((d) => <option key={d.id} value={d.id}>{d.nom}</option>)}
            </select>
          )}
          <select className="saisie-ui" value={params.get("categorie") || ""} onChange={(e) => maj({ categorie: e.target.value })} aria-label="Catégorie">
            <option value="">Toutes les catégories</option>
            {Object.entries(CATEGORIES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <select className="saisie-ui" value={params.get("etat") || ""} onChange={(e) => maj({ etat: e.target.value })} aria-label="État">
            <option value="">Tous les états</option>
            {Object.entries(ETATS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <select className="saisie-ui" value={params.get("statut_juridique") || ""} onChange={(e) => maj({ statut_juridique: e.target.value })} aria-label="Statut juridique">
            <option value="">Tout statut juridique</option>
            {Object.entries(JURIDIQUE).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          {actifs > 0 && (
            <button className="bouton fantome petit" onClick={() => { setRecherche(""); setParams({}, { replace: true }); }}>
              <X />Effacer les filtres
            </button>
          )}
        </div>

        <Etat chargement={chargement && !donnees} erreur={erreur} lignes={8}>
          {/* tableau ou état vide */}
          {donnees && (donnees.results.length === 0 ? (
            <Vide icone={Boxes} titre="Aucun bien ne correspond" texte="Modifiez la recherche ou effacez les filtres pour voir tout l'inventaire." />
          ) : (
            <div className="defilement" style={{ opacity: chargement ? 0.6 : 1 }}>
              <table className="tableau">
                <thead>
                  <tr>
                    <ColonneTri champ="nom" tri={tri} onTri={(t) => maj({ tri: t })}>Bien</ColonneTri>
                    <th>Type</th>
                    <th className="masquer-mobile">Localisation</th>
                    <th>État</th>
                    <th className="masquer-mobile">Statut juridique</th>
                    <ColonneTri champ="valeur" tri={tri} onTri={(t) => maj({ tri: t })} num>Valeur estimée</ColonneTri>
                    <ColonneTri champ="score_risque" tri={tri} onTri={(t) => maj({ tri: t })} num>Risque</ColonneTri>
                  </tr>
                </thead>
                <tbody>
                  {donnees.results.map((b) => (
                    <tr key={b.id} className="cliquable" onClick={() => nav(`/biens/${b.id}`)} tabIndex={0} onKeyDown={(e) => e.key === "Enter" && nav(`/biens/${b.id}`)}>
                      <td>
                        <div className="principal-cell">{b.nom}</div>
                        <div className="secondaire">{b.code}{b.quantite > 1 ? `, ${b.quantite} unités` : ""}</div>
                      </td>
                      <td>
                        <span style={{ display: "inline-flex", gap: 8, alignItems: "center" }}>
                          <i className="pastille" style={{ background: COULEUR_CATEGORIE[b.categorie] }} />
                          {b.sous_type || b.categorie_libelle}
                        </span>
                      </td>
                      <td className="masquer-mobile">{b.district_nom}<div className="secondaire">{b.paroisse_nom}</div></td>
                      <td><BadgeEtat etat={b.etat} libelle={b.etat_libelle} /></td>
                      <td className="masquer-mobile">
                        {b.statut_juridique === "NA" ? <span className="muet">—</span>
                          : <span className={`badge ${b.statut_juridique === "TITRE" ? "bon" : b.statut_juridique === "SANS_TITRE" ? "critique" : "attention"}`}>{b.juridique_libelle}</span>}
                      </td>
                      <td className="num chiffre">{bif(b.valeur_courante, true)}</td>
                      <td className="num"><Risque score={b.score_risque} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </Etat>
      </Carte>

      {ajout && (
        <BienFormulaire
          onFermer={() => setAjout(false)}
          onEnregistre={(b) => {
            setAjout(false);
            if (b.hors_ligne) return notifier(`${b.nom} est enregistré sur cet appareil et sera envoyé au retour du réseau.`);
            notifier(`${b.nom} est enregistré sous le code ${b.code}.`);
            recharger();
            nav(`/biens/${b.id}`);
          }}
        />
      )}
      {importer && <ImportBiens onFermer={() => setImporter(false)} onFait={(n) => { setImporter(false); notifier(`${n} biens importés.`); recharger(); }} />}
    </>
  );
}
