// Carte de membre : aperçu à l'écran et impression au format carte bancaire (registre et espace membre).
import { date as dateFr } from "../format";

export const initiales = (m) => `${(m.prenom || "")[0] || ""}${(m.nom || "")[0] || ""}`.toUpperCase();

export function CarteMembre({ m, org, photo }) {
  const prenom = m.prenom ? m.prenom.trim().charAt(0).toUpperCase() + m.prenom.trim().slice(1) : "";
  const nom = [prenom, (m.nom || "").trim().toUpperCase()].filter(Boolean).join(" ");
  return (
    <div className="carte-membre">
      <div className="entete"><img src="/logo.svg" alt="" />{org.sigle || org.nom || "Église"} · Carte de membre</div>
      <div className="photo">{photo ? <img src={photo} alt="" /> : (initiales(m) || "?")}</div>
      <div className="infos">
        <div className={`nom${nom ? "" : " vide"}`}>{nom || "Prénom NOM"}</div>
        <div className="lib">Église locale</div>
        <div className={m.paroisse_nom ? "" : "vide"}>{m.paroisse_nom || "—"}{m.district_nom ? `, ${m.district_nom}` : ""}</div>
        <div className="lib">Statut</div>
        <div>{m.statut_libelle || "—"}{m.date_bapteme ? ` · baptisé(e) le ${dateFr(m.date_bapteme)}` : ""}</div>
      </div>
      <div className="num">{m.numero || "N° ———"}</div>
    </div>
  );
}

// Carte de membre au format carte bancaire (85,6 × 54 mm), prête à imprimer
export function imprimerCarte(m, org) {
  const esc = (t) => String(t ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const w = window.open("", "_blank", "width=520,height=420");
  if (!w) return;
  const base = window.location.origin;
  w.document.write(`<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>Carte ${esc(m.numero)}</title>
<style>
@page { size: 85.6mm 54mm; margin: 0 }
* { box-sizing: border-box; -webkit-print-color-adjust: exact; print-color-adjust: exact }
body { margin: 0; font-family: "Segoe UI", Arial, sans-serif; display: grid; place-items: center; min-height: 100vh; background: #eee }
.c { width: 85.6mm; height: 54mm; border-radius: 3mm; padding: 3.5mm 4mm; color: #fff; position: relative; overflow: hidden;
  background: radial-gradient(120% 120% at 100% 0%, #2f8f5f 0%, #17573a 45%, #0f3d29 100%); display: grid; grid-template-columns: 19mm 1fr; gap: 1.5mm 3.5mm; align-content: start }
.h { grid-column: 1 / -1; display: flex; gap: 2mm; align-items: center; font-size: 6.5pt; letter-spacing: .08em; text-transform: uppercase }
.h img { width: 5mm; height: 5mm }
.p { width: 19mm; height: 23mm; border-radius: 2mm; background: rgba(255,255,255,.15); overflow: hidden; display: grid; place-items: center; font-size: 15pt; font-weight: 700 }
.p img { width: 100%; height: 100%; object-fit: cover }
.n { font-size: 10.5pt; font-weight: 700; line-height: 1.15 }
.l { font-size: 5.5pt; opacity: .7; text-transform: uppercase; letter-spacing: .06em; margin-top: 1.2mm }
.v { font-size: 7pt }
.num { position: absolute; right: 4mm; bottom: 3mm; font-size: 8pt; font-weight: 700; letter-spacing: .08em; background: rgba(0,0,0,.25); padding: .8mm 2mm; border-radius: 1.5mm }
.s { position: absolute; left: 4mm; bottom: 3.2mm; font-size: 5.5pt; opacity: .75 }
@media print { body { background: none; min-height: 0 } }
</style></head><body><div class="c">
<div class="h"><img src="${base}/logo.svg" alt="">${esc(org.nom || "Église")}</div>
<div class="p">${m.photo ? `<img src="${esc(m.photo)}" alt="">` : esc(initiales(m))}</div>
<div><div class="n">${esc(m.prenom)} ${esc(m.nom)}</div>
<div class="l">Église locale</div><div class="v">${esc(m.paroisse_nom)}${m.district_nom ? ", " + esc(m.district_nom) : ""}</div>
<div class="l">Statut</div><div class="v">${esc(m.statut_libelle)}</div>
<div class="l">Membre depuis</div><div class="v">${esc(dateFr(m.date_adhesion))}</div></div>
<div class="s">Plateforme UMURAGE</div><div class="num">${esc(m.numero)}</div>
</div><script>window.onload = () => setTimeout(() => window.print(), 300)</script></body></html>`);
  w.document.close();
}
