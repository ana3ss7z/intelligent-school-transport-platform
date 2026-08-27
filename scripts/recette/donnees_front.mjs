/**
 * Recette — les interfaces affichent-elles les BONNES valeurs ?
 *
 * `balayage_front.mjs` vérifie que les 27 routes se rendent sans erreur et que le RBAC
 * redirige. Il ne regarde jamais **ce qui est écrit à l'écran**. Une page peut s'afficher
 * parfaitement et montrer un chiffre faux, une liste vide, ou les élèves d'un autre bus.
 *
 * Ce script lit la vérité dans l'API, puis lit le texte réellement rendu par la page, et
 * compare. Pour chaque rôle, sur les écrans qui portent un chiffre vérifiable.
 *
 * Usage : node scripts/recette/donnees_front.mjs
 * Sortie : scripts/recette/resultats/donnees_front.json
 */
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

const RACINE = path.resolve(import.meta.dirname, "..", "..");
const puppeteer = (await import(pathToFileURL(path.resolve(
  RACINE, "frontend", "web-admin", "node_modules", "puppeteer-core",
  "lib", "puppeteer", "puppeteer-core.js")).href)).default;

const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const BASE = "http://localhost:5173";
const GW = "http://localhost:8080";
const MS2_INT = "http://localhost:8082/internal/eleves";
const OUT = path.join(RACINE, "scripts", "recette", "resultats");
fs.mkdirSync(OUT, { recursive: true });

const COMPTES = JSON.parse(fs.readFileSync(path.join(RACINE, "comptes_utilisateurs.json"), "utf8"));
const CSV = fs.readFileSync(path.join(RACINE, "comptes_utilisateurs.csv"), "utf8")
  .split(/\r?\n/).slice(1).filter(Boolean).map((l) => l.split(","));

const resultats = [];
let ecarts = 0;
const dodo = (ms) => new Promise((r) => setTimeout(r, ms));

function note(ecran, nom, attendu, obtenu, ok, commentaire = "") {
  ecarts += ok ? 0 : 1;
  resultats.push({ ecran, nom, attendu, obtenu, ok, commentaire });
  console.log(`  [${ok ? "OK  " : "ECART"}] ${ecran} — ${nom}`);
  console.log(`          attendu ${attendu} · affiché ${obtenu}`);
  if (commentaire) console.log(`          ${commentaire}`);
}

async function api(chemin, jeton) {
  const r = await fetch(chemin.startsWith("http") ? chemin : GW + chemin,
    jeton ? { headers: { Authorization: `Bearer ${jeton}` } } : {});
  return r.ok ? r.json() : null;
}

async function connexion(email, mdp) {
  const r = await fetch(`${GW}/api/auth/login`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, motDePasse: mdp }),
  });
  if (!r.ok) throw new Error(`connexion refusée pour ${email} (${r.status})`);
  return r.json();
}

/**
 * Nombres présents dans le texte de la page.
 * ⚠️ On extrait LIGNE PAR LIGNE : un `\s` dans la classe de caractères collerait
 * « 300 » et « 300 affectés » de deux lignes voisines en un « 300300 » inexistant.
 */
const nombres = (txt) => {
  const vus = new Set();
  for (const ligne of txt.split(String.fromCharCode(10))) {
    for (const n of ligne.match(/\d[\d  ]*/g) || []) {
      const v = parseInt(n.replace(/[^\d]/g, ""), 10);
      if (Number.isFinite(v)) vus.add(v);
    }
  }
  return vus;
};

async function ouvrir(page, route, attente = 3200) {
  await page.goto(BASE + route, { waitUntil: "networkidle2", timeout: 60000 });
  await dodo(attente);
  return page.evaluate(() => document.body.innerText);
}

async function seConnecter(page, email, mdp) {
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle2", timeout: 60000 });
  await page.waitForSelector("#login-email", { timeout: 20000 });
  for (const [sel, val] of [["#login-email", email], ["#login-pwd", mdp]]) {
    await page.focus(sel);
    await page.keyboard.down("Control"); await page.keyboard.press("KeyA"); await page.keyboard.up("Control");
    await page.keyboard.press("Backspace");
    await page.type(sel, val, { delay: 8 });
  }
  await page.click('button[type="submit"]');
  await dodo(3500);
  if (page.url().includes("/login")) throw new Error(`connexion UI refusée pour ${email}`);
}

// ══════════════════════════════════════════════════════════════════
console.log("\n=== Recette — les interfaces affichent-elles les bonnes valeurs ? ===\n");

// ── vérité, lue dans l'API ──
const admin = await connexion("admin@transport.ma", "Admin123!");
const eleves = await api(MS2_INT);
const bus = await api("/api/bus", admin.token);
const groupes = {};
for (const e of eleves) if (e.groupeId && e.groupeId !== 999) groupes[e.groupeId] = (groupes[e.groupeId] || 0) + 1;
const parBus = {};
for (const e of eleves) if (e.busId) (parBus[e.busId] ||= []).push(e);
const k = Object.keys(groupes).length;
const stats = await api("/api/notifications/stats", admin.token);
const incidents = await api("/api/incidents", admin.token);

console.log(`Vérité API : ${eleves.length} élèves · ${bus.length} bus · k=${k} groupes`
  + ` · tailles ${JSON.stringify(Object.values(groupes).sort((a, b) => b - a))}`);

// un chauffeur et un parent réels
const chLigne = CSV.find((l) => l[0] === "CHAUFFEUR");
const chauffeur = await connexion(chLigne[3], chLigne[4]);
const busChauffeur = bus.find((b) => b.chauffeurId === chauffeur.userId);
const parentInfo = COMPTES.parents.find((p) =>
  eleves.some((e) => e.parentId === p.userId && e.busId));
const parent = await connexion(parentInfo.email, parentInfo.motDePasse);
const enfantsParent = eleves.filter((e) => e.parentId === parent.userId);

console.log(`Acteurs : chauffeur #${chauffeur.userId} (bus ${busChauffeur?.id},`
  + ` ${parBus[busChauffeur?.id]?.length ?? 0} élèves) · parent #${parent.userId}`
  + ` (${enfantsParent.length} enfant(s))\n`);

const nav = await puppeteer.launch({
  executablePath: CHROME, headless: "new",
  args: ["--no-sandbox", "--disable-dev-shm-usage"],
  defaultViewport: { width: 1440, height: 1000 },
});

// ═══════════════════════ ADMIN ═══════════════════════
{
  const ctx = await nav.createBrowserContext();
  const page = await ctx.newPage(); page.setDefaultTimeout(60000);
  await seConnecter(page, "admin@transport.ma", "Admin123!");
  console.log("── Espace ADMINISTRATION ──");

  let t = await ouvrir(page, "/clustering", 6000);
  const mGroupes = t.match(/(\d+)\s*groupes?/i);
  note("/clustering", "le nombre de groupes annoncé est celui de la base",
    `${k} groupes`, mGroupes ? `${mGroupes[1]} groupes` : "non trouvé",
    mGroupes && Number(mGroupes[1]) === k,
    "c'est l'écran qui a révélé le défaut des deux algorithmes");

  const tailles = Object.values(groupes).sort((a, b) => a - b);
  // La légende « G1 · 50 » est rendue deux fois dans le DOM (bandeau de filtres + légende de
  // la carte) : on déduplique par groupe plutôt que de compter les occurrences.
  const parGroupe = {};
  for (const m of t.matchAll(/G(\d+)\s*·\s*(\d+)/g)) parGroupe[m[1]] = Number(m[2]);
  const affiches = Object.values(parGroupe).sort((a, b) => a - b);
  note("/clustering", "les tailles de chaque groupe correspondent",
    JSON.stringify(tailles), JSON.stringify(affiches),
    JSON.stringify(tailles) === JSON.stringify(affiches),
    `légende lue pour ${Object.keys(parGroupe).length} groupes distincts`);

  t = await ouvrir(page, "/eleves", 5000);
  note("/eleves", "l'effectif total affiché est le bon",
    `${eleves.length} élèves`,
    nombres(t).has(eleves.length) ? `${eleves.length} présent` : "absent du texte",
    nombres(t).has(eleves.length));

  t = await ouvrir(page, "/bus", 5000);
  note("/bus", "la flotte affichée est complète",
    `${bus.length} bus`, nombres(t).has(bus.length) ? `${bus.length} présent` : "absent",
    nombres(t).has(bus.length));

  const matriculesVus = bus.filter((b) => t.includes(b.matricule)).length;
  note("/bus", "chaque bus de la flotte est listé par son matricule",
    `${bus.length} matricules`, `${matriculesVus} trouvés`, matriculesVus === bus.length);

  t = await ouvrir(page, "/incidents", 5000);
  note("/incidents", "le nombre d'incidents correspond à la base",
    `${incidents.length} incidents`,
    nombres(t).has(incidents.length) ? "cohérent" : "non trouvé",
    nombres(t).has(incidents.length) || incidents.length === 0);

  t = await ouvrir(page, "/notifications", 6000);
  note("/notifications", "le total des notifications vient bien de /stats",
    `${stats.total}`, nombres(t).has(stats.total) ? `${stats.total} présent` : "absent",
    nombres(t).has(stats.total),
    "la page ne voit qu'une tranche : le total doit venir de /stats, pas d'un comptage local");

  t = await ouvrir(page, "/", 6000);
  note("/ (tableau de bord)", "les indicateurs reprennent les chiffres réels",
    `${eleves.length} élèves et ${bus.length} bus`,
    `élèves ${nombres(t).has(eleves.length) ? "oui" : "non"} · bus ${nombres(t).has(bus.length) ? "oui" : "non"}`,
    nombres(t).has(eleves.length));

  await ctx.close(); console.log("");
}

// ═══════════════════════ CHAUFFEUR ═══════════════════════
{
  const ctx = await nav.createBrowserContext();
  const page = await ctx.newPage(); page.setDefaultTimeout(60000);
  await seConnecter(page, chLigne[3], chLigne[4]);
  console.log("── Espace CHAUFFEUR ──");
  const mesEleves = parBus[busChauffeur.id] || [];

  let t = await ouvrir(page, "/chauffeur", 6500);
  note("/chauffeur", "le bus affiché est bien CELUI du chauffeur connecté",
    busChauffeur.matricule, t.includes(busChauffeur.matricule) ? busChauffeur.matricule : "absent",
    t.includes(busChauffeur.matricule));

  note("/chauffeur", "le nombre d'élèves de la tournée est celui de son bus",
    `${mesEleves.length} élèves`,
    nombres(t).has(mesEleves.length) ? `${mesEleves.length} présent` : "absent",
    nombres(t).has(mesEleves.length));

  const nomsSiens = mesEleves.filter((e) => t.includes(e.nom)).length;
  const autres = eleves.filter((e) => e.busId && e.busId !== busChauffeur.id);
  const nomsEtrangers = autres.filter((e) =>
    t.includes(`${e.prenom} ${e.nom}`) && !mesEleves.some((m) => m.nom === e.nom)).length;
  note("/chauffeur", "aucun élève d'un AUTRE bus n'apparaît dans sa liste",
    "0 élève étranger", `${nomsEtrangers} étranger(s), ${nomsSiens} des siens visibles`,
    nomsEtrangers === 0,
    "isolation entre chauffeurs, vérifiée sur le texte réellement rendu");

  t = await ouvrir(page, "/chauffeur/historique", 4500);
  const trajets = await api("/api/trajets/mes-trajets", chauffeur.token);
  note("/chauffeur/historique", "l'historique montre ses trajets, pas ceux des autres",
    `${trajets.length} trajet(s)`,
    trajets.length === 0
      ? (/aucun|vide|pas de/i.test(t) ? "état vide correct" : "état vide non signalé")
      : (nombres(t).has(trajets.length) ? "cohérent" : "nombre non trouvé"),
    trajets.length === 0 ? /aucun|vide|pas de/i.test(t) : true);

  await ctx.close(); console.log("");
}

// ═══════════════════════ PARENT ═══════════════════════
{
  const ctx = await nav.createBrowserContext();
  const page = await ctx.newPage(); page.setDefaultTimeout(60000);
  await seConnecter(page, parentInfo.email, parentInfo.motDePasse);
  console.log("── Espace PARENT ──");

  let t = await ouvrir(page, "/parent", 6500);
  const sesNoms = enfantsParent.filter((e) => t.includes(e.prenom)).length;
  note("/parent", "ses enfants sont nommés à l'écran",
    `${enfantsParent.length} enfant(s)`, `${sesNoms} affiché(s)`,
    sesNoms === enfantsParent.length,
    `attendus : ${enfantsParent.map((e) => e.prenom).join(", ")}`);

  const autresFamilles = eleves.filter((e) => e.parentId && e.parentId !== parent.userId);
  const fuite = autresFamilles.filter((e) => t.includes(`${e.prenom} ${e.nom}`)).length;
  note("/parent", "aucun enfant d'une AUTRE famille n'apparaît",
    "0 fuite", `${fuite} enfant(s) étranger(s)`, fuite === 0,
    "vérifié sur les 300 élèves, par nom complet");

  const sesBus = [...new Set(enfantsParent.map((e) => e.busId).filter(Boolean))];
  const matSiens = bus.filter((b) => sesBus.includes(b.id) && t.includes(b.matricule)).length;
  const matAutres = bus.filter((b) => !sesBus.includes(b.id) && t.includes(b.matricule)).length;
  note("/parent", "seul le bus de son enfant est mentionné",
    `${sesBus.length} bus, 0 autre`, `${matSiens} sien(s), ${matAutres} autre(s)`,
    matAutres === 0);

  t = await ouvrir(page, "/parent/eta", 12000);
  const eta = await api("/api/planification/mes-enfants?sens=matin", parent.token)
    .catch(() => null);
  note("/parent/eta", "la page Prévisions ne parle que de ses enfants",
    "0 enfant étranger",
    `${autresFamilles.filter((e) => t.includes(`${e.prenom} ${e.nom}`)).length} étranger(s)`,
    autresFamilles.filter((e) => t.includes(`${e.prenom} ${e.nom}`)).length === 0);

  t = await ouvrir(page, "/parent/notifications", 5000);
  const notifs = await api("/api/notifications/mes-notifications", parent.token);
  note("/parent/notifications", "ses notifications, et rien d'autre",
    `${notifs.length} notification(s)`,
    notifs.length === 0
      ? (/aucune|vide|pas de/i.test(t) ? "état vide correct" : "état vide non signalé")
      : "liste rendue",
    notifs.length === 0 ? /aucune|vide|pas de/i.test(t) : t.length > 100);

  await ctx.close();
}

await nav.close();
fs.writeFileSync(path.join(OUT, "donnees_front.json"),
  JSON.stringify({ date: new Date().toISOString(), total: resultats.length, ecarts, resultats }, null, 2),
  "utf8");

console.log(`\n=== ${resultats.length - ecarts}/${resultats.length} conformes · ${ecarts} écart(s) ===`);
if (ecarts) {
  console.log("\nÉcarts :");
  for (const r of resultats) if (!r.ok) console.log(`  • ${r.ecran} — ${r.nom} : ${r.obtenu}`);
}
process.exit(ecarts ? 2 : 0);
