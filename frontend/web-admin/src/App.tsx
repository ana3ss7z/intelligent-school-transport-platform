import { lazy, Suspense } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { RequireAuth } from "./auth/RequireAuth";
import { useAuth } from "./auth/AuthContext";
import { AppLayout } from "./layout/AppLayout";
import { Login } from "./pages/Login";
import { Spinner } from "./components/ui";

// Code-splitting par route : Leaflet (Carte) et Recharts (Clustering) hors du bundle initial.
const Dashboard = lazy(() => import("./pages/Dashboard").then((m) => ({ default: m.Dashboard })));
const CarteLive = lazy(() => import("./pages/CarteLive").then((m) => ({ default: m.CarteLive })));
const Clustering = lazy(() => import("./pages/Clustering").then((m) => ({ default: m.Clustering })));
const Notifications = lazy(() => import("./pages/Notifications").then((m) => ({ default: m.Notifications })));
const Eleves = lazy(() => import("./pages/Eleves").then((m) => ({ default: m.Eleves })));
const BusPage = lazy(() => import("./pages/BusPage").then((m) => ({ default: m.BusPage })));
const Incidents = lazy(() => import("./pages/Incidents").then((m) => ({ default: m.Incidents })));
const Anomalies = lazy(() => import("./pages/Anomalies").then((m) => ({ default: m.Anomalies })));
const Settings = lazy(() => import("./pages/Settings").then((m) => ({ default: m.Settings })));
const Users = lazy(() => import("./pages/Users").then((m) => ({ default: m.Users })));
const EtaPrevisions = lazy(() => import("./pages/EtaPrevisions").then((m) => ({ default: m.EtaPrevisions })));
const ChauffeurHome = lazy(() => import("./pages/ChauffeurHome").then((m) => ({ default: m.ChauffeurHome })));
const ChauffeurIncidents = lazy(() => import("./pages/ChauffeurIncidents").then((m) => ({ default: m.ChauffeurIncidents })));
const ChauffeurCarte = lazy(() => import("./pages/ChauffeurCarte").then((m) => ({ default: m.ChauffeurCarte })));
const ChauffeurEta = lazy(() => import("./pages/ChauffeurEta").then((m) => ({ default: m.ChauffeurEta })));
const ChauffeurNotifs = lazy(() => import("./pages/ChauffeurNotifs").then((m) => ({ default: m.ChauffeurNotifs })));
const ChauffeurHistorique = lazy(() => import("./pages/ChauffeurHistorique").then((m) => ({ default: m.ChauffeurHistorique })));
const TrajetsEnCours = lazy(() => import("./pages/TrajetsEnCours").then((m) => ({ default: m.TrajetsEnCours })));
const Messagerie = lazy(() => import("./pages/Messagerie").then((m) => ({ default: m.Messagerie })));
const ParentHome = lazy(() => import("./pages/ParentHome").then((m) => ({ default: m.ParentHome })));
const ParentCarte = lazy(() => import("./pages/ParentCarte").then((m) => ({ default: m.ParentCarte })));
const ParentMessagerie = lazy(() => import("./pages/ParentMessagerie").then((m) => ({ default: m.ParentMessagerie })));

/** Accueil selon le rôle (évite la boucle de redirection pour CHAUFFEUR/PARENT). */
function RoleHome() {
  const { role } = useAuth();
  if (role === "CHAUFFEUR") return <Navigate to="/chauffeur" replace />;
  if (role === "PARENT") return <Navigate to="/parent" replace />;
  return <Suspense fallback={<Spinner />}><Dashboard /></Suspense>; // ADMIN
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<RequireAuth><AppLayout /></RequireAuth>}>
        <Route index element={<RoleHome />} />
        <Route path="chauffeur" element={<RequireAuth roles={["CHAUFFEUR", "ADMIN"]}><Suspense fallback={<Spinner />}><ChauffeurHome /></Suspense></RequireAuth>} />
        <Route path="chauffeur/carte" element={<RequireAuth roles={["CHAUFFEUR", "ADMIN"]}><Suspense fallback={<Spinner />}><ChauffeurCarte /></Suspense></RequireAuth>} />
        <Route path="chauffeur/eta" element={<RequireAuth roles={["CHAUFFEUR", "ADMIN"]}><Suspense fallback={<Spinner />}><ChauffeurEta /></Suspense></RequireAuth>} />
        <Route path="chauffeur/incidents" element={<RequireAuth roles={["CHAUFFEUR", "ADMIN"]}><Suspense fallback={<Spinner />}><ChauffeurIncidents /></Suspense></RequireAuth>} />
        <Route path="chauffeur/notifications" element={<RequireAuth roles={["CHAUFFEUR", "ADMIN"]}><Suspense fallback={<Spinner />}><ChauffeurNotifs /></Suspense></RequireAuth>} />
        <Route path="chauffeur/historique" element={<RequireAuth roles={["CHAUFFEUR", "ADMIN"]}><Suspense fallback={<Spinner />}><ChauffeurHistorique /></Suspense></RequireAuth>} />
        <Route path="messages" element={<RequireAuth roles={["ADMIN", "CHAUFFEUR"]}><Suspense fallback={<Spinner />}><Messagerie /></Suspense></RequireAuth>} />
        <Route path="parent" element={<RequireAuth roles={["PARENT"]}><Suspense fallback={<Spinner />}><ParentHome /></Suspense></RequireAuth>} />
        <Route path="parent/carte" element={<RequireAuth roles={["PARENT"]}><Suspense fallback={<Spinner />}><ParentCarte /></Suspense></RequireAuth>} />
        <Route path="parent/messages" element={<RequireAuth roles={["PARENT"]}><Suspense fallback={<Spinner />}><ParentMessagerie /></Suspense></RequireAuth>} />
        <Route path="parent/notifications" element={<RequireAuth roles={["PARENT"]}><Suspense fallback={<Spinner />}><ChauffeurNotifs /></Suspense></RequireAuth>} />
        <Route path="carte" element={<Suspense fallback={<Spinner />}><CarteLive /></Suspense>} />
        <Route path="clustering" element={<RequireAuth roles={["ADMIN"]}><Suspense fallback={<Spinner />}><Clustering /></Suspense></RequireAuth>} />
        <Route path="notifications" element={<RequireAuth roles={["ADMIN"]}><Suspense fallback={<Spinner />}><Notifications /></Suspense></RequireAuth>} />
        <Route path="eleves" element={<RequireAuth roles={["ADMIN"]}><Suspense fallback={<Spinner />}><Eleves /></Suspense></RequireAuth>} />
        <Route path="bus" element={<RequireAuth roles={["ADMIN"]}><Suspense fallback={<Spinner />}><BusPage /></Suspense></RequireAuth>} />
        <Route path="eta" element={<RequireAuth roles={["ADMIN"]}><Suspense fallback={<Spinner />}><EtaPrevisions /></Suspense></RequireAuth>} />
        <Route path="trajets" element={<RequireAuth roles={["ADMIN"]}><Suspense fallback={<Spinner />}><TrajetsEnCours /></Suspense></RequireAuth>} />
        <Route path="incidents" element={<RequireAuth roles={["ADMIN"]}><Suspense fallback={<Spinner />}><Incidents /></Suspense></RequireAuth>} />
        <Route path="anomalies" element={<RequireAuth roles={["ADMIN"]}><Suspense fallback={<Spinner />}><Anomalies /></Suspense></RequireAuth>} />
        <Route path="users" element={<RequireAuth roles={["ADMIN"]}><Suspense fallback={<Spinner />}><Users /></Suspense></RequireAuth>} />
        <Route path="settings" element={<RequireAuth roles={["ADMIN"]}><Suspense fallback={<Spinner />}><Settings /></Suspense></RequireAuth>} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
