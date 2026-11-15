import { useState } from "react";
import { Check, Copy, MessageCircle, Printer } from "lucide-react";
import { Bandeau, Modale } from "./ui";

const esc = (t) => String(t ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

export const messageAcces = (a, org) =>
  `Bonjour, votre accès à l'espace membre de ${org?.nom || "l'Église"} est ouvert.\n`
  + `Adresse : ${a.adresse || `${window.location.origin}/connexion`}\nIdentifiant : ${a.identifiant}\nMot de passe provisoire : ${a.mot_de_passe}\n`
  + "Vous choisirez votre propre mot de passe à la première connexion. Ne le communiquez à personne.";

// Fiches d'accès à découper (8 par page A4), à remettre en main propre par le pasteur
export function imprimerIdentifiants(liste, org) {
  const w = window.open("", "_blank", "width=900,height=700");
  if (!w) return;
  const base = window.location.origin;
  const fiches = liste.map((a) => `<div class="f">
  <div class="h"><img src="${base}/logo.svg" alt="">${esc(org?.nom || "Église")} · Espace membre</div>
  <div class="n">${esc(a.nom)}</div><div class="p">${esc(a.paroisse || "")} · N° ${esc(a.numero)}</div>
  <table><tr><td>Adresse</td><td>${esc((a.adresse || `${base}/connexion`).replace(/^https?:\/\//, ""))}</td></tr>
  <tr><td>Identifiant</td><td class="m">${esc(a.identifiant)}</td></tr>
  <tr><td>Mot de passe provisoire</td><td class="m">${esc(a.mot_de_passe)}</td></tr></table>
  <div class="b">À la première connexion, vous choisirez votre propre mot de passe. Ne communiquez cette fiche à personne.</div>
</div>`).join("");
  w.document.write(`<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>Fiches d'accès</title><style>
@page { size: A4; margin: 10mm }
* { box-sizing: border-box; -webkit-print-color-adjust: exact; print-color-adjust: exact }
body { margin: 0; font-family: "Segoe UI", Arial, sans-serif; color: #142019 }
.g { display: grid; grid-template-columns: 1fr 1fr; gap: 0 }
.f { border: 1px dashed #9aa79f; padding: 5mm 6mm; height: 68mm; page-break-inside: avoid; display: flex; flex-direction: column; gap: 1.6mm }
.h { display: flex; gap: 2mm; align-items: center; font-size: 8pt; text-transform: uppercase; letter-spacing: .06em; color: #1e6b47; font-weight: 700 }
.h img { width: 6mm; height: 6mm }
.n { font-size: 13pt; font-weight: 700; margin-top: 1mm }
.p { font-size: 8.5pt; color: #47574e }
table { border-collapse: collapse; font-size: 9pt; margin-top: 1mm }
td { padding: 1mm 0; vertical-align: top } td:first-child { color: #6f7e76; padding-right: 4mm; white-space: nowrap }
.m { font-family: Consolas, monospace; font-size: 11pt; font-weight: 700; letter-spacing: .03em }
.b { margin-top: auto; font-size: 7.5pt; color: #6f7e76 }
</style></head><body><div class="g">${fiches}</div><script>window.onload = () => setTimeout(() => window.print(), 300)</script></body></html>`);
  w.document.close();
}

export default function IdentifiantsModale({ resultats, org, onFermer }) {
  const [copie, setCopie] = useState(null);
  const liste = [].concat(resultats);
  async function copier(a, i) {
    try {
      await navigator.clipboard.writeText(messageAcces(a, org));
      setCopie(i);
      setTimeout(() => setCopie(null), 1800);
    } catch { /* presse-papiers indisponible : l'administrateur recopie à la main */ }
  }
  const whatsapp = (a) => `https://wa.me/${(a.telephone || "").replace(/\D/g, "")}?text=${encodeURIComponent(messageAcces(a, org))}`;
  return (
    <Modale titre={liste.length > 1 ? `${liste.length} accès ouverts` : "Accès ouvert"} largeur={liste.length > 1 ? 780 : 640} onFermer={onFermer}
      description="Les mots de passe provisoires ne sont affichés qu'une seule fois. Transmettez-les maintenant ou imprimez les fiches."
      pied={<><button className="bouton" onClick={() => imprimerIdentifiants(liste, org)}><Printer />Imprimer {liste.length > 1 ? "les fiches" : "la fiche"}</button>
        <button className="bouton principal" onClick={onFermer}>Terminé</button></>}>
      {liste.some((a) => a.whatsapp_envoye) && <Bandeau type="succes" style={{ marginBottom: 12 }}>Identifiants envoyés par WhatsApp aux membres qui ont un numéro.</Bandeau>}
      <div className="defilement" style={{ maxHeight: 420 }}>
        <table className="tableau">
          <thead><tr><th>Membre</th><th>Identifiant</th><th>Mot de passe provisoire</th><th /></tr></thead>
          <tbody>{liste.map((a, i) => (
            <tr key={a.identifiant}>
              <td><div className="principal-cell">{a.nom}</div><div className="secondaire">{a.paroisse}</div></td>
              <td className="code">{a.identifiant}</td>
              <td className="code" style={{ fontWeight: 650 }}>{a.mot_de_passe}</td>
              <td className="num" style={{ whiteSpace: "nowrap" }}>
                <button className="icone-bouton" title="Copier le message" onClick={() => copier(a, i)}>{copie === i ? <Check size={16} /> : <Copy size={16} />}</button>
                {a.telephone && <a className="icone-bouton" title="Envoyer par WhatsApp" href={whatsapp(a)} target="_blank" rel="noreferrer"><MessageCircle size={16} /></a>}
              </td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </Modale>
  );
}
