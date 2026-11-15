import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { CircleMarker, MapContainer, TileLayer } from "react-leaflet";
import {
  ArrowLeft, CalendarClock, ClipboardList, Download, FileText, History, LayoutGrid, Loader2, Pencil, Plus, Radio, ShieldAlert, ShieldCheck,
} from "lucide-react";
import { api, telecharger } from "../api";
import { useAuth } from "../auth";
import BienFormulaire from "../components/BienFormulaire";
import { useAriane } from "../components/Layout";
import { BadgeEtat, Bandeau, Carte, Champ, Etat, Modale, Onglets, Risque, Squelette, useApi, useToast, Vide } from "../components/ui";
import { bif, COULEUR_CATEGORIE, date, nombre, devise } from "../format";
import { useTheme } from "../theme";

const TYPES_MVT = {
  MAINTENANCE: "Maintenance", REPARATION: "Réparation", INSPECTION: "Inspection",
  TRANSFERT: "Transfert", CESSION: "Cession", ACQUISITION: "Acquisition",
};

export default function FicheBien() {
  const { id } = useParams();
  const { peut } = useAuth();
  const notifier = useToast();
  const { donnees: b, erreur, recharger } = useApi(`biens/${id}/`, [id]);
  const analyse = useApi(`biens/${id}/analyse/`, [id, b?.modifie_le]);
  const mvts = useApi(`mouvements/?bien=${id}`, [id]);
  const docs = useApi(`documents/?bien=${id}`, [id]);
  const capteurs = useApi(`capteurs/?bien=${id}`, [id]);
  const [onglet, setOnglet] = useState("apercu");
  const [edition, setEdition] = useState(false);
  const [nouveauMvt, setNouveauMvt] = useState(false);
  useAriane(b?.nom);

  if (erreur) return <Bandeau type="erreur">{erreur}</Bandeau>;
  if (!b) return <Squelette lignes={8} hauteur={22} />;

  const risque = analyse.donnees?.risque;
  return (
    <>
      <div className="entete-page">
        <div>
          <Link to="/biens" className="petit" style={{ display: "inline-flex", alignItems: "center", gap: 6, textDecoration: "none" }}>
            <ArrowLeft size={14} />Inventaire
          </Link>
          <h1 style={{ marginTop: 8 }}>{b.nom}</h1>
          <div className="actions" style={{ marginTop: 10 }}>
            <span className="code" style={{ fontSize: "0.86rem" }}>{b.code}</span>
            <span className="badge"><i className="pastille" style={{ background: COULEUR_CATEGORIE[b.categorie] }} />{b.categorie_libelle}</span>
            <BadgeEtat etat={b.etat} libelle={b.etat_libelle} />
            <span className="muet petit">{b.district_nom}{b.paroisse_nom ? `, paroisse de ${b.paroisse_nom}` : ""}</span>
          </div>
        </div>
        <div className="actions">
          <button className="bouton" onClick={() => telecharger(`biens/${id}/qrcode/`, `${b.code}.png`)}><Download />Étiquette QR</button>
          {peut("inventaire") && <button className="bouton principal" onClick={() => setEdition(true)}><Pencil />Modifier</button>}
        </div>
      </div>

      <div className="kpis" style={{ marginBottom: 20 }}>
        <div className="kpi">
          <div className="kpi-tete"><span>Valeur estimée</span></div>
          <div className="kpi-valeur" style={{ fontSize: "1.5rem" }}>{bif(b.valeur_courante, true)}</div>
          <span className="kpi-note">{b.methode_valorisation || "Non valorisé"}</span>
        </div>
        <div className="kpi">
          <div className="kpi-tete"><span>Score de risque</span><div className={`kpi-icone ${(b.score_risque ?? 0) >= 50 ? "attention" : "bon"}`}>{(b.score_risque ?? 0) >= 50 ? <ShieldAlert /> : <ShieldCheck />}</div></div>
          <div className="kpi-valeur" style={{ fontSize: "1.5rem" }}>{b.score_risque != null ? Math.round(b.score_risque) : "—"}<small>sur 100</small></div>
          <span className="kpi-note">{risque?.facteurs?.[0] || "Aucun facteur de risque"}</span>
        </div>
        <div className="kpi">
          <div className="kpi-tete"><span>Acquisition</span><div className="kpi-icone"><CalendarClock /></div></div>
          <div className="kpi-valeur" style={{ fontSize: "1.5rem" }}>{b.date_acquisition ? new Date(b.date_acquisition).getFullYear() : "—"}</div>
          <span className="kpi-note">{b.age_ans != null ? `Il y a ${Math.round(b.age_ans)} ans, pour ${bif(b.valeur_acquisition, true)}` : "Date inconnue"}</span>
        </div>
        <div className="kpi">
          <div className="kpi-tete"><span>Statut juridique</span><div className={`kpi-icone ${b.statut_juridique === "SANS_TITRE" ? "critique" : b.statut_juridique === "EN_COURS" ? "attention" : "bon"}`}><FileText /></div></div>
          <div className="kpi-valeur" style={{ fontSize: "1.2rem", lineHeight: 1.2 }}>{b.juridique_libelle}</div>
          <span className="kpi-note">{b.financeur ? `Financé par ${b.financeur}` : "Financeur non renseigné"}</span>
        </div>
      </div>

      <Onglets actif={onglet} onChange={setOnglet} onglets={[
        { id: "apercu", libelle: "Vue d'ensemble", icone: LayoutGrid },
        { id: "historique", libelle: "Historique", icone: History, nb: mvts.donnees?.count },
        { id: "documents", libelle: "Documents", icone: FileText, nb: docs.donnees?.count },
        { id: "capteurs", libelle: "Capteurs", icone: Radio, nb: capteurs.donnees?.length },
      ]} />

      {onglet === "apercu" && (
        <div className="grille g-3-2">
          <div className="pile">
            <Carte titre="Valorisation" description="Comment l'estimation est obtenue">
              <Etat chargement={analyse.chargement && !analyse.donnees} erreur={analyse.erreur}>
                {analyse.donnees && <Valorisation v={analyse.donnees.valorisation} />}
              </Etat>
            </Carte>
            <Carte titre="Caractéristiques" brut>
              <dl className="proprietes" style={{ marginTop: 12, borderTop: "1px solid var(--trait)" }}>
                {[
                  ["Type précis", b.sous_type || "—"],
                  ["Surface", b.surface_m2 ? `${nombre(b.surface_m2)} m²` : "—"],
                  ["Quantité", b.quantite],
                  ["Durée de vie", b.duree_vie_ans ? `${b.duree_vie_ans} ans` : "Standard"],
                  ["Bénéficiaires", b.beneficiaires ? nombre(b.beneficiaires) : "—"],
                  ["Responsable", b.responsable || "—"],
                  ["ODD", b.odd_libelles.length ? b.odd_libelles.join(", ") : "—"],
                  ["Coordonnées", b.latitude ? `${b.latitude.toFixed(5)}, ${b.longitude.toFixed(5)}` : "Non géolocalisé"],
                ].map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}
              </dl>
              {b.description && <p style={{ padding: "14px 20px", color: "var(--encre-2)" }}>{b.description}</p>}
            </Carte>
          </div>
          <div className="pile">
            <Carte titre="Facteurs de risque">
              <div style={{ marginBottom: 12 }}><Risque score={b.score_risque} /></div>
              {risque?.facteurs?.length ? (
                <ul style={{ margin: 0, paddingLeft: 18, color: "var(--encre-2)", display: "grid", gap: 6 }}>
                  {risque.facteurs.map((f) => <li key={f}>{f}</li>)}
                </ul>
              ) : <p className="muet">Aucun facteur de risque détecté pour ce bien.</p>}
            </Carte>
            {b.latitude && <MiniCarte b={b} />}
            <QrCode id={id} code={b.code} />
          </div>
        </div>
      )}

      {onglet === "historique" && (
        <Carte titre="Historique du bien" description="Acquisition, entretiens, inspections et réparations"
          actions={peut("inventaire") && <button className="bouton petit" onClick={() => setNouveauMvt(true)}><Plus />Ajouter un événement</button>} plein>
          <Etat chargement={mvts.chargement && !mvts.donnees} erreur={mvts.erreur}>
            <table className="tableau">
              <thead><tr><th>Date</th><th>Événement</th><th className="masquer-mobile">Réalisé par</th><th className="num">Montant</th></tr></thead>
              <tbody>
                {mvts.donnees?.results.map((m) => (
                  <tr key={m.id}>
                    <td style={{ whiteSpace: "nowrap" }}>{date(m.date)}</td>
                    <td><div className="principal-cell">{m.type_libelle}</div><div className="secondaire">{m.description}</div></td>
                    <td className="masquer-mobile">{m.auteur || "—"}</td>
                    <td className="num chiffre">{bif(m.montant, true)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Etat>
        </Carte>
      )}

      {onglet === "documents" && (
        <Carte titre="Documents rattachés" plein>
          {docs.donnees?.results.length ? (
            <table className="tableau">
              <tbody>
                {docs.donnees.results.map((d) => (
                  <tr key={d.id}>
                    <td><div className="principal-cell">{d.titre}</div><div className="secondaire">{d.type_libelle}, {date(d.date)}</div></td>
                    <td className="num">{d.fichier ? <a className="bouton petit" href={d.fichier} target="_blank" rel="noreferrer">Ouvrir</a> : <span className="badge">Texte archivé</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <Vide icone={FileText} titre="Aucun document" texte="Ajoutez titres fonciers, contrats et rapports depuis la page Assistant et archives." />}
        </Carte>
      )}

      {onglet === "capteurs" && (
        <Carte titre="Capteurs installés" plein>
          {capteurs.donnees?.length ? (
            <table className="tableau">
              <tbody>
                {capteurs.donnees.map((c) => (
                  <tr key={c.id}>
                    <td><div className="principal-cell">{c.type_libelle}</div><div className="secondaire">{c.code}</div></td>
                    <td className="num chiffre"><b>{c.derniere_valeur?.toLocaleString("fr-FR")} {c.unite}</b></td>
                    <td className="num">{c.en_alerte ? <span className="badge critique">En alerte</span> : <span className="badge bon">Normal</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <Vide icone={Radio} titre="Aucun capteur" texte="Ce bien n'est pas encore équipé de capteurs connectés." />}
        </Carte>
      )}

      {edition && <BienFormulaire bien={b} onFermer={() => setEdition(false)} onEnregistre={() => { setEdition(false); notifier("Modifications enregistrées."); recharger(); }} />}
      {nouveauMvt && (
        <NouveauMouvement bienId={b.id} onFermer={() => setNouveauMvt(false)}
          onEnregistre={() => { setNouveauMvt(false); notifier("Événement ajouté à l'historique."); mvts.recharger(); recharger(); }} />
      )}
    </>
  );
}

function Valorisation({ v }) {
  if (v.erreur) return <Bandeau type="erreur">{v.erreur}</Bandeau>;
  const max = Math.max(...v.facteurs.map((f) => Math.abs(f.effet_bif)), 1);
  const [bas, haut] = v.intervalle;
  const pos = haut > bas ? ((v.valeur - bas) / (haut - bas)) * 100 : 50;
  return (
    <>
      <div style={{ display: "flex", alignItems: "baseline", gap: 12, flexWrap: "wrap" }}>
        <div className="chiffre" style={{ fontFamily: "var(--titre)", fontSize: "2rem", fontWeight: 700, letterSpacing: "-0.02em" }}>{bif(v.valeur)}</div>
        <span className="badge info">{v.methode}</span>
      </div>
      {haut > bas && (
        <div style={{ margin: "14px 0 18px" }}>
          <div style={{ position: "relative", height: 8, borderRadius: 4, background: "var(--surface-3)" }}>
            <div style={{ position: "absolute", left: 0, right: 0, top: 0, bottom: 0, borderRadius: 4, background: "linear-gradient(90deg, var(--marque-pale), var(--marque))", opacity: 0.6 }} />
            <div style={{ position: "absolute", left: `${pos}%`, top: -4, width: 4, height: 16, borderRadius: 2, background: "var(--encre)", transform: "translateX(-2px)" }} />
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6 }} className="petit muet">
            <span>{bif(bas, true)}</span><span>Fourchette probable</span><span>{bif(haut, true)}</span>
          </div>
        </div>
      )}
      <h3 style={{ marginBottom: 8 }}>Ce qui explique cette estimation</h3>
      <div style={{ display: "grid", gap: 8 }}>
        {v.facteurs.map((f) => (
          <div key={f.facteur} style={{ display: "grid", gridTemplateColumns: "minmax(0, 38%) minmax(0, 1fr) auto", gap: 12, alignItems: "center" }}>
            <span className="petit">{f.facteur}</span>
            <div style={{ height: 8, borderRadius: 4, background: "var(--surface-3)" }}>
              <div style={{ height: "100%", borderRadius: 4, width: `${(100 * Math.abs(f.effet_bif)) / max}%`, background: f.effet_bif >= 0 ? "var(--marque)" : "var(--critique)" }} />
            </div>
            <span className="chiffre petit" style={{ fontWeight: 600, minWidth: 90, textAlign: "right", color: f.effet_bif >= 0 ? "var(--marque-texte)" : "var(--critique)" }}>
              {f.effet_bif >= 0 ? "+" : "−"}{bif(Math.abs(f.effet_bif), true)}
            </span>
          </div>
        ))}
      </div>
      {v.details?.note && <p className="petit muet" style={{ marginTop: 12 }}>{v.details.note}</p>}
    </>
  );
}

function MiniCarte({ b }) {
  const { theme } = useTheme();
  const tuiles = theme === "dark" ? "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png" : "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
  return (
    <section className="carte-ui" style={{ overflow: "hidden" }}>
      <div style={{ height: 200 }}>
        <MapContainer key={theme} center={[b.latitude, b.longitude]} zoom={11} style={{ height: "100%" }} zoomControl={false} scrollWheelZoom={false} attributionControl={false}>
          <TileLayer url={tuiles} />
          <CircleMarker center={[b.latitude, b.longitude]} radius={9} pathOptions={{ color: "#fff", weight: 3, fillColor: COULEUR_CATEGORIE[b.categorie], fillOpacity: 1 }} />
        </MapContainer>
      </div>
      <div className="carte-pied"><span>{b.paroisse_nom || b.district_nom}</span><Link to="/carte">Ouvrir la carte</Link></div>
    </section>
  );
}

function QrCode({ id, code }) {
  const [qr, setQr] = useState(null);
  useEffect(() => {
    let url;
    telecharger(`biens/${id}/qrcode/`).then((u) => { url = u; setQr(u); }).catch(() => setQr(null));
    return () => url && URL.revokeObjectURL(url);
  }, [id]);
  return (
    <Carte titre="Étiquette QR" description="À imprimer et coller sur le bien">
      <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
        <div style={{ background: "#fff", padding: 6, borderRadius: 10, border: "1px solid var(--trait)" }}>
          {qr ? <img src={qr} alt={`QR code du bien ${code}`} width={112} height={112} /> : <div className="squelette" style={{ width: 112, height: 112 }} />}
        </div>
        <div>
          <div className="code" style={{ fontSize: "0.95rem", color: "var(--encre)" }}>{code}</div>
          <p className="petit muet" style={{ marginTop: 6 }}>Scanné avec un téléphone, il ouvre directement cette fiche.</p>
        </div>
      </div>
    </Carte>
  );
}

function NouveauMouvement({ bienId, onFermer, onEnregistre }) {
  const [f, setF] = useState({ type: "MAINTENANCE", date: new Date().toISOString().slice(0, 10), montant: 0, description: "", auteur: "" });
  const [erreur, setErreur] = useState("");
  const [encours, setEncours] = useState(false);
  const maj = (k) => (e) => setF({ ...f, [k]: e.target.value });
  async function enregistrer() {
    setEncours(true);
    try {
      await api("mouvements/", { methode: "POST", corps: { ...f, bien: bienId } });
      onEnregistre();
    } catch (e) {
      setErreur(e.message);
    }
    setEncours(false);
  }
  return (
    <Modale titre="Ajouter un événement" description="Un entretien récent fait baisser le score de risque du bien." onFermer={onFermer} largeur={620}
      pied={<><button className="bouton" onClick={onFermer}>Annuler</button><button className="bouton principal" onClick={enregistrer} disabled={encours}>{encours ? <Loader2 className="tourne" /> : <ClipboardList />}Ajouter l'événement</button></>}>
      {erreur && <Bandeau type="erreur" style={{ marginBottom: 14 }}>{erreur}</Bandeau>}
      <div className="formulaire">
        <Champ libelle="Type d'événement">
          <select value={f.type} onChange={maj("type")}>{Object.entries(TYPES_MVT).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
        </Champ>
        <Champ libelle="Date"><input type="date" value={f.date} onChange={maj("date")} /></Champ>
        <Champ libelle={`Montant (${devise()})`}><input type="number" min="0" value={f.montant} onChange={maj("montant")} /></Champ>
        <Champ libelle="Réalisé par"><input value={f.auteur} onChange={maj("auteur")} /></Champ>
        <Champ libelle="Description" large><textarea value={f.description} onChange={maj("description")} /></Champ>
      </div>
    </Modale>
  );
}
