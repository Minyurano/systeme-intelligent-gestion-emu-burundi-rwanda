import React, { lazy, Suspense } from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import "@fontsource-variable/bricolage-grotesque";
import "@fontsource-variable/public-sans";
import "leaflet/dist/leaflet.css";
import "./styles.css";
import { AuthProvider, useAuth } from "./auth";
import { LangueProvider } from "./i18n";
import { ThemeProvider } from "./theme";
import Layout from "./components/Layout";
import { Squelette, ToastProvider } from "./components/ui";
import Connexion from "./pages/Connexion";
import { ChangementObligatoire } from "./components/MotDePasse";

// Chaque page est chargée à la demande : l'application démarre plus vite.
const TableauDeBord = lazy(() => import("./pages/TableauDeBord"));
const Inventaire = lazy(() => import("./pages/Inventaire"));
const FicheBien = lazy(() => import("./pages/FicheBien"));
const Carte = lazy(() => import("./pages/Carte"));
const Projets = lazy(() => import("./pages/Projets"));
const Finances = lazy(() => import("./pages/Finances"));
const Capteurs = lazy(() => import("./pages/Capteurs"));
const Assistant = lazy(() => import("./pages/Assistant"));
const Journal = lazy(() => import("./pages/Journal"));
const Rapport = lazy(() => import("./pages/Rapport"));
const Portail = lazy(() => import("./pages/Portail"));
const Declarations = lazy(() => import("./pages/Declarations"));
const Qualite = lazy(() => import("./pages/Qualite"));
const Parametres = lazy(() => import("./pages/Parametres"));
const Inscription = lazy(() => import("./pages/Inscription"));
const Approbations = lazy(() => import("./pages/Approbations"));
const Echeancier = lazy(() => import("./pages/Echeancier"));
const Locations = lazy(() => import("./pages/Locations"));
const Maintenance = lazy(() => import("./pages/Maintenance"));
const Comptabilite = lazy(() => import("./pages/Comptabilite"));
const InventaireTerrain = lazy(() => import("./pages/InventaireTerrain"));
const Securite = lazy(() => import("./pages/Securite"));
const Comparaison = lazy(() => import("./pages/Comparaison"));
const Registre = lazy(() => import("./pages/Registre"));
const Statistiques = lazy(() => import("./pages/Statistiques"));
const AccesMembres = lazy(() => import("./pages/AccesMembres"));
const EspaceMembre = lazy(() => import("./pages/EspaceMembre"));
const DemandeAcces = lazy(() => import("./pages/DemandeAcces"));
const MotDePasseOublie = lazy(() => import("./pages/MotDePasseOublie"));
const VerifierAttestation = lazy(() => import("./pages/VerifierAttestation"));
const Contributions = lazy(() => import("./pages/Contributions"));

// espace : "gestion" (responsables) ou "membre" (fidèles). Chacun est renvoyé vers le sien.
function Protege({ children, espace = "gestion" }) {
  const { moi, pret } = useAuth();
  if (!pret) return <Squelette lignes={6} style={{ padding: 40 }} />;
  if (!moi) return <Navigate to="/connexion" replace />;
  if (moi.doit_changer_mdp) return <ChangementObligatoire />;
  if (espace === "gestion" && moi.est_membre) return <Navigate to="/membre" replace />;
  if (espace === "membre" && !moi.est_membre) return <Navigate to="/" replace />;
  return children;
}

const page = (Composant) => (
  <Suspense fallback={<Squelette lignes={8} hauteur={20} />}>
    <Composant />
  </Suspense>
);

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ThemeProvider>
      <LangueProvider>
      <ToastProvider>
        <AuthProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/connexion" element={<Connexion />} />
              <Route path="/public" element={page(Portail)} />
              <Route path="/public/:slug" element={page(Portail)} />
              <Route path="/inscription" element={page(Inscription)} />
              <Route path="/demande-acces" element={page(DemandeAcces)} />
              <Route path="/mot-de-passe-oublie" element={page(MotDePasseOublie)} />
              <Route path="/verifier/:code" element={page(VerifierAttestation)} />
              <Route path="/membre" element={<Protege espace="membre">{page(EspaceMembre)}</Protege>} />
              <Route element={<Protege><Layout /></Protege>}>
                <Route path="/" element={page(TableauDeBord)} />
                <Route path="/biens" element={page(Inventaire)} />
                <Route path="/biens/:id" element={page(FicheBien)} />
                <Route path="/carte" element={page(Carte)} />
                <Route path="/projets" element={page(Projets)} />
                <Route path="/finances" element={page(Finances)} />
                <Route path="/capteurs" element={page(Capteurs)} />
                <Route path="/assistant" element={page(Assistant)} />
                <Route path="/journal" element={page(Journal)} />
                <Route path="/rapport" element={page(Rapport)} />
                <Route path="/declarations" element={page(Declarations)} />
                <Route path="/qualite" element={page(Qualite)} />
                <Route path="/parametres" element={page(Parametres)} />
                <Route path="/approbations" element={page(Approbations)} />
                <Route path="/echeancier" element={page(Echeancier)} />
                <Route path="/locations" element={page(Locations)} />
                <Route path="/maintenance" element={page(Maintenance)} />
                <Route path="/comptabilite" element={page(Comptabilite)} />
                <Route path="/inventaire-terrain" element={page(InventaireTerrain)} />
                <Route path="/securite" element={page(Securite)} />
                <Route path="/comparaison" element={page(Comparaison)} />
                <Route path="/registre" element={page(Registre)} />
                <Route path="/statistiques" element={page(Statistiques)} />
                <Route path="/acces-membres" element={page(AccesMembres)} />
                <Route path="/contributions" element={page(Contributions)} />
              </Route>
              <Route path="*" element={<Navigate to="/" />} />
            </Routes>
          </BrowserRouter>
        </AuthProvider>
      </ToastProvider>
      </LangueProvider>
    </ThemeProvider>
  </React.StrictMode>
);

// Application installable et utilisable hors ligne (en production uniquement)
if ("serviceWorker" in navigator && import.meta.env.PROD) {
  window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {}));
}
