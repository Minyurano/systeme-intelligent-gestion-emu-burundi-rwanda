import { useEffect, useRef, useState } from "react";
import {
  Building2, Camera, FileBadge, HandCoins, CheckCircle2, Church, Clock, FolderKanban, Home, IdCard, Loader2, LogOut, MessageSquareWarning, Moon, Pencil,
  Phone, Printer, Save, ShieldCheck, Sun, UserRound, Users, X, XCircle,
} from "lucide-react";
import { api } from "../api";
import { useAuth } from "../auth";
import { CarteMembre, imprimerCarte, initiales } from "../components/CarteMembre";
import { CarteMotDePasse } from "../components/MotDePasse";
import { imprimerAttestation, imprimerRecu } from "../components/Recus";
import { Bandeau, Carte, Champ, Etat, Progres, useApi, useToast, Vide } from "../components/ui";
import { useTheme } from "../theme";
import { bif, date as dateFr, dateHeure, nombre } from "../format";

const SECTIONS = [
  { id: "accueil", libelle: "Accueil", icone: Home },
  { id: "fiche", libelle: "Ma fiche", icone: IdCard },
  { id: "dons", libelle: "Mes dons", icone: HandCoins },
  { id: "eglise", libelle: "Mon église", icone: Church },
  { id: "signaler", libelle: "Signaler", icone: MessageSquareWarning },
  { id: "securite", libelle: "Sécurité", icone: ShieldCheck },
];
const SITUATIONS = [["", "—"], ["CELIBATAIRE", "Célibataire"], ["MARIE", "Marié(e)"], ["VEUF", "Veuf / veuve"], ["DIVORCE", "Divorcé(e)"]];
const TON_ETAT = { BON: "bon", MOYEN: "attention", MAUVAIS: "critique", CONSTRUCTION: "info" };
const TON_SIGNALEMENT = { EN_ATTENTE: "attention", VALIDEE: "bon", REJETEE: "critique" };

export default function EspaceMembre() {
  const { moi, deconnexion } = useAuth();
  const { theme, basculer } = useTheme();
  const [section, setSection] = useState(() => (window.location.hash || "").slice(1) || "accueil");
  const [version, setVersion] = useState(0);
  const espace = useApi(`espace-membre/?v=${version}`, [version]);
  const e = espace.donnees;
  const recharger = () => setVersion((v) => v + 1);
  const aller = (id) => {
    setSection(id);
    window.history.replaceState(null, "", `#${id}`);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  useEffect(() => {
    document.title = `Espace membre — ${moi.organisation?.sigle || "UMURAGE"}`;
  }, [moi]);

  return (
    <div className="espace-membre">
      <header className="em-haut">
        <div className="em-marque">
          <img src="/logo.svg" alt="" width="32" height="32" />
          <div><strong>{moi.organisation?.nom}</strong><span>Espace membre</span></div>
        </div>
        <div className="em-actions">
          <button className="icone-bouton" onClick={basculer} aria-label={theme === "dark" ? "Thème clair" : "Thème sombre"}>{theme === "dark" ? <Sun /> : <Moon />}</button>
          <span className="avatar" aria-hidden="true">{initiales({ prenom: moi.nom.split(" ")[0], nom: moi.nom.split(" ").slice(-1)[0] })}</span>
          <button className="bouton petit" onClick={deconnexion} aria-label="Déconnexion"><LogOut /><span className="libelle">Déconnexion</span></button>
        </div>
      </header>
      <nav className="em-nav" aria-label="Sections de l'espace membre">
        {SECTIONS.map((s) => (
          <button key={s.id} aria-current={section === s.id ? "page" : undefined} onClick={() => aller(s.id)}>
            <s.icone />{s.libelle}
            {s.id === "signaler" && e?.signalements_en_attente > 0 && <span className="compteur attention">{e.signalements_en_attente}</span>}
          </button>
        ))}
      </nav>
      <main className="em-contenu" id="contenu">
        <Etat chargement={espace.chargement && !e} erreur={espace.erreur} lignes={6}>
          {e && section === "accueil" && <Accueil e={e} org={moi.organisation} aller={aller} />}
          {e && section === "fiche" && <MaFiche e={e} org={moi.organisation} onFait={recharger} />}
          {e && section === "dons" && <MesDons org={moi.organisation} fiche={e.fiche} />}
          {e && section === "eglise" && <MonEglise e={e} />}
          {e && section === "signaler" && <Signaler e={e} onFait={recharger} />}
          {section === "securite" && <div className="pile"><CarteMotDePasse /><Bandeau type="info">Votre mot de passe est personnel : ni le pasteur ni l'administrateur ne le connaissent. En cas d'oubli, demandez à l'administrateur un nouveau mot de passe provisoire.</Bandeau></div>}
        </Etat>
      </main>
      <footer className="em-pied">UMURAGE · {moi.organisation?.sigle}{e?.organisation?.portail_public && <> · <a href={`/public/${e.organisation.slug}`} target="_blank" rel="noreferrer">Portail de transparence</a></>}</footer>
    </div>
  );
}

function Accueil({ e, org, aller }) {
  const f = e.fiche;
  const heure = new Date().getHours();
  return (
    <div className="pile">
      <section className="em-bienvenue">
        <div>
          <p className="muet petit">{heure < 12 ? "Bonjour" : heure < 18 ? "Bon après-midi" : "Bonsoir"},</p>
          <h1>{f.prenom} {f.nom}</h1>
          <p>{f.statut_libelle} de l'église de <b>{f.paroisse_nom}</b>, district de {f.district_nom}.{f.ministere ? ` ${f.ministere}.` : ""}</p>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 14 }}>
            <button className="bouton principal" onClick={() => aller("signaler")}><MessageSquareWarning />Signaler un problème</button>
            <button className="bouton" onClick={() => imprimerCarte(f, org)}><Printer />Imprimer ma carte</button>
          </div>
        </div>
        <div className="em-carte"><CarteMembre m={f} org={org} photo={f.photo} /></div>
      </section>
      <div className="grille g3">
        <button className="em-tuile" onClick={() => aller("eglise")}>
          <Users /><b>{nombre(e.eglise.membres_inscrits)}</b><span>membres inscrits à {e.eglise.nom}</span>
        </button>
        <button className="em-tuile" onClick={() => aller("eglise")}>
          <Building2 /><b>{nombre(e.biens.length)}</b><span>biens de votre église et du district</span>
        </button>
        <button className="em-tuile" onClick={() => aller("eglise")}>
          <FolderKanban /><b>{nombre(e.projets.length)}</b><span>projets dans le district de {e.eglise.district}</span>
        </button>
      </div>
      <Carte titre="Vos responsables">
        <div className="grille g2">
          <Contact titre="Pasteur" nom={e.eglise.pasteur} />
          <Contact titre="Surintendant du district" nom={e.eglise.surintendant} />
        </div>
        {e.organisation.whatsapp && <p className="petit" style={{ marginTop: 12 }}><Phone size={14} style={{ verticalAlign: "-2px" }} /> WhatsApp de l'Église : <a href={`https://wa.me/${e.organisation.whatsapp.replace(/\D/g, "")}`} target="_blank" rel="noreferrer">{e.organisation.whatsapp}</a> (envoyez AIDE pour les commandes)</p>}
      </Carte>
    </div>
  );
}

const Contact = ({ titre, nom }) => (
  <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
    <span className="avatar">{nom ? initiales({ prenom: nom.replace(/^(Rév\.?|Pasteur|Pst\.?)\s+/i, ""), nom: nom.split(" ").slice(-1)[0] }) : <UserRound size={16} />}</span>
    <div><div className="petit muet">{titre}</div><b>{nom || "Non renseigné"}</b></div>
  </div>
);

function MaFiche({ e, org, onFait }) {
  const notifier = useToast();
  const f = e.fiche;
  const [edition, setEdition] = useState(false);
  const [c, setC] = useState({ telephone: f.telephone, adresse: f.adresse, profession: f.profession, situation_familiale: f.situation_familiale });
  const [encours, setEncours] = useState(false);
  const [erreur, setErreur] = useState("");
  async function enregistrer() {
    setEncours(true);
    setErreur("");
    try {
      const r = await api("espace-membre/coordonnees/", { methode: "PATCH", corps: c });
      notifier(r.modifies.length ? "Vos coordonnées sont à jour." : "Aucun changement.");
      setEdition(false);
      onFait();
    } catch (err) {
      setErreur(err.message);
    }
    setEncours(false);
  }
  const ligne = (libelle, valeur) => <div key={libelle}><dt>{libelle}</dt><dd>{valeur || <span className="muet">—</span>}</dd></div>;
  return (
    <div className="grille g-3-2">
      <div className="pile">
        <Carte brut titre="Ma fiche du registre" description={`N° de membre ${f.numero} : il est définitif et figure sur votre carte.`}>
          <dl className="proprietes" style={{ borderTop: "1px solid var(--trait)", margin: 0 }}>
            {ligne("Nom", `${f.prenom} ${f.nom}`)}
            {ligne("Sexe", f.sexe === "F" ? "Femme" : "Homme")}
            {ligne("Naissance", [f.date_naissance && dateFr(f.date_naissance), f.lieu_naissance].filter(Boolean).join(", "))}
            {ligne("Statut", f.statut_libelle)}
            {ligne("Membre depuis", dateFr(f.date_adhesion))}
            {ligne("Baptême", f.date_bapteme && dateFr(f.date_bapteme))}
            {ligne("Confirmation", f.date_confirmation && dateFr(f.date_confirmation))}
            {ligne("Ministère", f.ministere)}
            {ligne("Église locale", `${f.paroisse_nom}, ${f.district_nom}`)}
          </dl>
          <p className="petit muet" style={{ padding: "12px 20px 16px", margin: 0 }}>Une erreur dans votre nom, vos dates ou votre statut ? Seul votre pasteur peut corriger ces informations officielles.</p>
        </Carte>
        <Carte brut titre="Mes coordonnées" description="Vous pouvez les tenir à jour vous-même."
          actions={!edition && <button className="bouton petit" onClick={() => setEdition(true)}><Pencil />Modifier</button>}>
          {erreur && <Bandeau type="erreur" style={{ margin: "0 20px 12px" }}>{erreur}</Bandeau>}
          {edition ? (
            <div className="formulaire" style={{ padding: "4px 20px 20px" }}>
              <Champ libelle="Téléphone" aide="Sert aussi aux signalements par WhatsApp."><input value={c.telephone} onChange={(x) => setC({ ...c, telephone: x.target.value })} inputMode="tel" placeholder="+257…" /></Champ>
              <Champ libelle="Situation familiale"><select value={c.situation_familiale} onChange={(x) => setC({ ...c, situation_familiale: x.target.value })}>{SITUATIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></Champ>
              <Champ libelle="Adresse (colline, quartier)" large><input value={c.adresse} onChange={(x) => setC({ ...c, adresse: x.target.value })} /></Champ>
              <Champ libelle="Profession" large><input value={c.profession} onChange={(x) => setC({ ...c, profession: x.target.value })} /></Champ>
              <div className="large" style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
                <button className="bouton" onClick={() => setEdition(false)}>Annuler</button>
                <button className="bouton principal" onClick={enregistrer} disabled={encours}>{encours ? <Loader2 className="tourne" /> : <Save />}Enregistrer</button>
              </div>
            </div>
          ) : (
            <dl className="proprietes" style={{ borderTop: "1px solid var(--trait)", margin: 0 }}>
              {ligne("Téléphone", f.telephone)}
              {ligne("Adresse", f.adresse)}
              {ligne("Profession", f.profession)}
              {ligne("Situation familiale", f.situation_libelle)}
            </dl>
          )}
        </Carte>
      </div>
      <Carte titre="Ma carte de membre">
        <CarteMembre m={f} org={org} photo={f.photo} />
        <button className="bouton" style={{ marginTop: 14, width: "100%" }} onClick={() => imprimerCarte(f, org)}><Printer />Imprimer ma carte</button>
      </Carte>
    </div>
  );
}

function MonEglise({ e }) {
  const g = e.eglise;
  return (
    <div className="pile">
      <Carte titre={`Église de ${g.nom}`} description={`District de ${g.district}${g.siege ? `, siège à ${g.siege}` : ""}`}>
        <div className="grille g4 em-chiffres">
          <div><b>{nombre(g.membres_inscrits)}</b><span>membres inscrits</span></div>
          <div><b>{g.membres_declares ? nombre(g.membres_declares) : "—"}</b><span>membres déclarés</span></div>
          <div><b>{nombre(g.nouveaux_annee)}</b><span>nouveaux cette année</span></div>
          <div><b>{nombre(g.baptemes_annee)}</b><span>baptêmes cette année</span></div>
        </div>
      </Carte>
      <Carte brut titre="Le patrimoine de notre église" description="Ce que l'Église possède et entretient pour la communauté. Un problème ? Signalez-le.">
        {e.biens.length === 0 ? <Vide icone={Building2} titre="Aucun bien enregistré" texte="Le recensement de votre église n'est pas encore fait." /> : (
          <div className="em-biens">
            {e.biens.map((b) => (
              <article key={b.id} className="em-bien">
                <div className="photo">{b.photo ? <img src={b.photo} alt="" loading="lazy" /> : <Building2 />}</div>
                <div>
                  <b>{b.nom}</b>
                  <div className="secondaire">{b.sous_type || b.categorie_libelle} · <span className="code">{b.code}</span></div>
                  <span className={`badge ${TON_ETAT[b.etat] || ""}`}>{b.etat_libelle}</span>
                  {b.beneficiaires > 0 && <span className="secondaire"> · {nombre(b.beneficiaires)} bénéficiaires</span>}
                </div>
              </article>
            ))}
          </div>
        )}
      </Carte>
      <Carte titre="Projets du district" description="Les projets publiés par l'Église, avec leur avancement.">
        {e.projets.length === 0 ? <p className="muet">Aucun projet publié pour le moment.</p> : (
          <div className="pile" style={{ gap: 14 }}>
            {e.projets.map((p) => (
              <div key={p.id}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
                  <b>{p.nom}</b>
                  <span className="petit muet">{p.domaine} · {p.statut_libelle}{p.financeur ? ` · avec ${p.financeur}` : ""}</span>
                </div>
                <div style={{ display: "flex", gap: 10, alignItems: "center", marginTop: 6 }}>
                  <div style={{ flex: 1 }}><Progres valeur={p.avancement} /></div>
                  <span className="petit chiffre">{p.avancement} %</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </Carte>
    </div>
  );
}

function Signaler({ e, onFait }) {
  const notifier = useToast();
  const [texte, setTexte] = useState("");
  const [bien, setBien] = useState("");
  const [photo, setPhoto] = useState(null);
  const [apercu, setApercu] = useState(null);
  const [encours, setEncours] = useState(false);
  const [erreur, setErreur] = useState("");
  const [v, setV] = useState(0);
  const liste = useApi(`espace-membre/signalements/?v=${v}`, [v]);
  const entree = useRef(null);
  useEffect(() => () => apercu && URL.revokeObjectURL(apercu), [apercu]);

  function choisir(x) {
    const fichier = x.target.files?.[0];
    if (!fichier) return;
    if (fichier.size > 5 * 1024 * 1024) return notifier("La photo dépasse 5 Mo.", "erreur");
    setPhoto(fichier);
    setApercu(URL.createObjectURL(fichier));
  }
  async function envoyer(x) {
    x.preventDefault();
    setEncours(true);
    setErreur("");
    try {
      const corps = new FormData();
      corps.append("texte", texte);
      if (bien) corps.append("bien", bien);
      if (photo) corps.append("photo", photo);
      await api("espace-membre/signalements/", { methode: "POST", corps });
      notifier("Merci ! Votre signalement a été transmis au responsable du district.");
      setTexte(""); setBien(""); setPhoto(null); setApercu(null);
      setV((n) => n + 1);
      onFait();
    } catch (err) {
      setErreur(err.message);
    }
    setEncours(false);
  }
  const icone = { EN_ATTENTE: Clock, VALIDEE: CheckCircle2, REJETEE: XCircle };
  return (
    <div className="grille g-3-2">
      <Carte titre="Signaler un problème" description="Un toit qui fuit, un forage en panne, un bien abîmé ou disparu : le responsable du district est prévenu et vous suivez la suite ici.">
        <form className="pile" onSubmit={envoyer} style={{ gap: 14 }}>
          {erreur && <Bandeau type="erreur">{erreur}</Bandeau>}
          <label className="champ">Quel bien est concerné ?
            <select value={bien} onChange={(x) => setBien(x.target.value)}>
              <option value="">Je ne sais pas / autre</option>
              {e.biens.map((b) => <option key={b.id} value={b.id}>{b.nom} ({b.code})</option>)}
            </select>
          </label>
          <label className="champ">Décrivez le problème
            <textarea rows={4} value={texte} onChange={(x) => setTexte(x.target.value)} required minLength={10} maxLength={1500}
              placeholder="ex. Depuis la pluie de mardi, le toit de la salle de classe fuit au-dessus du tableau." />
          </label>
          <div>
            <input ref={entree} type="file" accept="image/*" capture="environment" hidden onChange={choisir} />
            {apercu ? (
              <div className="em-apercu"><img src={apercu} alt="Photo jointe" /><button type="button" className="icone-bouton" aria-label="Retirer la photo" onClick={() => { setPhoto(null); setApercu(null); }}><X /></button></div>
            ) : <button type="button" className="bouton" onClick={() => entree.current?.click()}><Camera />Ajouter une photo</button>}
          </div>
          <div><button className="bouton principal" disabled={encours || texte.trim().length < 10}>{encours ? <Loader2 className="tourne" /> : <MessageSquareWarning />}Envoyer le signalement</button></div>
        </form>
      </Carte>
      <Carte titre="Mes signalements">
        <Etat chargement={liste.chargement && !liste.donnees} erreur={liste.erreur}>
          {(liste.donnees || []).length === 0 ? <p className="muet">Vous n'avez encore rien signalé.</p> : (
            <ul className="em-signalements">
              {liste.donnees.map((s) => {
                const Ic = icone[s.statut] || Clock;
                return (
                  <li key={s.id}>
                    <Ic className={TON_SIGNALEMENT[s.statut]} />
                    <div>
                      <div className="petit muet">N° {s.id} · {dateHeure(s.recue_le)}{s.bien_signale ? ` · ${s.bien_signale.nom}` : ""}</div>
                      <p>{s.texte}</p>
                      <span className={`badge ${TON_SIGNALEMENT[s.statut] || ""}`}>{s.statut_libelle}</span>
                      {s.motif_rejet && <span className="petit muet"> : {s.motif_rejet}</span>}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </Etat>
      </Carte>
    </div>
  );
}

const MOIS_COURTS = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"];

function MesDons({ org, fiche }) {
  const notifier = useToast();
  const [annee, setAnnee] = useState(new Date().getFullYear());
  const d = useApi(`espace-membre/contributions/?annee=${annee}`, [annee]);
  const [encours, setEncours] = useState(false);
  const r = d.donnees;
  const max = r ? Math.max(1, ...r.par_mois.map((m) => Number(m.total))) : 1;
  const enCours = annee === new Date().getFullYear();

  async function attestation() {
    setEncours(true);
    try {
      imprimerAttestation(await api("espace-membre/attestation/", { methode: "POST", corps: { annee } }));
    } catch (err) {
      notifier(err.message, "erreur");
    }
    setEncours(false);
  }
  return (
    <div className="pile">
      <Etat chargement={d.chargement && !r} erreur={d.erreur}>
        {r && (
          <>
            <section className="em-dons-tete">
              <div>
                <label className="petit muet" htmlFor="annee-dons">Année</label>
                <select id="annee-dons" className="saisie-ui" value={annee} onChange={(x) => setAnnee(+x.target.value)}>
                  {r.annees.map((a) => <option key={a} value={a}>{a}</option>)}
                </select>
              </div>
              <div className="em-dons-total">
                <span>Mes contributions {annee}</span>
                <b>{bif(r.total)}</b>
                <small>{nombre(r.nombre)} versement{r.nombre > 1 ? "s" : ""}{enCours ? " depuis le 1er janvier" : ""}</small>
              </div>
              <button className="bouton principal" onClick={attestation} disabled={encours || !r.nombre}>
                {encours ? <Loader2 className="tourne" /> : <FileBadge />}{enCours ? "Attestation provisoire" : `Attestation ${annee}`}
              </button>
            </section>
            <div className="grille g2">
              <Carte titre="Mois par mois">
                <div className="em-mois" role="img" aria-label={`Contributions par mois en ${annee}`}>
                  {r.par_mois.map((m) => (
                    <div key={m.mois} title={`${MOIS_COURTS[m.mois - 1]} : ${bif(m.total)}`}>
                      <span style={{ height: `${(100 * Number(m.total)) / max}%` }} className={Number(m.total) ? "" : "nul"} />
                      <small>{MOIS_COURTS[m.mois - 1]}</small>
                    </div>
                  ))}
                </div>
              </Carte>
              <Carte titre="Par nature">
                {r.par_type.length === 0 ? <p className="muet">Aucune contribution enregistrée cette année.</p> : (
                  <div className="pile" style={{ gap: 12 }}>
                    {r.par_type.map((t) => (
                      <div key={t.type}>
                        <div style={{ display: "flex", justifyContent: "space-between" }}><span>{t.libelle}</span><b className="chiffre">{bif(t.total)}</b></div>
                        <Progres valeur={(100 * Number(t.total)) / Number(r.total || 1)} />
                      </div>
                    ))}
                  </div>
                )}
              </Carte>
            </div>
            <Carte brut titre="Mes reçus" description="Un reçu manque ou une somme est fausse ? Signalez-le au trésorier de votre église avec le numéro du reçu.">
              {r.contributions.length === 0 ? <p className="muet" style={{ padding: "0 20px 20px" }}>Aucun reçu pour cette année.</p> : (
                <div className="defilement"><table className="tableau">
                  <thead><tr><th>Date</th><th>Reçu</th><th>Nature</th><th className="masquer-mobile">Mode</th><th className="num">Montant</th><th /></tr></thead>
                  <tbody>{r.contributions.map((c) => (
                    <tr key={c.id}>
                      <td className="chiffre">{dateFr(c.date)}</td><td className="code">{c.recu}</td><td>{c.type}</td>
                      <td className="masquer-mobile secondaire">{c.mode}</td><td className="num chiffre">{bif(c.montant)}</td>
                      <td className="num"><button className="icone-bouton" title="Imprimer le reçu"
                        onClick={() => imprimerRecu({ numero_recu: c.recu, montant: c.montant, date: c.date, type_libelle: c.type, mode_libelle: c.mode,
                          membre_nom: `${fiche.prenom} ${fiche.nom}`, membre_numero: fiche.numero, paroisse_nom: fiche.paroisse_nom, district_nom: fiche.district_nom }, org)}>
                        <Printer size={16} /></button></td>
                    </tr>
                  ))}</tbody>
                </table></div>
              )}
            </Carte>
            {r.attestations.length > 0 && (
              <p className="petit muet">Attestations déjà émises : {r.attestations.map((a) => `${a.annee}${a.definitive ? "" : " (provisoire)"} · code ${a.code}`).join(" ; ")}.</p>
            )}
          </>
        )}
      </Etat>
    </div>
  );
}
