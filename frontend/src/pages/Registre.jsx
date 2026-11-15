import { useEffect, useMemo, useRef, useState } from "react";
import {
  BadgeCheck, Camera, CheckCircle2, Droplets, IdCard, KeyRound, Loader2, Pencil, Printer, Search, UserCheck, UserPlus, Users, X,
} from "lucide-react";
import { api } from "../api";
import { useAuth } from "../auth";
import { CarteMembre, imprimerCarte, initiales } from "../components/CarteMembre";
import IdentifiantsModale from "../components/IdentifiantsAcces";
import Scribe from "../components/Scribe";
import { Bandeau, Carte, Champ, EnTete, Etat, Kpi, Pagination, Segments, useApi, useToast, Vide } from "../components/ui";
import { date as dateFr, nombre } from "../format";

const STATUTS = [
  { v: "CONFESSANT", l: "Membre confessant", ton: "bon" },
  { v: "BAPTISE", l: "Membre baptisé", ton: "bon" },
  { v: "CATECHUMENE", l: "Catéchumène", ton: "info" },
  { v: "SYMPATHISANT", l: "Sympathisant", ton: "attention" },
  { v: "TRANSFERE", l: "Transféré", ton: "" },
  { v: "DECEDE", l: "Décédé", ton: "" },
];
const TON = Object.fromEntries(STATUTS.map((s) => [s.v, s.ton]));
const SITUATIONS = [["", "—"], ["CELIBATAIRE", "Célibataire"], ["MARIE", "Marié(e)"], ["VEUF", "Veuf / veuve"], ["DIVORCE", "Divorcé(e)"]];
const MINISTERES = ["Chorale", "Femmes méthodistes", "Hommes méthodistes", "Jeunesse", "École du dimanche", "Intercession", "Diaconat"];

const VIDE = {
  nom: "", prenom: "", sexe: "", date_naissance: "", lieu_naissance: "", telephone: "", adresse: "", situation_familiale: "",
  profession: "", paroisse: "", statut: "CATECHUMENE", date_adhesion: new Date().toISOString().slice(0, 10), date_bapteme: "",
  date_confirmation: "", ministere: "", notes: "",
};
const OBLIGATOIRES = ["nom", "prenom", "sexe", "paroisse", "statut", "date_adhesion"];
// Ce qui compte pour la progression de la fiche (l'obligatoire pèse double)
const UTILES = ["date_naissance", "lieu_naissance", "telephone", "adresse", "situation_familiale", "profession", "ministere"];


export default function Registre() {
  const { moi } = useAuth();
  const notifier = useToast();
  const org = moi?.organisation || {};
  const ecriture = ["ADMIN", "EVEQUE", "SURINTENDANT", "AGENT"].includes(moi?.role);
  const gereAcces = moi?.role === "ADMIN";
  const [identifiants, setIdentifiants] = useState(null);
  async function donnerAcces(m) {
    try {
      setIdentifiants(await api(`acces-membres/${m.id}/accorder/`, { methode: "POST", corps: {} }));
      setVersion((v) => v + 1);
    } catch (e) {
      notifier(e.message, "erreur");
    }
  }

  const [f, setF] = useState(VIDE);
  const [photo, setPhoto] = useState(null);
  const [apercuPhoto, setApercuPhoto] = useState(null);
  const [edition, setEdition] = useState(null); // fiche en cours de modification
  const [actif, setActif] = useState(false);
  const [envoi, setEnvoi] = useState(false);
  const [erreur, setErreur] = useState("");
  const [doublon, setDoublon] = useState("");
  const [confirmer, setConfirmer] = useState(false);
  const [enregistre, setEnregistre] = useState(null);
  const minuteur = useRef(null);
  const haut = useRef(null);
  const entreePhoto = useRef(null);

  const [q, setQ] = useState("");
  const [statut, setStatut] = useState("");
  const [paroisseFiltre, setParoisseFiltre] = useState("");
  const [page, setPage] = useState(1);
  const [version, setVersion] = useState(0);

  const { donnees: paroisses } = useApi("paroisses/");
  const stats = useApi(`registre/statistiques/?v=${version}`, [version]);
  const filtres = new URLSearchParams({ page, page_size: 25, ordering: "-cree_le", ...(q && { search: q }), ...(statut && { statut }),
    ...(paroisseFiltre && { paroisse: paroisseFiltre }) }).toString();
  const liste = useApi(`registre/?${filtres}&v=${version}`, [filtres, version]);

  useEffect(() => () => apercuPhoto && URL.revokeObjectURL(apercuPhoto), [apercuPhoto]);

  const maj = (k, v) => {
    setF((x) => ({ ...x, [k]: v }));
    setActif(true);
    clearTimeout(minuteur.current);
    minuteur.current = setTimeout(() => setActif(false), 1400);
  };

  const manquants = OBLIGATOIRES.filter((k) => !f[k]);
  const progression = useMemo(() => {
    const total = OBLIGATOIRES.length * 2 + UTILES.length + 1;
    const fait = OBLIGATOIRES.filter((k) => f[k]).length * 2 + UTILES.filter((k) => f[k]).length + (photo || apercuPhoto ? 1 : 0);
    return (100 * fait) / total;
  }, [f, photo, apercuPhoto]);
  const pret = manquants.length === 0;
  const paroisse = (paroisses || []).find((p) => String(p.id) === String(f.paroisse));
  const sectionComplete = (cles) => cles.every((k) => f[k]);

  function choisirPhoto(e) {
    const fichier = e.target.files?.[0];
    if (!fichier) return;
    if (fichier.size > 5 * 1024 * 1024) return notifier("La photo dépasse 5 Mo.", "erreur");
    setPhoto(fichier);
    setApercuPhoto(URL.createObjectURL(fichier));
    setActif(true);
  }

  function reinitialiser() {
    setF({ ...VIDE, paroisse: f.paroisse }); // on garde l'église locale pour enchaîner les fiches
    setPhoto(null); setApercuPhoto(null); setEdition(null); setErreur(""); setDoublon(""); setConfirmer(false);
  }

  function modifier(m) {
    setEnregistre(null);
    setEdition(m);
    setF(Object.fromEntries(Object.keys(VIDE).map((k) => [k, m[k] ?? ""])));
    setPhoto(null); setApercuPhoto(m.photo || null); setErreur(""); setDoublon(""); setConfirmer(false);
    haut.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function enregistrer() {
    setEnvoi(true); setErreur(""); setDoublon("");
    const corps = Object.fromEntries(Object.entries(f).map(([k, v]) => [k, v === "" ? null : v]));
    for (const k of ["lieu_naissance", "telephone", "adresse", "situation_familiale", "profession", "ministere", "notes"]) if (corps[k] === null) corps[k] = "";
    if (confirmer) corps.confirmer_doublon = true;
    try {
      let envoi = corps;
      if (photo) {
        envoi = new FormData();
        Object.entries(corps).forEach(([k, v]) => v !== null && envoi.append(k, v));
        envoi.append("photo", photo);
      }
      const r = await api(edition ? `registre/${edition.id}/` : "registre/", { methode: edition ? "PATCH" : "POST", corps: envoi });
      setEnregistre({ ...r, modification: !!edition });
      notifier(edition ? `Fiche ${r.numero} mise à jour.` : `Membre enregistré : ${r.numero}`);
      reinitialiser();
      setVersion((v) => v + 1);
    } catch (e) {
      if (e.details?.doublon) setDoublon([].concat(e.details.doublon).join(" "));
      else setErreur(e.message);
    }
    setEnvoi(false);
  }

  // Classe « requis-vide » : le champ obligatoire encore vide respire en ambre
  const requis = (k) => (OBLIGATOIRES.includes(k) && !f[k] ? "requis-vide" : "");
  const champ = (k, libelle, props = {}) => (
    <div className={requis(k) || undefined} style={{ display: "contents" }}>
      <Champ libelle={libelle + (OBLIGATOIRES.includes(k) ? " *" : "")} large={props.large}>
        <input type={props.type || "text"} value={f[k]} placeholder={props.exemple} onChange={(e) => maj(k, e.target.value)}
          max={props.type === "date" ? new Date().toISOString().slice(0, 10) : undefined} />
      </Champ>
    </div>
  );

  const s = stats.donnees;
  const resultats = liste.donnees?.results || [];

  return (
    <>
      <EnTete titre="Registre des membres"
        sousTitre="Enregistrement officiel des membres de chaque église locale. Chaque fiche reçoit un numéro unique et définitif, et chaque modification est tracée dans le journal d'audit." />

      <div className="pile">
        <div className="kpis">
          <Kpi libelle="Membres actifs" icone={Users} ton="info" valeur={s ? nombre(s.actifs) : "…"} note={s ? `${nombre(s.femmes)} femmes, ${nombre(s.hommes)} hommes` : ""} />
          <Kpi libelle="Baptisés et confessants" icone={Droplets} ton="bon" valeur={s ? nombre(s.baptises) : "…"} note={s?.actifs ? `${Math.round(100 * s.baptises / s.actifs)} % des actifs` : ""} />
          <Kpi libelle="Nouveaux ce mois" icone={UserPlus} ton={s?.nouveaux_mois ? "bon" : "attention"} valeur={s ? nombre(s.nouveaux_mois) : "…"} note="fiches créées depuis le 1er" />
          <Kpi libelle="Taux d'enregistrement" icone={IdCard} ton={s?.taux_enregistrement < 25 ? "critique" : "attention"}
            valeur={s?.taux_enregistrement != null ? `${s.taux_enregistrement.toLocaleString("fr-FR")} %` : "—"}
            note={s ? `des ${nombre(s.declares)} membres déclarés` : ""} noteTon={s?.taux_enregistrement < 25 ? "critique" : ""} />
        </div>

        {ecriture && (
          <section className="fiche-officielle" ref={haut} aria-label="Fiche d'enregistrement">
            <div className="fiche-tete">
              <div className="titre">
                <img src="/logo.svg" alt="" />
                <div>
                  <h2>{edition ? "Modification de la fiche" : "Fiche officielle d'adhésion"}</h2>
                  <p>{org.nom || "Église"}{paroisse ? ` · ${paroisse.nom}` : ""}</p>
                </div>
              </div>
              <div className="numero">
                N° de membre
                <b>{edition ? edition.numero : enregistre && !enregistre.modification ? enregistre.numero : "attribué à l'enregistrement"}</b>
              </div>
            </div>

            {enregistre ? (
              <div className="succes-enregistrement">
                <div className="coche"><CheckCircle2 /></div>
                <h2>{enregistre.modification ? "Fiche mise à jour" : "Membre enregistré"}</h2>
                <div className="gros-numero">{enregistre.numero}</div>
                <p className="muet">{enregistre.prenom} {enregistre.nom}, {enregistre.paroisse_nom} ({enregistre.district_nom}). {enregistre.statut_libelle}.</p>
                <div style={{ width: "min(360px, 100%)", margin: "6px 0" }}><CarteMembre m={enregistre} org={org} photo={enregistre.photo} /></div>
                <div style={{ display: "flex", gap: 10, flexWrap: "wrap", justifyContent: "center" }}>
                  <button className="bouton" onClick={() => imprimerCarte(enregistre, org)}><Printer />Imprimer la carte de membre</button>
                  <button className="bouton principal" onClick={() => setEnregistre(null)}><UserPlus />Enregistrer un autre membre</button>
                </div>
              </div>
            ) : (
              <div className="fiche-corps">
                <div className="fiche-cote">
                  <Scribe actif={actif} progression={progression} pret={pret} />
                  <div>
                    <div className="petit muet" style={{ marginBottom: 8, fontWeight: 600 }}>Aperçu de la carte de membre</div>
                    <CarteMembre m={{ ...f, paroisse_nom: paroisse?.nom, district_nom: paroisse?.district_nom, numero: edition?.numero,
                      statut_libelle: STATUTS.find((x) => x.v === f.statut)?.l }} org={org} photo={apercuPhoto} />
                  </div>
                </div>

                <div className="fiche-form">
                  {erreur && <Bandeau type="erreur">{erreur}</Bandeau>}
                  {doublon && (
                    <Bandeau type="attention">
                      <div>{doublon}</div>
                      <label style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 8, fontWeight: 600 }}>
                        <input type="checkbox" checked={confirmer} onChange={(e) => setConfirmer(e.target.checked)} />
                        Je confirme qu'il s'agit d'une autre personne
                      </label>
                    </Bandeau>
                  )}

                  <div className={`fiche-section${sectionComplete(["nom", "prenom", "sexe"]) ? " complete" : ""}`}>
                    <h3><span className="num">1</span>Identité{sectionComplete(["nom", "prenom", "sexe"]) && <span className="ok"><BadgeCheck size={15} />Complet</span>}</h3>
                    <div className="fiche-grille">
                      <div className="large zone-photo">
                        <div className="apercu" onClick={() => entreePhoto.current?.click()} role="button" tabIndex={0} aria-label="Ajouter une photo"
                          onKeyDown={(e) => e.key === "Enter" && entreePhoto.current?.click()}>
                          {apercuPhoto ? <img src={apercuPhoto} alt="Photo du membre" /> : <Camera />}
                        </div>
                        <div className="petit muet">
                          <b style={{ color: "var(--encre)" }}>Photo d'identité</b><br />
                          Visage de face, fond clair. JPG ou PNG, 5 Mo au plus. Sur téléphone, l'appareil photo s'ouvre directement.
                          <div style={{ marginTop: 8, display: "flex", gap: 8 }}>
                            <button className="bouton" type="button" onClick={() => entreePhoto.current?.click()}><Camera />{apercuPhoto ? "Changer" : "Ajouter"}</button>
                            {apercuPhoto && <button className="bouton" type="button" onClick={() => { setPhoto(null); setApercuPhoto(null); }}><X />Retirer</button>}
                          </div>
                        </div>
                        <input ref={entreePhoto} type="file" accept="image/*" capture="user" hidden onChange={choisirPhoto} />
                      </div>
                      {champ("nom", "Nom", { exemple: "ex. NIYONZIMA" })}
                      {champ("prenom", "Prénom", { exemple: "ex. Esther" })}
                      <div className={`champ ${requis("sexe")}`} role="group" aria-label="Sexe">
                        Sexe *
                        <div className="choix-sexe">
                          {[["F", "Femme"], ["H", "Homme"]].map(([v, l]) => (
                            <button key={v} type="button" aria-pressed={f.sexe === v} onClick={() => maj("sexe", v)}>{l}</button>
                          ))}
                        </div>
                      </div>
                      {champ("date_naissance", "Date de naissance", { type: "date" })}
                      {champ("lieu_naissance", "Lieu de naissance", { exemple: "ex. Gitega" })}
                    </div>
                  </div>

                  <div className={`fiche-section${sectionComplete(["telephone", "adresse"]) ? " complete" : ""}`}>
                    <h3><span className="num">2</span>Contact et famille{sectionComplete(["telephone", "adresse"]) && <span className="ok"><BadgeCheck size={15} />Complet</span>}</h3>
                    <div className="fiche-grille">
                      {champ("telephone", "Téléphone (WhatsApp)", { type: "tel", exemple: "+257 79 00 00 00" })}
                      {champ("adresse", "Colline ou quartier", { exemple: "ex. Colline Mweya" })}
                      <Champ libelle="Situation familiale">
                        <select value={f.situation_familiale} onChange={(e) => maj("situation_familiale", e.target.value)}>
                          {SITUATIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                        </select>
                      </Champ>
                      {champ("profession", "Profession", { exemple: "ex. Enseignante" })}
                    </div>
                  </div>

                  <div className={`fiche-section${sectionComplete(["paroisse", "statut", "date_adhesion"]) ? " complete" : ""}`}>
                    <h3><span className="num">3</span>Vie de l'Église{sectionComplete(["paroisse", "statut", "date_adhesion"]) && <span className="ok"><BadgeCheck size={15} />Complet</span>}</h3>
                    <div className="fiche-grille">
                      <div className={requis("paroisse") || undefined} style={{ display: "contents" }}><Champ libelle="Église locale *" large>
                        <select value={f.paroisse} onChange={(e) => maj("paroisse", e.target.value)}>
                          <option value="">Choisir l'église locale…</option>
                          {(paroisses || []).map((p) => <option key={p.id} value={p.id}>{p.nom}{p.district_nom ? ` — ${p.district_nom}` : ""}</option>)}
                        </select>
                      </Champ></div>
                      <Champ libelle="Statut dans l'Église *">
                        <select value={f.statut} onChange={(e) => maj("statut", e.target.value)}>
                          {STATUTS.map((x) => <option key={x.v} value={x.v}>{x.l}</option>)}
                        </select>
                      </Champ>
                      {champ("date_adhesion", "Date d'adhésion", { type: "date" })}
                      {champ("date_bapteme", "Date du baptême", { type: "date" })}
                      {champ("date_confirmation", "Date de confirmation", { type: "date" })}
                      <Champ libelle="Ministère ou groupe" large>
                        <input list="ministeres" value={f.ministere} onChange={(e) => maj("ministere", e.target.value)} placeholder="ex. Chorale" />
                        <datalist id="ministeres">{MINISTERES.map((m) => <option key={m} value={m} />)}</datalist>
                      </Champ>
                      <Champ libelle="Observations" large>
                        <textarea rows={2} value={f.notes} onChange={(e) => maj("notes", e.target.value)} placeholder="Transfert depuis une autre église, parrain, remarques…" />
                      </Champ>
                    </div>
                  </div>

                  <div className="fiche-pied">
                    <div className="barre-completude">
                      <div className="piste"><span style={{ width: `${progression}%` }} /></div>
                      <small>{pret ? "Tout l'obligatoire est rempli. Les autres informations peuvent être complétées plus tard."
                        : `Encore ${manquants.length} information(s) obligatoire(s) : ${manquants.map((k) => ({ nom: "nom", prenom: "prénom", sexe: "sexe", paroisse: "église locale", statut: "statut", date_adhesion: "date d'adhésion" }[k])).join(", ")}.`}</small>
                    </div>
                    <div style={{ display: "flex", gap: 10 }}>
                      {(edition || progression > 0) && <button className="bouton" type="button" onClick={reinitialiser}>{edition ? "Annuler" : "Vider"}</button>}
                      <button className="bouton principal enorme" disabled={!pret || envoi || (doublon && !confirmer)} onClick={enregistrer}>
                        {envoi ? <Loader2 className="tourne" /> : <UserPlus />}{edition ? "Enregistrer les modifications" : "Enregistrer le membre"}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </section>
        )}

        <Carte brut titre="Registre" description="Les fiches les plus récentes en premier. Cliquez sur une ligne pour la modifier."
          actions={
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <div className="recherche-ui" style={{ position: "relative" }}>
                <Search size={15} style={{ position: "absolute", left: 10, top: 11, color: "var(--encre-3)" }} />
                <input className="saisie-ui" style={{ paddingLeft: 32, width: 230 }} placeholder="Nom, numéro, téléphone…" value={q}
                  onChange={(e) => { setQ(e.target.value); setPage(1); }} />
              </div>
              <select className="saisie-ui" value={paroisseFiltre} onChange={(e) => { setParoisseFiltre(e.target.value); setPage(1); }} aria-label="Église locale">
                <option value="">Toutes les églises</option>
                {(paroisses || []).map((p) => <option key={p.id} value={p.id}>{p.nom}</option>)}
              </select>
            </div>
          }>
          <div style={{ padding: "0 20px 12px" }}>
            <Segments label="Statut" valeur={statut} onChange={(v) => { setStatut(v); setPage(1); }}
              options={[{ id: "", libelle: "Tous" }, ...STATUTS.map((x) => ({ id: x.v, libelle: x.l, nb: s?.par_statut?.find((p) => p.statut === x.v)?.n }))]} />
          </div>
          <Etat chargement={liste.chargement && !liste.donnees} erreur={liste.erreur}>
            {resultats.length === 0 ? <Vide icone={Users} titre="Aucune fiche" texte="Aucun membre ne correspond à ces critères." /> : (
              <div className="defilement"><table className="tableau">
                <thead><tr><th>Membre</th><th>N°</th><th>Église locale</th><th>Statut</th><th>Ministère</th><th>Adhésion</th><th /></tr></thead>
                <tbody>{resultats.map((m) => (
                  <tr key={m.id} onClick={() => ecriture && modifier(m)} style={{ cursor: ecriture ? "pointer" : undefined }}>
                    <td><div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                      <span className="avatar-membre">{m.photo ? <img src={m.photo} alt="" /> : initiales(m)}</span>
                      <div><div className="principal-cell">{m.prenom} {m.nom}</div>
                        <div className="secondaire">{[m.sexe_libelle, m.telephone].filter(Boolean).join(" · ")}</div></div>
                    </div></td>
                    <td className="chiffre" style={{ whiteSpace: "nowrap" }}>{m.numero}</td>
                    <td>{m.paroisse_nom}<div className="secondaire">{m.district_nom}</div></td>
                    <td><span className={`badge ${TON[m.statut] || ""}`}>{m.statut_libelle}</span></td>
                    <td className="secondaire">{m.ministere || "—"}</td>
                    <td className="chiffre">{dateFr(m.date_adhesion)}</td>
                    <td className="num" style={{ whiteSpace: "nowrap" }} onClick={(e) => e.stopPropagation()}>
                      {gereAcces && m.actif && !m.compte && <button className="icone-bouton" title="Donner l'accès à l'espace membre" onClick={() => donnerAcces(m)}><KeyRound size={16} /></button>}
                      {m.compte && <span className="icone-bouton" title="A un accès à l'espace membre" style={{ color: "var(--succes)", cursor: "default" }}><UserCheck size={16} /></span>}
                      {ecriture && <button className="icone-bouton" title="Modifier" onClick={() => modifier(m)}><Pencil size={16} /></button>}
                      <button className="icone-bouton" title="Imprimer la carte" onClick={() => imprimerCarte(m, org)}><Printer size={16} /></button>
                    </td>
                  </tr>
                ))}</tbody>
              </table></div>
            )}
          </Etat>
          <div className="carte-pied"><Pagination page={page} total={liste.donnees?.count || 0} parPage={25} onChange={setPage} unite="membres" /></div>
          {identifiants && <IdentifiantsModale resultats={identifiants} org={org} onFermer={() => setIdentifiants(null)} />}
        </Carte>

        {s?.eglises?.length > 0 && (
          <Carte titre="Avancement de l'enregistrement par église locale" description="Fiches actives comparées à l'effectif déclaré par chaque église.">
            <div className="defilement"><table className="tableau">
              <thead><tr><th>Église locale</th><th>District</th><th className="num">Déclarés</th><th className="num">Enregistrés</th><th style={{ minWidth: 180 }}>Avancement</th></tr></thead>
              <tbody>{s.eglises.slice(0, 12).map((e) => (
                <tr key={e.id}>
                  <td className="principal-cell">{e.nom}</td><td>{e.district}</td>
                  <td className="num chiffre">{nombre(e.declares)}</td><td className="num chiffre">{nombre(e.inscrits)}</td>
                  <td><div className="barre-completude" style={{ minWidth: 160 }}><div className="piste" style={{ height: 8 }}>
                    <span style={{ width: `${Math.min(100, Math.max(e.taux || 0, e.inscrits ? 2 : 0))}%` }} /></div>
                    <small>{e.taux != null ? `${e.taux.toLocaleString("fr-FR")} %` : "effectif non déclaré"}</small></div></td>
                </tr>
              ))}</tbody>
            </table></div>
          </Carte>
        )}
      </div>
    </>
  );
}
