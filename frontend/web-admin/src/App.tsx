import { lazy, Suspense } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { RequireAuth } from "./auth/RequireAuth";
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

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<RequireAuth><AppLayout /></RequireAuth>}>
        <Route index element={<RequireAuth roles={["ADMIN"]}><Suspense fallback={<Spinner />}><Dashboard /></Suspense></RequireAuth>} />
        <Route path="carte" element={<Suspense fallback={<Spinner />}><CarteLive /></Suspense>} />
        <Route path="clustering" element={<RequireAuth roles={["ADMIN"]}><Suspense fallback={<Spinner />}><Clustering /></Suspense></RequireAuth>} />
        <Route path="notifications" element={<Suspense fallback={<Spinner />}><Notifications /></Suspense>} />
        <Route path="eleves" element={<RequireAuth roles={["ADMIN", "CHAUFFEUR"]}><Suspense fallback={<Spinner />}><Eleves /></Suspense></RequireAuth>} />
        <Route path="bus" element={<RequireAuth roles={["ADMIN", "CHAUFFEUR"]}><Suspense fallback={<Spinner />}><BusPage /></Suspense></RequireAuth>} />
        <Route path="eta" element={<RequireAuth roles={["ADMIN", "CHAUFFEUR"]}><Suspense fallback={<Spinner />}><EtaPrevisions /></Suspense></RequireAuth>} />
        <Route path="incidents" element={<RequireAuth roles={["ADMIN"]}><Suspense fallback={<Spinner />}><Incidents /></Suspense></RequireAuth>} />
        <Route path="anomalies" element={<RequireAuth roles={["ADMIN"]}><Suspense fallback={<Spinner />}><Anomalies /></Suspense></RequireAuth>} />
        <Route path="users" element={<RequireAuth roles={["ADMIN"]}><Suspense fallback={<Spinner />}><Users /></Suspense></RequireAuth>} />
        <Route path="settings" element={<RequireAuth roles={["ADMIN"]}><Suspense fallback={<Spinner />}><Settings /></Suspense></RequireAuth>} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
