import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bus, ArrowRight } from "lucide-react";
import { useAuth } from "../auth/AuthContext";
import { Button } from "../components/ui";

export function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("admin@transport.ma");
  const [pwd, setPwd] = useState("Admin123!");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null); setBusy(true);
    try { await login(email, pwd); nav("/"); }
    catch { setErr("Identifiants invalides."); }
    finally { setBusy(false); }
  };

  return (
    <div className="min-h-svh grid lg:grid-cols-2">
      {/* Volet signalétique */}
      <div className="hidden lg:flex flex-col justify-between p-10 text-white relative overflow-hidden"
        style={{ background: "var(--header)" }}>
        <div className="flex items-center gap-2.5">
          <span className="grid place-items-center size-9 rounded-lg bg-white/10"><Bus size={20} /></span>
          <span className="font-display font-semibold">Transport Meknès</span>
        </div>
        {/* ligne + stations décoratives (motif signature) */}
        <div className="relative pl-6 my-auto">
          <span className="station-line absolute left-[9px] top-2 bottom-2 w-0.5 bg-white/30" aria-hidden />
          {["Ramassage", "Trajet optimisé", "Arrivée école"].map((s, i) => (
            <div key={s} className="relative py-4">
              <span className="absolute -left-[15px] top-5 size-3 rounded-full border-2 border-white"
                style={{ background: i === 2 ? "#fff" : "transparent" }} aria-hidden />
              <div className="font-display text-xl">{s}</div>
              <div className="text-white/60 text-sm font-mono uppercase tracking-wider">étape {i + 1}</div>
            </div>
          ))}
        </div>
        <p className="text-white/50 text-sm max-w-sm">
          Console d'administration — clustering, tournées, suivi GPS temps réel, prédiction ETA et anomalies.
        </p>
      </div>

      {/* Formulaire */}
      <div className="flex items-center justify-center p-6">
        <form onSubmit={submit} className="w-full max-w-sm">
          <h1 className="text-2xl mb-1">Connexion</h1>
          <p className="text-ink-soft text-sm mb-6">Accédez à la console de transport scolaire.</p>

          <label htmlFor="login-email" className="block text-[11px] font-mono uppercase tracking-wider text-ink-soft mb-1">Email</label>
          <input id="login-email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required
            className="w-full mb-4 rounded-lg border border-line bg-panel px-3 py-2.5 text-sm outline-none focus:border-route" />

          <label htmlFor="login-pwd" className="block text-[11px] font-mono uppercase tracking-wider text-ink-soft mb-1">Mot de passe</label>
          <input id="login-pwd" type="password" autoComplete="current-password" value={pwd} onChange={(e) => setPwd(e.target.value)} required
            className="w-full mb-5 rounded-lg border border-line bg-panel px-3 py-2.5 text-sm outline-none focus:border-route" />

          {err && <div className="mb-4 text-sm text-alert" role="alert">{err}</div>}

          <Button type="submit" disabled={busy}>
            {busy ? "Connexion…" : "Se connecter"} <ArrowRight size={16} />
          </Button>
        </form>
      </div>
    </div>
  );
}
