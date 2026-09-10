import { createContext, useContext, useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import type { AuthResponse, Role } from "../api/types";
import { login as apiLogin } from "../api/endpoints";
import { setUnauthorizedHandler } from "../api/client";

interface AuthState {
  token: string | null;
  user: Omit<AuthResponse, "token"> | null;
  role: Role | null;
  login: (email: string, motDePasse: string) => Promise<void>;
  logout: () => void;
}

const Ctx = createContext<AuthState | null>(null);
const KEY = "ts_auth";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<Omit<AuthResponse, "token"> & { token: string } | null>(() => {
    const raw = localStorage.getItem(KEY);
    return raw ? JSON.parse(raw) : null;
  });

  const logout = useCallback(() => {
    localStorage.removeItem(KEY);
    localStorage.removeItem("token");
    setState(null);
  }, []);

  useEffect(() => setUnauthorizedHandler(logout), [logout]);

  const login = useCallback(async (email: string, motDePasse: string) => {
    const res = await apiLogin(email, motDePasse);
    localStorage.setItem("token", res.token);
    localStorage.setItem(KEY, JSON.stringify(res));
    setState(res);
  }, []);

  const value = useMemo<AuthState>(() => ({
    token: state?.token ?? null,
    user: state ? { userId: state.userId, nom: state.nom, email: state.email, role: state.role } : null,
    role: state?.role ?? null,
    login,
    logout,
  }), [state, login, logout]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useAuth hors AuthProvider");
  return c;
}
