import axios from "axios";

const GATEWAY = import.meta.env.VITE_GATEWAY ?? "http://localhost:8080";

/** Client axios unique — parle au backend via la Gateway. */
export const api = axios.create({ baseURL: GATEWAY, timeout: 20000 });

// Injection du Bearer token à chaque requête
api.interceptors.request.use((cfg) => {
  const t = localStorage.getItem("token");
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  return cfg;
});

// Gestion centralisée du 401 (token expiré/invalide → logout)
let onUnauthorized: (() => void) | null = null;
export const setUnauthorizedHandler = (fn: () => void) => {
  onUnauthorized = fn;
};
api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err?.response?.status === 401) onUnauthorized?.();
    return Promise.reject(err);
  },
);
