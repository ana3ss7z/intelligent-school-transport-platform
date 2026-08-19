import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bus, ArrowRight, Eye, EyeOff } from "lucide-react";
import { useAuth } from "../auth/AuthContext";
import { Button } from "../components/ui";

/* Les identifiants de démonstration ne sont pré-remplis qu'en développement :
   une console livrée ne doit pas exposer un mot de passe dans son bundle. */
const DEMO = import.meta.env.DEV
  ? { email: "admin@transport.ma", pwd: "Admin123!" }
  : { email: "", pwd: "" };

/* ── Diagramme de réseau ──────────────────────────────────────────────────────
   Une tournée réelle : l'école est le dépôt, le bus ramasse dans l'ordre calculé
   puis y revient. Tracé en géométrie de plan de réseau (0°, 45°, 90°) — il annonce
   « réseau de transport » sans se faire passer pour une carte GPS.
   Composant hissé hors de Login : c'est du décor statique, il ne doit jamais
   re-rendre quand on saisit son email. */
const ARRETS = [
  { x: 48, y: 48 }, { x: 96, y: 168 }, { x: 168, y: 168 },
  { x: 216, y: 216 }, { x: 216, y: 272 }, { x: 168, y: 320 }, { x: 120, y: 320 },
];
const TRACE = "M48,48 V120 L96,168 H168 L216,216 V272 L168,320 H120 L72,368";

function DiagrammeReseau() {
  return (
    <svg viewBox="0 0 320 400" className="w-full max-w-90 max-h-[52vh]" aria-hidden="true">
      {/* Lignes voisines. Elles SORTENT du cadre au lieu de s'arrêter en l'air : une ligne
          coupée net se lit comme une rayure, pas comme un réseau qui continue.
          La seconde rejoint l'école — la flotte compte 7 bus, tous y convergent. */}
      <path d="M296,-16 V80 L240,136 V240 L296,296 V416" fill="none" stroke="var(--line2)"
        strokeWidth="2" strokeLinecap="round" opacity="0.45" />
      <path d="M-16,264 H24 L72,312 V368" fill="none" stroke="var(--ok)"
        strokeWidth="2" strokeLinecap="round" opacity="0.45" />

      {/* Tournée mise en avant */}
      <path className="route-trace" d={TRACE} fill="none" stroke="var(--route)"
        strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" />

      {ARRETS.map((a, i) => (
        <circle key={i} className="route-stop" cx={a.x} cy={a.y} r="5.5"
          fill="var(--surface-deep)" stroke="#fff" strokeWidth="2.5"
          style={{ animationDelay: `${0.5 + i * 0.32}s` }} />
      ))}

      {/* École : terminus de la tournée */}
      <circle className="route-ecole-halo" cx="72" cy="368" r="17" fill="var(--warn)" />
      <circle className="route-stop" cx="72" cy="368" r="9" fill="#fff"
        style={{ animationDelay: "2.7s" }} />
      <text x="94" y="373" fill="#fff" fontSize="12" fontFamily="var(--font-mono)"
        letterSpacing="1.5" opacity="0.85">ÉCOLE</text>
    </svg>
  );
}

/* Le pipeline réel du système — chaque étape est un microservice, pas un slogan. */
const PIPELINE = [
  { n: "Regroupement", d: "élèves → bus, sous contrainte de capacité" },
  { n: "Tournée", d: "ordre de passage optimisé" },
  { n: "Arrivée", d: "heure prédite, suivie en direct" },
];

function Pipeline() {
  return (
    <ol className="space-y-2.5">
      {PIPELINE.map((p, i) => (
        <li key={p.n} className="pipeline-step flex items-baseline gap-3"
          style={{ animationDelay: `${1.6 + i * 0.25}s` }}>
          {/* Le rang est déjà porté par <ol> : ce chiffre n'est que sa forme visible. */}
          <span aria-hidden className="font-mono text-[10px] text-white/40 tabular-nums w-3">{i + 1}</span>
          <span className="font-display text-[15px] text-white">{p.n}</span>
          <span className="text-white/45 text-[12px]">{p.d}</span>
        </li>
      ))}
    </ol>
  );
}

export function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState(DEMO.email);
  const [pwd, setPwd] = useState(DEMO.pwd);
  const [visible, setVisible] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null); setBusy(true);
    try { await login(email, pwd); nav("/"); }
    catch { setErr("Email ou mot de passe incorrect."); }
    finally { setBusy(false); }
  };

  // Pas de `outline-none` : il masquerait l'anneau `:focus-visible` global (index.css).
  // La bordure colorée s'y ajoute, elle ne le remplace pas.
  const champ = "w-full rounded-lg border border-line bg-panel px-3 py-2.5 text-sm transition-colors focus:border-route";
  const etiquette = "block text-[11px] font-mono uppercase tracking-wider text-ink-soft mb-1.5";

  return (
    <div className="min-h-svh grid lg:grid-cols-[1.05fr_1fr]">
      {/* ── Volet réseau ─────────────────────────────────────────────── */}
      {/* Lueur radiale centrée sur le diagramme : elle éclaire le héros et laisse les bords
          plus profonds. Un dégradé linéaire éteignait le navy PILE sur la couture, où le volet
          rencontre le noir du formulaire — les deux panneaux se confondaient. */}
      <div className="hidden lg:flex flex-col justify-between p-12 text-white relative overflow-hidden"
        style={{
          background:
            "radial-gradient(115% 85% at 42% 42%, #17395f 0%, var(--surface-deep) 52%, #0a1e33 100%)",
        }}>
        <div className="flex items-center gap-2.5">
          <span className="grid place-items-center size-9 rounded-lg bg-white/10"><Bus size={20} aria-hidden /></span>
          <span className="font-display font-semibold tracking-tight">Transport Meknès</span>
        </div>

        {/* Centré : collé à gauche, le diagramme laissait ~575 px de vide à sa droite. */}
        <div className="my-auto flex justify-center py-6"><DiagrammeReseau /></div>

        <div className="space-y-6">
          <Pipeline />
          <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-white/35">
            7 bus · 300 élèves · trajet réduit de 12,6 %
          </p>
        </div>
      </div>

      {/* ── Formulaire ───────────────────────────────────────────────── */}
      <main className="flex items-center justify-center p-6">
        <form onSubmit={submit} className="w-full max-w-sm">
          {/* Marque rappelée sur petit écran, où le volet réseau est masqué */}
          <div className="lg:hidden flex items-center gap-2.5 mb-8">
            <span className="grid place-items-center size-9 rounded-lg text-white"
              style={{ background: "var(--surface-deep)" }}><Bus size={20} aria-hidden /></span>
            <span className="font-display font-semibold tracking-tight">Transport Meknès</span>
          </div>

          <h1 className="text-2xl mb-1.5">Connexion</h1>
          <p className="text-ink-soft text-sm mb-7">
            Console de transport scolaire — administration, chauffeurs, familles.
          </p>

          <label htmlFor="login-email" className={etiquette}>Email</label>
          <input id="login-email" name="email" type="email" autoComplete="email" required autoFocus
            spellCheck={false} inputMode="email"
            value={email} onChange={(e) => setEmail(e.target.value)} className={`${champ} mb-4`} />

          <label htmlFor="login-pwd" className={etiquette}>Mot de passe</label>
          <div className="relative mb-5">
            <input id="login-pwd" name="password" type={visible ? "text" : "password"}
              autoComplete="current-password" required spellCheck={false}
              value={pwd} onChange={(e) => setPwd(e.target.value)} className={`${champ} pr-11`} />
            <button type="button" onClick={() => setVisible((v) => !v)}
              aria-label={visible ? "Masquer le mot de passe" : "Afficher le mot de passe"}
              className="absolute right-1 top-1/2 -translate-y-1/2 grid place-items-center size-9 rounded-md text-ink-soft transition-colors hover:text-ink">
              {visible ? <EyeOff size={16} aria-hidden /> : <Eye size={16} aria-hidden />}
            </button>
          </div>

          <div aria-live="polite">
            {err ? <p className="mb-4 text-sm text-alert" role="alert">{err}</p> : null}
          </div>

          <Button type="submit" disabled={busy} full>
            {busy ? "Connexion…" : "Se connecter"} <ArrowRight size={16} aria-hidden />
          </Button>
        </form>
      </main>
    </div>
  );
}
