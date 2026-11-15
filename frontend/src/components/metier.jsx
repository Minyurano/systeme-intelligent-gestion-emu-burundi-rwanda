import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { api, tout } from "../api";
import { Bandeau, Champ, Modale } from "./ui";

// Liste des biens actifs du périmètre, chargée une fois pour les listes déroulantes.
let cacheBiens = null;
export function useBiens() {
  const [biens, setBiens] = useState(cacheBiens || []);
  useEffect(() => {
    if (cacheBiens) return;
    tout("biens/?page_size=200&ordering=code").then((b) => { cacheBiens = b || []; setBiens(cacheBiens); }).catch(() => {});
  }, []);
  return biens;
}

export const optionsBiens = (biens) => [{ v: "", l: "—" }, ...biens.map((b) => ({ v: b.id, l: `${b.code} · ${b.nom}` }))];

/*
  Formulaire générique en modale.
  champs : [{ k, libelle, type: "texte" | "nombre" | "date" | "select" | "zone" | "case", options: [{v, l}], large, requis, aide }]
*/
export function FormModale({ titre, description, champs, initial = {}, envoyer, onFermer, onFait, bouton = "Enregistrer" }) {
  const [f, setF] = useState(() => Object.fromEntries(champs.map((c) => [c.k, initial[c.k] ?? (c.type === "case" ? false : "")])));
  const [erreur, setErreur] = useState("");
  const [encours, setEncours] = useState(false);
  const manque = champs.some((c) => c.requis && (f[c.k] === "" || f[c.k] === null));

  async function valider() {
    setEncours(true);
    setErreur("");
    const corps = Object.fromEntries(Object.entries(f).map(([k, v]) => [k, v === "" ? null : v]));
    for (const c of champs) if ((c.type === "texte" || c.type === "zone") && corps[c.k] === null) corps[c.k] = "";
    try {
      const r = await envoyer(corps);
      onFait?.(r);
      onFermer();
    } catch (e) {
      setErreur(e.message);
    }
    setEncours(false);
  }

  return (
    <Modale titre={titre} description={description} onFermer={onFermer} pied={
      <>
        <button className="bouton" onClick={onFermer}>Annuler</button>
        <button className="bouton principal" disabled={encours || manque} onClick={valider}>
          {encours && <Loader2 className="tourne" />}{bouton}
        </button>
      </>
    }>
      {erreur && <Bandeau type="erreur" style={{ marginBottom: 14 }}>{erreur}</Bandeau>}
      <div className="formulaire"><fieldset>
        {champs.filter((c) => !c.cache?.(f)).map((c) => (
          <Champ key={c.k} libelle={c.libelle + (c.requis ? " *" : "")} large={c.large || c.type === "zone"} aide={c.aide}>
            {c.type === "select" ? (
              <select value={f[c.k] ?? ""} onChange={(e) => setF({ ...f, [c.k]: e.target.value })}>
                {(c.options || []).map((o) => <option key={o.v} value={o.v}>{o.l}</option>)}
              </select>
            ) : c.type === "zone" ? (
              <textarea rows={3} value={f[c.k]} onChange={(e) => setF({ ...f, [c.k]: e.target.value })} placeholder={c.exemple} />
            ) : c.type === "case" ? (
              <input type="checkbox" checked={!!f[c.k]} onChange={(e) => setF({ ...f, [c.k]: e.target.checked })} style={{ width: 20, height: 20 }} />
            ) : (
              <input type={c.type === "nombre" ? "number" : c.type === "date" ? "date" : "text"} value={f[c.k] ?? ""}
                onChange={(e) => setF({ ...f, [c.k]: e.target.value })} placeholder={c.exemple} min={c.type === "nombre" ? 0 : undefined} />
            )}
          </Champ>
        ))}
      </fieldset></div>
    </Modale>
  );
}

// Action POST simple avec gestion d'erreur et notification.
export async function agir(chemin, corps, notifier, succes) {
  try {
    const r = await api(chemin, { methode: "POST", corps: corps || {} });
    if (succes) notifier(succes);
    return r;
  } catch (e) {
    notifier(e.message, "erreur");
    return null;
  }
}

export const joursRestants = (n) =>
  n < 0 ? `${-n} j de retard` : n === 0 ? "aujourd'hui" : n === 1 ? "demain" : `dans ${n} j`;
