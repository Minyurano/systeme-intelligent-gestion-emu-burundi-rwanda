import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { CircleAlert, Loader2, ShieldCheck, ShieldX } from "lucide-react";
import { date as dateFr, nombre } from "../format";

// Page publique ouverte par le QR code d'une attestation annuelle.
export default function VerifierAttestation() {
  const { code } = useParams();
  const [r, setR] = useState(null);
  useEffect(() => {
    fetch(`/api/attestations/verifier/${encodeURIComponent(code)}/`).then((x) => x.json()).then(setR)
      .catch(() => setR({ valide: false, message: "Vérification impossible : pas de connexion au serveur." }));
  }, [code]);

  return (
    <div className="ecran-centre">
      <div className="carte-ui" style={{ width: "min(480px, 100%)", padding: 28 }}>
        <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 18 }}>
          <img src="/logo.svg" alt="" width="34" height="34" />
          <div><h1 style={{ fontSize: "1.25rem" }}>Vérification d'une attestation</h1><p className="petit muet code">{code}</p></div>
        </div>
        {!r ? <p className="muet"><Loader2 className="tourne" size={16} /> Vérification…</p> : r.valide ? (
          <div className="pile" style={{ gap: 14 }}>
            <div className={`verif ${r.a_jour ? "ok" : "attention"}`}>
              {r.a_jour ? <ShieldCheck /> : <CircleAlert />}
              <div><b>{r.a_jour ? "Attestation authentique" : "Attestation authentique, mais dépassée"}</b>
                <span>{r.a_jour ? "Délivrée par la plateforme UMURAGE de cette Église." : r.message.replace("Attestation authentique. ", "")}</span></div>
            </div>
            <dl className="proprietes" style={{ border: "1px solid var(--trait)", borderRadius: 10, margin: 0 }}>
              {[["Organisation", r.organisation], ["Église locale", r.paroisse], ["Membre", `${r.membre} (n° ${r.numero_partiel})`],
                ["Année", `${r.annee}${r.definitive ? "" : " (provisoire)"}`], ["Total attesté", `${nombre(Number(r.total))} ${r.devise}`],
                ["Versements", r.nombre], ["Émise le", dateFr(r.emise_le)]].map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}
            </dl>
            <p className="petit muet">Comparez ces informations avec le document papier. Le détail des dons n'est jamais publié.</p>
          </div>
        ) : (
          <div className="verif critique"><ShieldX /><div><b>Document non reconnu</b><span>{r.message}</span></div></div>
        )}
      </div>
    </div>
  );
}
