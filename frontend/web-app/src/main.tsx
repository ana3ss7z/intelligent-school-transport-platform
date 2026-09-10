import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "./index.css";
import { AuthProvider } from "./auth/AuthContext";
import { ToastProvider } from "./components/Toast";
import { ConfirmProvider } from "./components/ConfirmDialog";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { ParamsProvider } from "./params/ParamsContext";
import App from "./App";

// Thème appliqué AVANT le premier rendu. `useTheme` ne pose [data-theme] que depuis les écrans
// qui l'utilisent (via AppLayout) : au chargement direct de /login l'attribut manquait, donc la
// page s'affichait en clair malgré un choix « sombre » — puis basculait après connexion.
document.documentElement.setAttribute(
  "data-theme",
  localStorage.getItem("ts_theme") === "dark" ? "dark" : "light",
);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ErrorBoundary>
      <BrowserRouter>
        <ToastProvider>
          <ConfirmProvider>
            <AuthProvider>
              {/* Sous AuthProvider : la lecture des paramètres exige un jeton (tout rôle). */}
              <ParamsProvider>
                <App />
              </ParamsProvider>
            </AuthProvider>
          </ConfirmProvider>
        </ToastProvider>
      </BrowserRouter>
    </ErrorBoundary>
  </StrictMode>,
);
