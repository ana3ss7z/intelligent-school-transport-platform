import { Navigate, useLocation } from "react-router-dom";
import type { ReactNode } from "react";
import type { Role } from "../api/types";
import { useAuth } from "./AuthContext";

/** Garde de route : exige un token ; optionnellement un/des rôles. */
export function RequireAuth({ children, roles }: { children: ReactNode; roles?: Role[] }) {
  const { token, role } = useAuth();
  const loc = useLocation();
  if (!token) return <Navigate to="/login" state={{ from: loc }} replace />;
  if (roles && role && !roles.includes(role)) return <Navigate to="/" replace />;
  return <>{children}</>;
}
