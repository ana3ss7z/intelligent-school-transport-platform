/**
 * Recette finale — Phase 8 : balayage des 27 routes de web-admin dans un vrai Chrome.
 *
 * web-admin n'a AUCUN test automatisé (ni vitest, ni playwright) : ses 27 routes et
 * tout son RBAC sont vérifiés à la main. Ce script remplace ce passage manuel.
 *
 * Pour chaque rôle (ADMIN, CHAUFFEUR, PARENT) :
 *   1. connexion RÉELLE par le formulaire (pas d'injection de jeton — c'est le
 *      parcours qu'on veut prouver) ;
 *   2. visite de chaque route autorisée : erreurs console, requêtes réseau en échec,
 *      détection d'ErrorBoundary, capture d'écran ;
 *   3. assertions RBAC : ce qu'un rôle NE doit PAS atteindre.
 *
 * Usage : node scripts/recette/balayage_front.mjs
 * Sortie : scripts/recette/resultats/balayage_front.json + captures/*.png
 */
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

// puppeteer-core est installé dans frontend/web-admin ; ce script vit ailleurs,
// donc on résout explicitement plutôt que de dépendre du cwd d'invocation.
const puppeteer = (await import(pathToFileURL(path.resolve(
  import.meta.dirname, "..", "..", "frontend", "web-admin",
  "node_modules", "puppeteer-core", "lib", "puppeteer", "puppeteer-core.js",
)).href)).default;

const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const BASE = "http://localhost:5173";
const RACINE = path.resolve(import.meta.dirname, "..", "..");
const OUT = path.join(RACINE, "scripts", "recette", "resultats");
const SHOTS = path.join(OUT, "captures");
fs.mkdirSync(SHOTS, { recursive: true });

const COMPTES = JSON.parse(
  fs.readFileSync(path.join(RACINE, "comptes_utilisateurs.json"), "utf8"),
);
const PARENT = COMPTES.parents[0];

const ROLES = {
  ADMIN: { email: "admin@transport.ma", mdp: "Admin123!" },
  CHAUFFEUR: { email: "chauffeur1@transport.ma", mdp: "Chauffeur123!" },
  PARENT: { email: PARENT.email, mdp: PARENT.motDePasse },
};

// Routes autorisées par rôle (relevées dans src/App.tsx)
const ROUTES = {
  ADMIN: ["/", "/carte", "/assistant", "/clustering", "/trajets", "/eta", "/incidents",
          "/anomalies", "/notifications", "/eleves", "/bus", "/users", "/settings", "/messages"],
  CHAUFFEUR: ["/chauffeur", "/chauffeur/carte", "/chauffeur/eta", "/chauffeur/incidents",
              "/chauffeur/notifications", "/chauffeur/historique", "/messages"],
  PARENT: ["/parent", "/parent/carte", "/parent/eta", "/parent/messages",
           "/parent/notifications", "/parent/assistant"],
};

// Ce qu'un rôle ne doit PAS atteindre : on attend une redirection hors de la route.
const INTERDITS = {
  CHAUFFEUR: ["/eleves", "/users", "/settings", "/clustering", "/parent", "/anomalies"],
  PARENT: ["/eleves", "/users", "/settings", "/clustering", "/chauffeur", "/anomalies", "/trajets"],
};

// Route sensible sans garde de rôle dans App.tsx — on vérifie ce qu'il en est réellement.
const A_QUALIFIER = { CHAUFFEUR: ["/carte"], PARENT: ["/carte"] };

const resultats = [];
const dodo = (ms) => new Promise((r) => setTimeout(r, ms));

// Bruit connu, sans rapport avec la santé de l'application.
const IGNORE = [
  /favicon/i, /Download the React DevTools/i, /\[vite\]/i,
  /source-?map/i, /net::ERR_ABORTED.*\.map/i,
];
const pertinent = (t) => !IGNORE.some((re) => re.test(t));

async function connecter(page, role) {
  const { email, mdp } = ROLES[role];
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle2", timeout: 60000 });
  await page.waitForSelector("#login-email", { timeout: 20000 });
  // Les champs sont pré-remplis en DEV (Login.tsx) : il faut les VIDER avant de
  // saisir. Un triple-clic + Backspace ne suffit pas sur un input contrôlé React
  // (la valeur se concatène) — Ctrl+A puis frappe déclenche bien onChange.
  for (const [sel, val] of [["#login-email", email], ["#login-pwd", mdp]]) {
    await page.focus(sel);
    await page.keyboard.down("Control");
    await page.keyboard.press("KeyA");
    await page.keyboard.up("Control");
    await page.keyboard.press("Backspace");
    await page.type(sel, val, { delay: 8 });
  }
  const saisi = await page.evaluate(() => ({
    e: document.querySelector("#login-email")?.value,
    p: document.querySelector("#login-pwd")?.value,
  }));
  if (saisi.e !== email) throw new Error(`saisie email incorrecte : ${saisi.e}`);
  await page.click('button[type="submit"]');
  await dodo(3500);
  const url = page.url();
  if (url.includes("/login")) throw new Error(`connexion refusée pour ${role} (reste sur /login)`);
  return url;
}

async function visiter(page, role, route, attendu) {
  const erreurs = [];
  const reseau = [];
  const onConsole = (m) => {
    if (m.type() === "error" && pertinent(m.text())) erreurs.push(m.text().slice(0, 200));
  };
  const onPageErr = (e) => erreurs.push(`PAGEERROR ${String(e).slice(0, 200)}`);
  const onResp = (r) => {
    const s = r.status();
    if (s >= 400 && pertinent(r.url())) reseau.push(`${s} ${r.url().replace(/^https?:\/\/[^/]+/, "")}`);
  };
  page.on("console", onConsole);
  page.on("pageerror", onPageErr);
  page.on("response", onResp);

  let urlFinale = "", texte = "", crash = false;
  try {
    await page.goto(BASE + route, { waitUntil: "networkidle2", timeout: 60000 });
    await dodo(2200); // laisser les sondages et le chargement différé se faire
    urlFinale = page.url();
    texte = await page.evaluate(() => document.body.innerText.slice(0, 4000));
    crash = /Une erreur est survenue|Something went wrong|ErrorBoundary/i.test(texte);
    const nom = `${role}${route.replace(/\//g, "_") || "_racine"}.png`;
    await page.screenshot({ path: path.join(SHOTS, nom) });
  } catch (e) {
    erreurs.push(`NAVIGATION ${String(e).slice(0, 200)}`);
  } finally {
    page.off("console", onConsole);
    page.off("pageerror", onPageErr);
    page.off("response", onResp);
  }

  const chemin = urlFinale.replace(BASE, "") || "(inconnu)";
  const reste = chemin === route || chemin.startsWith(route + "?");
  let ok, verdict;
  if (attendu === "accessible") {
    ok = reste && !crash && erreurs.length === 0;
    verdict = !reste ? `REDIRIGE vers ${chemin}` : crash ? "ErrorBoundary" :
              erreurs.length ? `${erreurs.length} erreur(s) console` : "rendu OK";
  } else {
    ok = !reste;
    verdict = reste ? "ATTEINTE alors qu'elle devrait être refusée" : `redirigé vers ${chemin}`;
  }

  const contenu = texte.replace(/\s+/g, " ").trim().slice(0, 90);
  resultats.push({ role, route, attendu, urlFinale: chemin, ok, verdict,
                   erreurs, reseau: [...new Set(reseau)].slice(0, 6), extrait: contenu });
  const tag = ok ? "OK  " : "ECART";
  console.log(`  [${tag}] ${role.padEnd(9)} ${route.padEnd(26)} ${verdict}`);
  if (erreurs.length) erreurs.slice(0, 2).forEach((e) => console.log(`           console: ${e}`));
  if (reseau.length) console.log(`           réseau : ${[...new Set(reseau)].slice(0, 4).join(" · ")}`);
}

const nav = await puppeteer.launch({
  executablePath: CHROME,
  headless: "new",
  args: ["--no-sandbox", "--disable-dev-shm-usage", "--window-size=1440,900"],
  defaultViewport: { width: 1440, height: 900 },
});

console.log("\n=== Recette Phase 8 — balayage des 27 routes de web-admin (Chrome réel) ===\n");

for (const role of ["ADMIN", "CHAUFFEUR", "PARENT"]) {
  const ctx = await nav.createBrowserContext(); // session isolée par rôle
  const page = await ctx.newPage();
  page.setDefaultTimeout(60000);
  try {
    const apres = await connecter(page, role);
    console.log(`── ${role} — connecté, atterrissage sur ${apres.replace(BASE, "")}`);
    for (const r of ROUTES[role]) await visiter(page, role, r, "accessible");
    for (const r of INTERDITS[role] ?? []) await visiter(page, role, r, "refusee");
    for (const r of A_QUALIFIER[role] ?? []) await visiter(page, role, r, "refusee");
  } catch (e) {
    console.log(`  [ECART] ${role} — ${e.message}`);
    resultats.push({ role, route: "/login", attendu: "connexion", ok: false, verdict: e.message });
  }
  await ctx.close();
  console.log("");
}

await nav.close();

const ecarts = resultats.filter((r) => !r.ok);
fs.writeFileSync(path.join(OUT, "balayage_front.json"),
  JSON.stringify({ date: new Date().toISOString(), total: resultats.length,
                   ecarts: ecarts.length, resultats }, null, 2), "utf8");

console.log(`=== ${resultats.length - ecarts.length}/${resultats.length} conformes · ${ecarts.length} écart(s) ===`);
console.log(`Captures : ${SHOTS}`);
if (ecarts.length) {
  console.log("\nÉcarts :");
  for (const e of ecarts) console.log(`  • ${e.role} ${e.route} → ${e.verdict}`);
}
process.exit(ecarts.length ? 2 : 0);
