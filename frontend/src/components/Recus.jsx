// Reçu d'une contribution (format A6) et attestation annuelle (A4, avec QR code de vérification).
import { date as dateFr, nombre } from "../format";

const esc = (t) => String(t ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const montant = (v, devise) => `${nombre(Number(v))} ${esc(devise || "")}`;

function ouvrir(titre, styles, corps) {
  const w = window.open("", "_blank", "width=860,height=900");
  if (!w) return;
  w.document.write(`<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>${esc(titre)}</title><style>
* { box-sizing: border-box; -webkit-print-color-adjust: exact; print-color-adjust: exact }
body { margin: 0; font-family: "Segoe UI", Arial, sans-serif; color: #142019; background: #eef2ef }
.page { background: #fff; margin: 16px auto; box-shadow: 0 6px 24px rgba(0,0,0,.12) }
@media print { body { background: none } .page { margin: 0; box-shadow: none } }
${styles}</style></head><body>${corps}<script>window.onload = () => setTimeout(() => window.print(), 350)</script></body></html>`);
  w.document.close();
}

export function imprimerRecu(c, org) {
  const base = window.location.origin;
  ouvrir(`Reçu ${c.numero_recu}`, `
@page { size: A6; margin: 0 }
.page { width: 105mm; min-height: 148mm; padding: 9mm 8mm; display: flex; flex-direction: column; gap: 3mm }
.h { display: flex; gap: 3mm; align-items: center; border-bottom: 2px solid #1e6b47; padding-bottom: 3mm }
.h img { width: 10mm; height: 10mm } .h b { display: block; font-size: 10pt } .h span { font-size: 7.5pt; color: #6f7e76 }
h1 { font-size: 13pt; margin: 2mm 0 0; letter-spacing: .04em } .n { font-family: Consolas, monospace; font-size: 10pt; color: #1e6b47; font-weight: 700 }
table { width: 100%; border-collapse: collapse; font-size: 9pt } td { padding: 1.4mm 0; border-bottom: 1px solid #e2e8e3; vertical-align: top }
td:first-child { color: #6f7e76; width: 34mm }
.m { font-size: 17pt; font-weight: 700; text-align: center; padding: 3mm; background: #e2f0e8; border-radius: 2mm; color: #165536 }
.annule { color: #b42318; border: 2px solid #b42318; text-align: center; font-weight: 700; padding: 2mm; transform: rotate(-3deg) }
.b { margin-top: auto; font-size: 7pt; color: #6f7e76; text-align: center }`,
  `<div class="page">
  <div class="h"><img src="${base}/logo.svg" alt=""><div><b>${esc(org?.nom)}</b><span>${esc(c.paroisse_nom)}${c.district_nom ? " · district de " + esc(c.district_nom) : ""}</span></div></div>
  <h1>REÇU</h1><div class="n">N° ${esc(c.numero_recu)}</div>
  ${c.annulee ? `<div class="annule">ANNULÉ — ${esc(c.motif_annulation)}</div>` : ""}
  <div class="m">${montant(c.montant, org?.devise)}</div>
  <table>
    <tr><td>Reçu de</td><td><b>${esc(c.membre_nom || "Collecte du culte (anonyme)")}</b>${c.membre_numero ? `<br>N° de membre ${esc(c.membre_numero)}` : ""}</td></tr>
    <tr><td>Nature</td><td>${esc(c.type_libelle)}</td></tr>
    <tr><td>Date</td><td>${esc(dateFr(c.date))}</td></tr>
    <tr><td>Mode de paiement</td><td>${esc(c.mode_libelle)}${c.reference ? ` · réf. ${esc(c.reference)}` : ""}</td></tr>
    <tr><td>Enregistré par</td><td>${esc(c.enregistre_par_nom || "")}</td></tr>
  </table>
  <div class="b">« Que chacun donne comme il l'a résolu en son cœur. » 2 Corinthiens 9:7<br>Reçu émis par UMURAGE. Conservez-le.</div>
</div>`);
}

export function imprimerAttestation(a) {
  const base = window.location.origin;
  const lignes = a.lignes.map((l) => `<tr><td>${esc(dateFr(l.date))}</td><td class="mono">${esc(l.recu)}</td><td>${esc(l.type)}</td><td>${esc(l.mode)}</td><td class="num">${montant(l.montant, "")}</td></tr>`).join("");
  const types = a.par_type.map((t) => `<tr><td>${esc(t.libelle)}</td><td class="num">${montant(t.total, a.devise)}</td></tr>`).join("");
  ouvrir(`Attestation ${a.annee} — ${a.membre.nom}`, `
@page { size: A4; margin: 0 }
.page { width: 210mm; min-height: 297mm; padding: 16mm 17mm; position: relative }
.h { display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 3px solid #1e6b47; padding-bottom: 5mm }
.org { display: flex; gap: 4mm; align-items: center } .org img { width: 15mm; height: 15mm }
.org b { font-size: 13pt; display: block } .org span { font-size: 9pt; color: #47574e }
.qr { text-align: center; font-size: 7pt; color: #47574e } .qr img { width: 28mm; height: 28mm; display: block; margin: 0 auto 1mm }
h1 { font-size: 20pt; margin: 9mm 0 1mm; letter-spacing: .02em } .sous { color: #47574e; margin: 0 0 7mm }
.provisoire { display: inline-block; background: #fbf0d9; color: #9a6a0c; font-weight: 700; padding: 1mm 3mm; border-radius: 1.5mm; font-size: 9pt; margin-left: 3mm; vertical-align: middle }
p { line-height: 1.55; font-size: 10.5pt }
.total { display: flex; justify-content: space-between; align-items: baseline; background: #e2f0e8; border-radius: 3mm; padding: 5mm 7mm; margin: 6mm 0 }
.total span { font-size: 10pt; color: #165536 } .total b { font-size: 22pt; color: #165536 }
table { width: 100%; border-collapse: collapse; font-size: 9pt } th { text-align: left; color: #6f7e76; font-weight: 600; border-bottom: 1.5px solid #c9d3cc; padding: 2mm 1.5mm }
td { padding: 1.5mm; border-bottom: 1px solid #e2e8e3 } .num { text-align: right; font-variant-numeric: tabular-nums } .mono { font-family: Consolas, monospace; font-size: 8pt }
.cols { display: grid; grid-template-columns: 1fr 1fr; gap: 10mm; margin-top: 4mm }
.sign { margin-top: 12mm; display: flex; justify-content: space-between; font-size: 9.5pt } .sign div { width: 70mm; border-top: 1px solid #142019; padding-top: 2mm }
.pied { position: absolute; bottom: 10mm; left: 17mm; right: 17mm; font-size: 7.5pt; color: #6f7e76; border-top: 1px solid #e2e8e3; padding-top: 2mm }
h2 { font-size: 11pt; margin: 8mm 0 2mm }`,
  `<div class="page">
  <div class="h">
    <div class="org"><img src="${base}/logo.svg" alt=""><div><b>${esc(a.organisation.nom)}</b><span>Église locale de ${esc(a.membre.paroisse)} · district de ${esc(a.membre.district)}<br>${esc(a.organisation.pays)}</span></div></div>
    <div class="qr"><img src="${a.qr}" alt="QR code de vérification">Vérifier : ${esc(a.code)}</div>
  </div>
  <h1>Attestation de contributions ${esc(a.annee)}${a.definitive ? "" : '<span class="provisoire">PROVISOIRE</span>'}</h1>
  <p class="sous">Émise le ${esc(dateFr(a.emise_le))}</p>
  <p>Nous attestons que <b>${esc(a.membre.nom)}</b>, membre n° <b>${esc(a.membre.numero)}</b> de l'église locale de ${esc(a.membre.paroisse)},
  a versé à ${esc(a.organisation.nom)}, du 1<sup>er</sup> janvier au 31 décembre ${esc(a.annee)}, les contributions suivantes
  (${esc(a.nombre)} versement${a.nombre > 1 ? "s" : ""}).${a.definitive ? "" : " L'année n'étant pas terminée, cette attestation est provisoire."}</p>
  <div class="total"><span>Total des contributions ${esc(a.annee)}</span><b>${montant(a.total, a.devise)}</b></div>
  <div class="cols">
    <div><h2>Par nature</h2><table>${types}</table></div>
    <div><h2>Authenticité</h2><p style="font-size:9pt">Scannez le QR code ou ouvrez <b>${esc(a.url_verification.replace(/^https?:\/\//, ""))}</b> :
    la plateforme confirme l'organisation, l'année et le total, sans révéler le détail des dons.</p></div>
  </div>
  <h2>Détail des versements</h2>
  <table><thead><tr><th>Date</th><th>Reçu</th><th>Nature</th><th>Mode</th><th class="num">Montant (${esc(a.devise)})</th></tr></thead><tbody>${lignes}</tbody></table>
  <div class="sign"><div>Le trésorier</div><div>Le pasteur${a.pasteur ? ` : ${esc(a.pasteur)}` : ""}</div></div>
  <div class="pied">Document établi à partir du registre des contributions de la plateforme UMURAGE. Code de vérification ${esc(a.code)}.</div>
</div>`);
}
