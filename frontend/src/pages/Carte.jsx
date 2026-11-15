import { useMemo, useState } from "react";
import { CircleMarker, MapContainer, Popup, TileLayer } from "react-leaflet";
import { Link } from "react-router-dom";
import { EnTete, Etat, Risque, useApi } from "../components/ui";
import { bif, CATEGORIES, COULEUR_CATEGORIE } from "../format";
import { useTheme } from "../theme";

export default function Carte() {
  const { theme } = useTheme();
  const { donnees, erreur, chargement } = useApi("carte/");
  const [visibles, setVisibles] = useState(new Set([...Object.keys(CATEGORIES), "projet"]));
  const [risque, setRisque] = useState(false);
  const basculer = (k) => {
    const s = new Set(visibles);
    s.has(k) ? s.delete(k) : s.add(k);
    setVisibles(s);
  };
  const comptes = useMemo(() => {
    const c = {};
    (donnees || []).forEach((p) => { const k = p.type === "projet" ? "projet" : p.categorie; c[k] = (c[k] || 0) + 1; });
    return c;
  }, [donnees]);
  const points = (donnees || []).filter((p) =>
    p.type === "projet" ? visibles.has("projet") : visibles.has(p.categorie) && (!risque || (p.risque ?? 0) >= 50)
  );
  const tuiles = theme === "dark"
    ? { url: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", attr: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>, &copy; <a href="https://carto.com/">CARTO</a>' }
    : { url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", attr: '&copy; contributeurs <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' };

  return (
    <>
      <EnTete titre="Carte du patrimoine" sousTitre="Biens et projets géolocalisés dans les cinq districts. Cliquez sur un point pour ouvrir sa fiche." />
      <Etat chargement={chargement} erreur={erreur} lignes={6}>
        <div className="carte-geo">
          <div className="couches" role="group" aria-label="Couches affichées">
            <h3>Couches</h3>
            {Object.entries(CATEGORIES).map(([k, v]) => (
              <label key={k}>
                <input type="checkbox" checked={visibles.has(k)} onChange={() => basculer(k)} />
                <i className="puce" style={{ background: COULEUR_CATEGORIE[k], width: 10, height: 10 }} />
                {v.split(" (")[0]}
                <span className="compte">{comptes[k] || 0}</span>
              </label>
            ))}
            <label>
              <input type="checkbox" checked={visibles.has("projet")} onChange={() => basculer("projet")} />
              <i className="puce" style={{ border: "2px dashed var(--encre)", width: 11, height: 11, background: "transparent" }} />
              Projets
              <span className="compte">{comptes.projet || 0}</span>
            </label>
            <hr />
            <label>
              <input type="checkbox" checked={risque} onChange={(e) => setRisque(e.target.checked)} />
              Seulement les biens à risque élevé
            </label>
          </div>
          <MapContainer key={theme} center={[-3.35, 29.95]} zoom={8} style={{ height: "100%" }} scrollWheelZoom>
            <TileLayer attribution={tuiles.attr} url={tuiles.url} />
            {points.map((p) =>
              p.type === "projet" ? (
                <CircleMarker key={`p${p.id}`} center={[p.lat, p.lon]} radius={14}
                  pathOptions={{ color: theme === "dark" ? "#e6eee9" : "#142019", weight: 2, fillOpacity: 0, dashArray: "4 3" }}>
                  <Popup>
                    <b>{p.nom}</b>
                    <div className="muet">{p.domaine}, {p.district}</div>
                    <div style={{ margin: "8px 0" }}>{p.statut}, avancement {p.avancement} %</div>
                    <Link to="/projets">Voir les projets</Link>
                  </Popup>
                </CircleMarker>
              ) : (
                <CircleMarker key={`b${p.id}`} center={[p.lat, p.lon]} radius={(p.risque ?? 0) >= 50 ? 9 : 7}
                  pathOptions={{ color: theme === "dark" ? "#131c18" : "#fff", weight: 2, fillColor: COULEUR_CATEGORIE[p.categorie], fillOpacity: 1 }}
                  className={(p.risque ?? 0) >= 85 ? "marqueur-urgence" : (p.risque ?? 0) >= 70 ? "marqueur-eleve" : (p.risque ?? 0) >= 50 ? "marqueur-attention" : ""}>
                  <Popup>
                    <b>{p.nom}</b>
                    <div className="code">{p.code}</div>
                    <div style={{ margin: "8px 0", display: "grid", gap: 4 }}>
                      <span>{p.categorie_libelle}, {p.district}</span>
                      <span>Valeur estimée : <b style={{ display: "inline", fontFamily: "inherit", fontSize: "inherit" }}>{bif(p.valeur, true)}</b></span>
                      <span style={{ display: "flex", gap: 8, alignItems: "center" }}>Risque : <Risque score={p.risque} /></span>
                    </div>
                    <Link to={`/biens/${p.id}`}>Ouvrir la fiche</Link>
                  </Popup>
                </CircleMarker>
              )
            )}
          </MapContainer>
        </div>
      </Etat>
    </>
  );
}
