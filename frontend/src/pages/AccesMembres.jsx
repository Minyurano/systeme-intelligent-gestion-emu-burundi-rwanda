import { useEffect, useState } from "react";
import {
  BadgeCheck, CheckCircle2, Clock, Eye, EyeOff, Inbox, KeyRound, Link2, Loader2, LogIn, RotateCcw, Search, Settings2, ShieldBan,
  ShieldCheck, Trash2, UserCheck, Users, X,
} from "lucide-react";
import { api } from "../api";
import { useAuth } from "../auth";
import IdentifiantsModale from "../components/IdentifiantsAcces";
import { Bandeau, Carte, Champ, EnTete, Etat, Kpi, Modale, Onglets, Pagination, Segments, useApi, useToast, Vide } from "../components/ui";
import { dateHeure, nombre } from "../format";

const ETATS = [
  { id: "", libelle: "Tous" },
  { id: "sans", libelle: "Sans accès" },
  { id: "avec", libelle: "Accès actif" },
  { id: "attente", libelle: "1re connexion attendue" },
  { id: "suspendu", libelle: "Suspendus" },
];

export default function AccesMembres() {
  const { moi } = useAuth();
  const [onglet, setOnglet] = useState("membres");
  const [version, setVersion] = useState(0);
  const stats = useApi(`acces-membres/statistiques/?v=${version}`, [version]);
  const s = stats.donnees;
  const recharger = () => setVersion((v) => v + 1);
  return (
    <>
      <EnTete titre="Accès des membres"
        sousTitre="Les administrateurs ouvrent l'espace membre aux fidèles inscrits au registre. Un membre voit sa fiche, sa carte, son église locale et ses signalements, jamais les finances ni la gestion." />
      <div className="pile">
        <div className="kpis">
          <Kpi libelle="Membres actifs au registre" icone={Users} ton="info" valeur={s ? nombre(s.membres_actifs) : "…"} note={s ? `${nombre(s.sans_acces)} sans accès` : ""} />
          <Kpi libelle="Accès ouverts" icone={UserCheck} ton="bon" valeur={s ? nombre(s.avec_acces) : "…"}
            note={s?.membres_actifs ? `${Math.round((100 * s.avec_acces) / s.membres_actifs)} % des membres actifs` : ""} />
          <Kpi libelle="Première connexion attendue" icone={Clock} ton={s?.en_attente_premiere_connexion ? "attention" : "bon"}
            valeur={s ? nombre(s.en_attente_premiere_connexion) : "…"} note="mot de passe provisoire pas encore changé" />
          <Kpi libelle="Demandes d'accès" icone={Inbox} ton={s?.demandes_en_attente ? "attention" : "bon"} valeur={s ? nombre(s.demandes_en_attente) : "…"}
            note={s ? (s.demandes_ouvertes ? "formulaire public ouvert" : "formulaire public fermé") : ""} />
        </div>
        <div>
          <Onglets actif={onglet} onChange={setOnglet} onglets={[
            { id: "membres", libelle: "Membres", icone: Users },
            { id: "demandes", libelle: "Demandes", icone: Inbox, nb: s?.demandes_en_attente || undefined },
            { id: "reglages", libelle: "Réglages", icone: Settings2 },
          ]} />
          {onglet === "membres" && <ListeAcces org={moi.organisation} onChange={recharger} version={version} />}
          {onglet === "demandes" && <Demandes org={moi.organisation} onChange={recharger} />}
          {onglet === "reglages" && <Reglages ouvertes={s?.demandes_ouvertes} onChange={recharger} />}
        </div>
      </div>
    </>
  );
}

function BadgeAcces({ m }) {
  const a = m.acces;
  if (!a) return m.actif ? <span className="badge">Pas d'accès</span> : <span className="badge muet">{m.statut_libelle}</span>;
  if (!a.actif) return <span className="badge critique">Suspendu</span>;
  if (a.doit_changer_mdp) return <span className="badge attention">En attente de 1re connexion</span>;
  return <span className="badge bon">Actif{a.double_authentification ? " · 2FA" : ""}</span>;
}

function ListeAcces({ org, onChange, version }) {
  const notifier = useToast();
  const [q, setQ] = useState("");
  const [etat, setEtat] = useState("");
  const [paroisse, setParoisse] = useState("");
  const [page, setPage] = useState(1);
  const [v, setV] = useState(0);
  const [selection, setSelection] = useState(new Set());
  const [whatsapp, setWhatsapp] = useState(false);
  const [resultats, setResultats] = useState(null);
  const [encours, setEncours] = useState(null);
  const [confirmation, setConfirmation] = useState(null);
  const [accord, setAccord] = useState(null);
  const [ignores, setIgnores] = useState([]);
  const { donnees: paroisses } = useApi("paroisses/");
  const filtres = new URLSearchParams({ page, ...(q && { search: q }), ...(etat && { etat }), ...(paroisse && { paroisse }) }).toString();
  const liste = useApi(`acces-membres/?${filtres}&v=${v}-${version}`, [filtres, v, version]);
  const lignes = liste.donnees?.results || [];
  useEffect(() => setSelection(new Set()), [filtres]);

  const actualiser = () => { setV((x) => x + 1); onChange(); };
  async function agir(m, quoi, corps = {}) {
    setEncours(`${m.id}-${quoi}`);
    try {
      const r = await api(`acces-membres/${m.id}/${quoi}/`, { methode: "POST", corps: { envoyer_whatsapp: whatsapp, ...corps } });
      if (r?.mot_de_passe) setResultats(r);
      else notifier({ suspendre: "Accès suspendu.", reactiver: "Accès rétabli.", retirer: "Accès retiré ; la fiche du registre est conservée." }[quoi]);
      setAccord(null);
      actualiser();
    } catch (e) {
      // Membre mineur : on demande l'accord d'un parent ou tuteur, puis on recommence
      if (e.details?.code === "accord_parental_requis") setAccord({ m, age: e.details.age, minimum: e.details.age_minimum });
      else notifier(e.message, "erreur");
    }
    setEncours(null);
    setConfirmation(null);
  }
  async function groupe(corps) {
    setEncours("groupe");
    try {
      const r = await api("acces-membres/accorder-groupe/", { methode: "POST", corps: { envoyer_whatsapp: whatsapp, ...corps } });
      if (r.crees.length) setResultats(r.crees);
      setIgnores(r.ignores || []);
      if (r.limite_atteinte) notifier("500 accès ouverts : relancez pour les membres suivants.", "erreur");
      setSelection(new Set());
      actualiser();
    } catch (e) {
      notifier(e.message, "erreur");
    }
    setEncours(null);
    setConfirmation(null);
  }
  const eligibles = lignes.filter((m) => !m.acces && m.actif);
  const basculer = (id) => setSelection((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const tousCoches = eligibles.length > 0 && eligibles.every((m) => selection.has(m.id));
  const nomParoisse = (paroisses || []).find((p) => String(p.id) === String(paroisse))?.nom;

  return (
    <Carte brut titre="Membres et accès" description="Cochez des membres pour leur ouvrir l'accès en une fois, ou choisissez une église locale."
      actions={
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <div style={{ position: "relative" }}>
            <Search size={15} style={{ position: "absolute", left: 10, top: 11, color: "var(--encre-3)" }} />
            <input className="saisie-ui" style={{ paddingLeft: 32, width: 220 }} placeholder="Nom, numéro, téléphone…" value={q}
              onChange={(e) => { setQ(e.target.value); setPage(1); }} aria-label="Rechercher un membre" />
          </div>
          <select className="saisie-ui" value={paroisse} onChange={(e) => { setParoisse(e.target.value); setPage(1); }} aria-label="Église locale">
            <option value="">Toutes les églises</option>
            {(paroisses || []).map((p) => <option key={p.id} value={p.id}>{p.nom}</option>)}
          </select>
        </div>
      }>
      <div style={{ padding: "0 20px 12px", display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center", justifyContent: "space-between" }}>
        <Segments label="État de l'accès" valeur={etat} onChange={(x) => { setEtat(x); setPage(1); }}
          options={ETATS} />
        <label className="petit" style={{ display: "flex", gap: 8, alignItems: "center" }} title="Nécessite l'API WhatsApp Cloud configurée sur le serveur">
          <input type="checkbox" checked={whatsapp} onChange={(e) => setWhatsapp(e.target.checked)} />
          Envoyer aussi les identifiants par WhatsApp
        </label>
      </div>
      {(selection.size > 0 || (paroisse && etat !== "avec")) && (
        <div className="barre-selection">
          {selection.size > 0 ? (
            <>
              <span><b>{selection.size}</b> membre(s) sélectionné(s)</span>
              <button className="bouton petit" onClick={() => setSelection(new Set())}><X />Annuler</button>
              <button className="bouton principal petit" disabled={encours === "groupe"} onClick={() => groupe({ ids: [...selection] })}>
                {encours === "groupe" ? <Loader2 className="tourne" /> : <KeyRound />}Donner l'accès
              </button>
            </>
          ) : (
            <>
              <span>Église locale : <b>{nomParoisse}</b></span>
              <button className="bouton principal petit" onClick={() => setConfirmation({ type: "paroisse" })}><KeyRound />Ouvrir l'accès à tous ses membres actifs</button>
            </>
          )}
        </div>
      )}
      {ignores.length > 0 && (
        <div style={{ margin: "0 20px 12px" }}>
          <Bandeau type="attention">
            <b>{ignores.length} membre(s) mis de côté</b>, à traiter un par un :{" "}
            {ignores.slice(0, 6).map((i) => `${i.nom} (${i.raison === "accord_parental_requis" ? "mineur : accord parental" : "date de naissance manquante"})`).join(", ")}
            {ignores.length > 6 ? "…" : "."} <button className="bouton fantome petit" onClick={() => setIgnores([])}>Fermer</button>
          </Bandeau>
        </div>
      )}
      <Etat chargement={liste.chargement && !liste.donnees} erreur={liste.erreur}>
        {lignes.length === 0 ? <Vide icone={Users} titre="Aucun membre" texte="Aucune fiche ne correspond à ces critères." /> : (
          <div className="defilement"><table className="tableau">
            <thead><tr>
              <th style={{ width: 36 }}><input type="checkbox" aria-label="Tout sélectionner" checked={tousCoches} disabled={!eligibles.length}
                onChange={() => setSelection(tousCoches ? new Set() : new Set(eligibles.map((m) => m.id)))} /></th>
              <th>Membre</th><th>Église locale</th><th>Accès</th><th className="masquer-mobile">Dernière connexion</th><th />
            </tr></thead>
            <tbody>{lignes.map((m) => (
              <tr key={m.id}>
                <td>{!m.acces && m.actif && <input type="checkbox" aria-label={`Sélectionner ${m.prenom} ${m.nom}`} checked={selection.has(m.id)} onChange={() => basculer(m.id)} />}</td>
                <td><div className="principal-cell">{m.prenom} {m.nom}</div>
                  <div className="secondaire">{m.numero}{m.telephone ? ` · ${m.telephone}` : ""}{m.acces ? ` · identifiant ${m.acces.identifiant}` : ""}</div></td>
                <td>{m.paroisse_nom}<div className="secondaire">{m.district_nom}</div></td>
                <td><BadgeAcces m={m} />{m.mineur && <div style={{ marginTop: 4 }}><span className="badge info" title={m.accord_parental ? `Accord de ${m.accord_parental.nom} (${m.accord_parental.lien})` : "Accord d'un parent ou tuteur nécessaire"}>
                  {m.age} ans{m.accord_parental ? " · accord parental" : " · mineur"}</span></div>}</td>
                <td className="masquer-mobile petit muet">{m.acces?.derniere_connexion ? dateHeure(m.acces.derniere_connexion) : m.acces ? "Jamais" : "—"}</td>
                <td className="num" style={{ whiteSpace: "nowrap" }}>
                  {!m.acces && m.actif && (
                    <button className="bouton petit principal" disabled={!!encours} onClick={() => agir(m, "accorder")}>
                      {encours === `${m.id}-accorder` ? <Loader2 className="tourne" /> : <KeyRound />}Donner l'accès
                    </button>
                  )}
                  {m.acces?.actif && <>
                    <button className="icone-bouton" title="Nouveau mot de passe provisoire" disabled={!!encours} onClick={() => agir(m, "reinitialiser")}><RotateCcw size={16} /></button>
                    <button className="icone-bouton" title="Suspendre l'accès" disabled={!!encours} onClick={() => setConfirmation({ type: "suspendre", m })}><ShieldBan size={16} /></button>
                  </>}
                  {m.acces && !m.acces.actif && <>
                    {m.actif && <button className="icone-bouton" title="Rétablir l'accès" disabled={!!encours} onClick={() => agir(m, "reactiver")}><ShieldCheck size={16} /></button>}
                    <button className="icone-bouton" title="Retirer définitivement l'accès" disabled={!!encours} onClick={() => setConfirmation({ type: "retirer", m })}><Trash2 size={16} /></button>
                  </>}
                </td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
      </Etat>
      <div className="carte-pied"><Pagination page={page} total={liste.donnees?.count || 0} parPage={50} onChange={setPage} unite="membres" /></div>

      {confirmation && (
        <Modale onFermer={() => setConfirmation(null)}
          titre={{ suspendre: "Suspendre l'accès ?", retirer: "Retirer l'accès ?", paroisse: "Ouvrir l'accès à toute l'église locale ?" }[confirmation.type]}
          pied={<><button className="bouton" onClick={() => setConfirmation(null)}>Annuler</button>
            <button className={`bouton ${confirmation.type === "paroisse" ? "principal" : "danger"}`} disabled={!!encours}
              onClick={() => confirmation.type === "paroisse" ? groupe({ paroisse }) : agir(confirmation.m, confirmation.type)}>
              {encours && <Loader2 className="tourne" />}Confirmer
            </button></>}>
          {confirmation.type === "suspendre" && <p>{confirmation.m.prenom} {confirmation.m.nom} ne pourra plus se connecter. Vous pourrez rétablir l'accès à tout moment.</p>}
          {confirmation.type === "retirer" && <p>Le compte de {confirmation.m.prenom} {confirmation.m.nom} sera supprimé. Sa fiche du registre et l'historique restent conservés.</p>}
          {confirmation.type === "paroisse" && <p>Un identifiant et un mot de passe provisoire seront créés pour chaque membre actif de <b>{nomParoisse}</b> qui n'a pas encore d'accès. Vous pourrez ensuite imprimer les fiches d'accès à remettre par le pasteur.</p>}
        </Modale>
      )}
      {resultats && <IdentifiantsModale resultats={resultats} org={org} onFermer={() => setResultats(null)} />}
      {accord && <AccordParental info={accord} encours={!!encours} onFermer={() => setAccord(null)}
        onConfirmer={(a) => agir(accord.m, "accorder", { accord_parental: a })} />}
    </Carte>
  );
}

// Accord d'un parent ou tuteur pour un membre plus jeune que l'âge fixé par l'organisation
function AccordParental({ info, encours, onFermer, onConfirmer }) {
  const [a, setA] = useState({ nom: "", lien: "Père", confirme: false });
  return (
    <Modale titre="Accord d'un parent ou tuteur" onFermer={onFermer}
      description={`${info.m.prenom} ${info.m.nom} a ${info.age} ans. Dans votre Église, l'accès sans accord parental commence à ${info.minimum} ans.`}
      pied={<><button className="bouton" onClick={onFermer}>Annuler</button>
        <button className="bouton principal" disabled={encours || a.nom.trim().length < 4 || !a.confirme} onClick={() => onConfirmer(a)}>
          {encours ? <Loader2 className="tourne" /> : <KeyRound />}Donner l'accès</button></>}>
      <div className="formulaire">
        <Champ libelle="Nom du parent ou tuteur"><input value={a.nom} onChange={(e) => setA({ ...a, nom: e.target.value })} autoFocus /></Champ>
        <Champ libelle="Lien"><select value={a.lien} onChange={(e) => setA({ ...a, lien: e.target.value })}>
          {["Père", "Mère", "Tuteur", "Tutrice", "Grand-parent", "Autre responsable légal"].map((l) => <option key={l}>{l}</option>)}
        </select></Champ>
        <label className="large" style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
          <input type="checkbox" checked={a.confirme} onChange={(e) => setA({ ...a, confirme: e.target.checked })} style={{ marginTop: 3 }} />
          <span>Je confirme avoir recueilli l'accord de cette personne. L'accord est enregistré sur la fiche et inscrit au journal d'audit.</span>
        </label>
      </div>
    </Modale>
  );
}

function Demandes({ org, onChange }) {
  const notifier = useToast();
  const [statut, setStatut] = useState("EN_ATTENTE");
  const [v, setV] = useState(0);
  const liste = useApi(`demandes-acces/?statut=${statut}&v=${v}`, [statut, v]);
  const [resultats, setResultats] = useState(null);
  const [rattacher, setRattacher] = useState(null);
  const [refus, setRefus] = useState(null);
  const lignes = liste.donnees?.results || [];

  const [accord, setAccord] = useState(null);
  async function accorder(d, membre, accordParental) {
    try {
      const corps = { ...(membre ? { membre } : {}), ...(accordParental ? { accord_parental: accordParental } : {}) };
      const r = await api(`demandes-acces/${d.id}/accorder/`, { methode: "POST", corps });
      setResultats(r);
      setRattacher(null);
      setAccord(null);
      setV((x) => x + 1);
      onChange();
    } catch (e) {
      if (e.details?.code === "accord_parental_requis") {
        const nom = (d.membre_detail?.nom || d.nom_saisi).split(" ");
        setRattacher(null);
        setAccord({ d, membre, m: { prenom: nom[0], nom: nom.slice(1).join(" ") }, age: e.details.age, minimum: e.details.age_minimum });
      } else notifier(e.message, "erreur");
    }
  }
  async function refuser() {
    try {
      await api(`demandes-acces/${refus.d.id}/refuser/`, { methode: "POST", corps: { motif: refus.motif } });
      notifier("Demande refusée.");
      setRefus(null);
      setV((x) => x + 1);
      onChange();
    } catch (e) {
      notifier(e.message, "erreur");
    }
  }

  return (
    <Carte brut titre="Demandes d'accès" description="Envoyées par les fidèles depuis la page de connexion. « Vérifiée » : le numéro de membre et le téléphone correspondent à la fiche du registre.">
      <div style={{ padding: "0 20px 12px" }}>
        <Segments label="Statut" valeur={statut} onChange={setStatut}
          options={[{ id: "EN_ATTENTE", libelle: "À traiter" }, { id: "ACCORDEE", libelle: "Accordées" }, { id: "REFUSEE", libelle: "Refusées" }]} />
      </div>
      <Etat chargement={liste.chargement && !liste.donnees} erreur={liste.erreur}>
        {lignes.length === 0 ? <Vide icone={Inbox} titre="Aucune demande" texte={statut === "EN_ATTENTE" ? "Toutes les demandes ont été traitées." : "Rien à afficher."} /> : (
          <div className="liste-demandes">
            {lignes.map((d) => (
              <article key={d.id} className="demande-acces">
                <div className="tete">
                  <div>
                    <b>{d.nom_saisi}</b>
                    <div className="secondaire">{d.telephone}{d.numero_saisi ? ` · N° saisi ${d.numero_saisi}` : " · sans numéro de membre"} · {dateHeure(d.cree_le)}</div>
                  </div>
                  {d.verifiee ? <span className="badge bon"><BadgeCheck size={13} />Vérifiée</span> : <span className="badge attention">À vérifier</span>}
                </div>
                {d.message && <p className="petit" style={{ margin: "8px 0 0" }}>« {d.message} »</p>}
                <div className="fiche-liee">
                  {d.membre_detail ? (
                    <><Link2 size={15} />Fiche : <b>{d.membre_detail.nom}</b> · {d.membre_detail.numero} · {d.membre_detail.paroisse_nom} · {d.membre_detail.statut_libelle}
                      {d.membre_detail.mineur && <span className="badge info">{d.membre_detail.age} ans{d.membre_detail.accord_parental ? " · accord parental" : " · accord parental requis"}</span>}
                      {d.membre_detail.telephone && !d.verifiee && <span className="muet"> (téléphone de la fiche : {d.membre_detail.telephone})</span>}</>
                  ) : <span className="muet">Aucune fiche reconnue : recherchez le membre dans le registre avant d'accorder.</span>}
                </div>
                {d.statut === "EN_ATTENTE" ? (
                  <div className="actions">
                    <button className="bouton petit" onClick={() => setRefus({ d, motif: "" })}><X />Refuser</button>
                    <button className="bouton petit" onClick={() => setRattacher(d)}><Search />{d.membre_detail ? "Changer de fiche" : "Rechercher la fiche"}</button>
                    {d.membre_detail && <button className="bouton petit principal" onClick={() => accorder(d)}><KeyRound />Accorder l'accès</button>}
                  </div>
                ) : (
                  <p className="petit muet" style={{ margin: "8px 0 0" }}>{d.statut_libelle} par {d.traitee_par_nom} le {dateHeure(d.traitee_le)}{d.motif_refus ? ` : ${d.motif_refus}` : ""}</p>
                )}
              </article>
            ))}
          </div>
        )}
      </Etat>
      {rattacher && <RechercheFiche demande={rattacher} onFermer={() => setRattacher(null)} onChoisir={(id) => accorder(rattacher, id)} />}
      {refus && (
        <Modale titre="Refuser la demande" onFermer={() => setRefus(null)}
          pied={<><button className="bouton" onClick={() => setRefus(null)}>Annuler</button><button className="bouton danger" onClick={refuser}>Refuser</button></>}>
          <Champ libelle="Motif (envoyé au demandeur par WhatsApp si l'API est branchée)">
            <input value={refus.motif} onChange={(e) => setRefus({ ...refus, motif: e.target.value })} placeholder="ex. Pas encore inscrit au registre de la paroisse" maxLength={255} />
          </Champ>
        </Modale>
      )}
      {resultats && <IdentifiantsModale resultats={resultats} org={org} onFermer={() => setResultats(null)} />}
      {accord && <AccordParental info={accord} onFermer={() => setAccord(null)} onConfirmer={(a) => accorder(accord.d, accord.membre, a)} />}
    </Carte>
  );
}

function RechercheFiche({ demande, onFermer, onChoisir }) {
  const [q, setQ] = useState(demande.nom_saisi.split(" ").slice(-1)[0] || "");
  const r = useApi(q.length >= 2 ? `acces-membres/?search=${encodeURIComponent(q)}` : null, [q]);
  return (
    <Modale titre="Rattacher à une fiche du registre" largeur={640} onFermer={onFermer}
      description={`Demande de ${demande.nom_saisi}, téléphone ${demande.telephone}. Vérifiez qu'il s'agit bien de la même personne.`}>
      <input className="saisie-ui" style={{ width: "100%", marginBottom: 12 }} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Nom, numéro ou téléphone" autoFocus />
      <Etat chargement={r.chargement && !r.donnees} erreur={r.erreur}>
        <div className="defilement" style={{ maxHeight: 340 }}>
          <table className="tableau"><tbody>
            {(r.donnees?.results || []).map((m) => (
              <tr key={m.id}>
                <td><div className="principal-cell">{m.prenom} {m.nom}</div><div className="secondaire">{m.numero} · {m.paroisse_nom}{m.telephone ? ` · ${m.telephone}` : ""}</div></td>
                <td><BadgeAcces m={m} />{m.mineur && <div style={{ marginTop: 4 }}><span className="badge info" title={m.accord_parental ? `Accord de ${m.accord_parental.nom} (${m.accord_parental.lien})` : "Accord d'un parent ou tuteur nécessaire"}>
                  {m.age} ans{m.accord_parental ? " · accord parental" : " · mineur"}</span></div>}</td>
                <td className="num">{m.actif && !m.acces?.actif && <button className="bouton petit principal" onClick={() => onChoisir(m.id)}><CheckCircle2 />Choisir et accorder</button>}</td>
              </tr>
            ))}
          </tbody></table>
          {q.length >= 2 && r.donnees?.results?.length === 0 && <p className="petit muet" style={{ padding: 12 }}>Aucune fiche. Le membre doit d'abord être enregistré au registre par sa paroisse.</p>}
        </div>
      </Etat>
    </Modale>
  );
}

function Reglages({ ouvertes, onChange }) {
  const notifier = useToast();
  const [encours, setEncours] = useState(false);
  const org = useApi("organisation/");
  const [age, setAge] = useState("");
  useEffect(() => { if (org.donnees) setAge(org.donnees.age_minimum_acces); }, [org.donnees]);
  async function enregistrerAge() {
    try {
      await api("organisation/", { methode: "PATCH", corps: { age_minimum_acces: Number(age) } });
      notifier(`Âge minimum enregistré : ${age} ans.`);
    } catch (e) {
      notifier(e.message, "erreur");
    }
  }
  const lien = `${window.location.origin}/demande-acces`;
  async function basculer() {
    setEncours(true);
    try {
      await api("organisation/", { methode: "PATCH", corps: { demandes_acces_ouvertes: !ouvertes } });
      notifier(!ouvertes ? "Les membres peuvent demander un accès." : "Formulaire de demande fermé.");
      onChange();
    } catch (e) {
      notifier(e.message, "erreur");
    }
    setEncours(false);
  }
  return (
    <div className="grille g2">
      <Carte titre="Demandes en libre-service" description="Un fidèle saisit son numéro de membre et son téléphone ; un administrateur décide.">
        <div className="pile" style={{ gap: 12 }}>
          <label style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <input type="checkbox" checked={!!ouvertes} onChange={basculer} disabled={encours || ouvertes === undefined} />
            Autoriser les membres à demander un accès depuis la page de connexion
          </label>
          <p className="petit muet">Adresse à partager (annonces, groupe WhatsApp de la paroisse) :</p>
          <code className="code" style={{ display: "block", padding: 10, background: "var(--surface-2)", borderRadius: 8, wordBreak: "break-all" }}>{lien}</code>
          <Bandeau type="info">La réponse au demandeur est toujours la même : le formulaire ne révèle jamais si une personne est inscrite au registre.</Bandeau>
        </div>
      </Carte>
      <Carte titre="Membres mineurs" description="Protection des enfants et des adolescents.">
        <div className="pile" style={{ gap: 12 }}>
          <p className="petit">Sous cet âge, l'accès n'est ouvert qu'avec l'accord d'un parent ou tuteur, enregistré sur la fiche et au journal. La date de naissance est obligatoire pour ouvrir un accès.</p>
          <div style={{ display: "flex", gap: 10, alignItems: "flex-end", flexWrap: "wrap" }}>
            <Champ libelle="Âge minimum sans accord parental"><input type="number" min={10} max={21} value={age} onChange={(e) => setAge(e.target.value)} style={{ width: 120 }} /></Champ>
            <button className="bouton" onClick={enregistrerAge} disabled={!age || Number(age) === org.donnees?.age_minimum_acces}>Enregistrer</button>
          </div>
          <p className="petit muet">Un accès groupé met de côté les mineurs sans accord et les fiches sans date de naissance ; ils se traitent un par un.</p>
        </div>
      </Carte>
      <Carte titre="Ce que voit un membre" description="Garanti par le serveur, pas seulement par l'interface.">
        <ul className="liste-droits">
          <li className="oui"><Eye size={15} />Sa fiche du registre et sa carte de membre (à imprimer)</li>
          <li className="oui"><Eye size={15} />Ses coordonnées, qu'il corrige lui-même (tracé au journal)</li>
          <li className="oui"><Eye size={15} />Son église locale : pasteur, surintendant, communauté</li>
          <li className="oui"><Eye size={15} />Les biens de son église (nom, état, photo) et les projets publics du district</li>
          <li className="oui"><LogIn size={15} />Signaler un problème sur un bien, puis suivre la réponse</li>
          <li className="oui"><Eye size={15} />Ses propres dîmes et offrandes, ses reçus et son attestation annuelle</li>
          <li className="non"><EyeOff size={15} />Jamais : finances, valeurs, titres de propriété, autres membres, journal, tableaux de bord</li>
        </ul>
      </Carte>
    </div>
  );
}
