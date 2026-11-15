import { useRef, useState } from "react";
import { CheckCircle2, FileSpreadsheet, Loader2, Upload } from "lucide-react";
import { api, telecharger } from "../api";
import { Bandeau, Modale } from "./ui";
import { bif } from "../format";

// Importe un inventaire existant (Excel ou CSV) : aperçu ligne par ligne, puis import des lignes valides.
export default function ImportBiens({ onFermer, onFait }) {
  const [fichier, setFichier] = useState(null);
  const [apercu, setApercu] = useState(null);
  const [erreur, setErreur] = useState("");
  const [encours, setEncours] = useState(false);
  const [survol, setSurvol] = useState(false);
  const ref = useRef(null);

  async function envoyer(f, apercuSeul) {
    setEncours(true);
    setErreur("");
    const fd = new FormData();
    fd.append("fichier", f);
    if (apercuSeul) fd.append("apercu", "1");
    try {
      const r = await api("import/biens/", { methode: "POST", corps: fd });
      if (apercuSeul) setApercu(r);
      else onFait(r.crees);
    } catch (e) {
      setErreur(e.message);
    }
    setEncours(false);
  }

  function choisir(f) {
    if (!f) return;
    setFichier(f);
    setApercu(null);
    envoyer(f, true);
  }

  return (
    <Modale titre="Importer un inventaire" description="Depuis un fichier Excel ou CSV : les colonnes sont reconnues automatiquement, rien n'est enregistré avant votre confirmation."
      onFermer={onFermer} largeur={860}
      pied={<>
        <button className="bouton fantome" onClick={() => telecharger("import/modele/", "umurage_modele_import.xlsx")} style={{ marginRight: "auto" }}><FileSpreadsheet />Télécharger le modèle Excel</button>
        <button className="bouton" onClick={onFermer}>Annuler</button>
        <button className="bouton principal" disabled={!apercu?.valides || encours} onClick={() => envoyer(fichier, false)}>
          {encours && apercu ? <Loader2 className="tourne" /> : <Upload />}Importer {apercu?.valides || 0} biens
        </button>
      </>}>
      {erreur && <Bandeau type="erreur" style={{ marginBottom: 14 }}>{erreur}</Bandeau>}
      <div className={`depot${survol ? " actif" : ""}`} onClick={() => ref.current?.click()} role="button" tabIndex={0}
        onKeyDown={(e) => e.key === "Enter" && ref.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setSurvol(true); }} onDragLeave={() => setSurvol(false)}
        onDrop={(e) => { e.preventDefault(); setSurvol(false); choisir(e.dataTransfer.files[0]); }}>
        {encours && !apercu ? <Loader2 className="tourne" /> : <Upload />}
        <b>{fichier ? fichier.name : "Déposez votre fichier ici ou cliquez pour le choisir"}</b>
        <span className="petit muet">Excel (.xlsx) ou CSV. Une ligne par bien ; colonnes reconnues : nom, catégorie, district, paroisse, état, valeur, date, GPS…</span>
        <input ref={ref} type="file" accept=".xlsx,.csv,.txt" hidden onChange={(e) => choisir(e.target.files[0])} />
      </div>

      {apercu && (
        <div style={{ marginTop: 18 }}>
          <div className="actions" style={{ marginBottom: 10 }}>
            <span className="badge bon"><CheckCircle2 />{apercu.valides} lignes prêtes</span>
            {apercu.invalides > 0 && <span className="badge critique">{apercu.invalides} lignes à corriger</span>}
            <span className="petit muet">Colonnes reconnues : {apercu.colonnes_reconnues.join(", ")}{apercu.colonnes_ignorees.length ? `. Ignorées : ${apercu.colonnes_ignorees.join(", ")}` : ""}</span>
          </div>
          <div className="defilement" style={{ maxHeight: 320, border: "1px solid var(--trait)", borderRadius: 10 }}>
            <table className="tableau compact">
              <thead><tr><th>Ligne</th><th>Bien</th><th>District</th><th className="num">Valeur</th><th>Statut</th></tr></thead>
              <tbody>
                {apercu.details.map((l) => (
                  <tr key={l.ligne}>
                    <td className="code">{l.ligne}</td>
                    <td><div className="principal-cell">{l.nom || <span className="muet">(sans nom)</span>}</div></td>
                    <td>{l.district || "—"}</td>
                    <td className="num chiffre">{l.valeur ? bif(l.valeur, true) : "—"}</td>
                    <td>{l.erreurs.length ? <span className="petit" style={{ color: "var(--critique)" }}>{l.erreurs.join(" ; ")}</span> : <span className="badge bon">Prête</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </Modale>
  );
}
