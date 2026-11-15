import { useState } from "react";
import { Loader2, LocateFixed } from "lucide-react";
import { api } from "../api";
import { useAuth } from "../auth";
import { CATEGORIES, ETATS, JURIDIQUE, devise } from "../format";
import { Bandeau, Champ, Modale, useApi } from "./ui";

const VIDE = {
  nom: "", categorie: "IMM", sous_type: "", district: "", paroisse: "", etat: "BON", statut_juridique: "NA",
  surface_m2: "", quantite: 1, date_acquisition: "", valeur_acquisition: "", duree_vie_ans: "",
  latitude: "", longitude: "", financeur: "", odd: "", beneficiaires: 0, responsable: "", description: "",
};

// Création ou modification d'un bien : le même écran sert à l'agent de terrain et au bureau.
export default function BienFormulaire({ bien, onFermer, onEnregistre }) {
  const { moi } = useAuth();
  const [f, setF] = useState(() =>
    bien ? Object.fromEntries(Object.keys(VIDE).map((k) => [k, bien[k] ?? ""])) : { ...VIDE, district: moi.voit_tout ? "" : moi.district }
  );
  const [erreur, setErreur] = useState("");
  const [encours, setEncours] = useState(false);
  const [gps, setGps] = useState(false);
  const { donnees: districts } = useApi("districts/");
  const { donnees: paroisses } = useApi(f.district ? `paroisses/?district=${f.district}` : null, [f.district]);
  const maj = (k) => (e) => setF({ ...f, [k]: e.target.value });

  function localiser() {
    setGps(true);
    navigator.geolocation?.getCurrentPosition(
      (p) => { setF((x) => ({ ...x, latitude: p.coords.latitude.toFixed(6), longitude: p.coords.longitude.toFixed(6) })); setGps(false); },
      () => { setErreur("Position GPS indisponible. Autorisez la localisation ou saisissez les coordonnées."); setGps(false); }
    );
  }

  async function enregistrer() {
    setEncours(true);
    setErreur("");
    const corps = Object.fromEntries(Object.entries(f).map(([k, v]) => [k, v === "" ? null : v]));
    for (const k of ["sous_type", "financeur", "odd", "responsable", "description"]) corps[k] = corps[k] ?? "";
    try {
      onEnregistre(await api(bien ? `biens/${bien.id}/` : "biens/", { methode: bien ? "PATCH" : "POST", corps }));
    } catch (e) {
      setErreur(e.message);
    }
    setEncours(false);
  }

  return (
    <Modale
      titre={bien ? `Modifier ${bien.code}` : "Enregistrer un bien"}
      description={bien ? bien.nom : "Le code, la valeur estimée et le score de risque sont calculés automatiquement."}
      onFermer={onFermer}
      pied={
        <>
          <button className="bouton" onClick={onFermer}>Annuler</button>
          <button className="bouton principal" onClick={enregistrer} disabled={encours || !f.nom || !f.district}>
            {encours && <Loader2 className="tourne" />}
            {bien ? "Enregistrer les modifications" : "Enregistrer le bien"}
          </button>
        </>
      }
    >
      {erreur && <Bandeau type="erreur" style={{ marginBottom: 14 }}>{erreur}</Bandeau>}
      <div className="formulaire">
        <fieldset>
          <legend>Identification</legend>
          <Champ libelle="Nom du bien" large>
            <input value={f.nom} onChange={maj("nom")} placeholder="Forage de la paroisse de Rohero" required />
          </Champ>
          <Champ libelle="Catégorie">
            <select value={f.categorie} onChange={maj("categorie")}>
              {Object.entries(CATEGORIES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </Champ>
          <Champ libelle="Type précis">
            <input value={f.sous_type} onChange={maj("sous_type")} placeholder="École, centre de santé, forage…" />
          </Champ>
          <Champ libelle="État">
            <select value={f.etat} onChange={maj("etat")}>
              {Object.entries(ETATS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </Champ>
          <Champ libelle="Statut juridique">
            <select value={f.statut_juridique} onChange={maj("statut_juridique")}>
              {Object.entries(JURIDIQUE).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </Champ>
        </fieldset>

        <fieldset>
          <legend>Localisation</legend>
          <Champ libelle="District">
            <select value={f.district} onChange={(e) => setF({ ...f, district: e.target.value, paroisse: "" })} disabled={!moi.voit_tout}>
              <option value="">Choisir…</option>
              {districts?.map((d) => <option key={d.id} value={d.id}>{d.nom}</option>)}
            </select>
          </Champ>
          <Champ libelle="Paroisse">
            <select value={f.paroisse || ""} onChange={maj("paroisse")}>
              <option value="">Aucune</option>
              {paroisses?.map((p) => <option key={p.id} value={p.id}>{p.nom}</option>)}
            </select>
          </Champ>
          <Champ libelle="Latitude"><input type="number" step="any" value={f.latitude} onChange={maj("latitude")} /></Champ>
          <Champ libelle="Longitude"><input type="number" step="any" value={f.longitude} onChange={maj("longitude")} /></Champ>
          <div className="large">
            <button type="button" className="bouton petit" onClick={localiser} disabled={gps}>
              {gps ? <Loader2 className="tourne" /> : <LocateFixed />}Utiliser la position de cet appareil
            </button>
          </div>
        </fieldset>

        <fieldset>
          <legend>Valeur et caractéristiques</legend>
          <Champ libelle="Surface (m²)"><input type="number" min="0" value={f.surface_m2} onChange={maj("surface_m2")} /></Champ>
          <Champ libelle="Quantité"><input type="number" min="1" value={f.quantite} onChange={maj("quantite")} /></Champ>
          <Champ libelle="Date d'acquisition"><input type="date" value={f.date_acquisition} onChange={maj("date_acquisition")} /></Champ>
          <Champ libelle={`Valeur d'acquisition (${devise()})`}><input type="number" min="0" value={f.valeur_acquisition} onChange={maj("valeur_acquisition")} /></Champ>
          <Champ libelle="Durée de vie (années)" aide="Laissez vide pour la valeur standard de la catégorie.">
            <input type="number" min="1" value={f.duree_vie_ans} onChange={maj("duree_vie_ans")} />
          </Champ>
          <Champ libelle="Financeur"><input value={f.financeur} onChange={maj("financeur")} placeholder="UMCOR, UMDA…" /></Champ>
        </fieldset>

        <fieldset>
          <legend>Impact et responsabilité</legend>
          <Champ libelle="ODD concernés" aide="Numéros séparés par des virgules, par exemple 3,6.">
            <input value={f.odd} onChange={maj("odd")} />
          </Champ>
          <Champ libelle="Bénéficiaires"><input type="number" min="0" value={f.beneficiaires} onChange={maj("beneficiaires")} /></Champ>
          <Champ libelle="Responsable" large><input value={f.responsable} onChange={maj("responsable")} /></Champ>
          <Champ libelle="Description" large><textarea value={f.description} onChange={maj("description")} /></Champ>
        </fieldset>
      </div>
    </Modale>
  );
}
