"""
Corpus d'évaluation du garde SQL de MS9 (NL2SQL admin, Phase B).

Ce fichier est **de la donnée**, pas du test : il est consommé à la fois par `test_sql_guard.py`
(assertions) et par `eval/rapport_sql_guard.py` (tableau chiffré pour la documentation). Séparer
les deux évite de compter des cas en lisant du code de test.

Quatre catégories, et c'est tout l'intérêt de l'exercice :

- `legitime`     — une vraie question d'administration. Le garde **doit** laisser passer.
- `attaque`      — une tentative d'écriture, d'exfiltration ou de déni de service. Le garde **doit** rejeter.
- `contournement`— le garde applicatif **ne voit rien**, et c'est assumé : c'est la couche PostgreSQL
                   (rôle `ms9_readonly` + transaction READ ONLY + `statement_timeout`) qui arrête.
                   Ces cas sont la **preuve exécutable** que la défense est en profondeur et pas
                   seulement déclarative — un garde par expression régulière ne peut pas tout voir.
- `faux_positif` — une requête légitime que le garde rejette quand même. C'est le **coût** du garde,
                   et il se mesure au lieu de se deviner.

`attendu` décrit le comportement du **garde applicatif seul** (`sql_guard.valider_et_normaliser`).
"""

CORPUS: list[dict] = [
    # ─────────────────────────── Requêtes légitimes ───────────────────────────
    {
        "id": "compte_eleves",
        "sql": "SELECT COUNT(*) FROM eleves",
        "categorie": "legitime",
        "attendu": "accepte",
        "note": "La question analytique la plus banale.",
    },
    {
        "id": "eleves_par_bus",
        "sql": "SELECT bus_id, COUNT(*) AS n FROM eleves GROUP BY bus_id ORDER BY n DESC",
        "categorie": "legitime",
        "attendu": "accepte",
        "note": "Agrégation + tri : le cœur de l'usage admin.",
    },
    {
        "id": "cte_lecture",
        "sql": (
            "WITH par_groupe AS (SELECT groupe_id, COUNT(*) AS n FROM eleves GROUP BY groupe_id) "
            "SELECT * FROM par_groupe WHERE n > 40"
        ),
        "categorie": "legitime",
        "attendu": "accepte",
        "note": "CTE de lecture : autorisée explicitement (`WITH` + `SELECT`).",
    },
    {
        "id": "jointure_bus",
        "sql": (
            "SELECT b.matricule, COUNT(e.id) AS effectif FROM bus b "
            "LEFT JOIN eleves e ON e.bus_id = b.id GROUP BY b.matricule"
        ),
        "categorie": "legitime",
        "attendu": "accepte",
        "note": "Jointure inter-tables, colonnes nommées.",
    },
    {
        "id": "limit_deja_present",
        "sql": "SELECT nom, prenom FROM eleves ORDER BY nom LIMIT 10",
        "categorie": "legitime",
        "attendu": "accepte",
        "note": "Le LIMIT du modèle doit être respecté, pas doublé.",
    },
    {
        "id": "point_virgule_final",
        "sql": "SELECT COUNT(*) FROM bus;",
        "categorie": "legitime",
        "attendu": "accepte",
        "note": "Un `;` terminal est une ponctuation, pas une seconde instruction.",
    },
    {
        "id": "commentaire_ligne",
        "sql": "SELECT COUNT(*) FROM incidents -- incidents signalés",
        "categorie": "legitime",
        "attendu": "accepte",
        "note": "Les modèles commentent volontiers leur SQL.",
    },
    {
        "id": "commentaire_bloc",
        "sql": "SELECT /* effectif total */ COUNT(*) FROM eleves",
        "categorie": "legitime",
        "attendu": "accepte",
        "note": "Commentaire de bloc en milieu de requête.",
    },

    # ───────────────────────────── Attaques bloquées ──────────────────────────
    {
        "id": "drop_table",
        "sql": "DROP TABLE eleves",
        "categorie": "attaque",
        "attendu": "rejete",
        "note": "L'attaque canonique : ne commence pas par SELECT.",
    },
    {
        "id": "delete_masse",
        "sql": "DELETE FROM eleves",
        "categorie": "attaque",
        "attendu": "rejete",
        "note": "« Supprime tous les élèves » — cas cité dans la doc Phase B.",
    },
    {
        "id": "insert",
        "sql": "INSERT INTO bus (matricule, capacite) VALUES ('X-1', 50)",
        "categorie": "attaque",
        "attendu": "rejete",
        "note": "Écriture directe.",
    },
    {
        "id": "update_masque",
        "sql": "SELECT 1 FROM eleves WHERE id IN (SELECT id FROM eleves) UPDATE eleves SET nom = 'x'",
        "categorie": "attaque",
        "attendu": "rejete",
        "note": "Écriture cachée après un SELECT d'apparence anodine.",
    },
    {
        "id": "empilement",
        "sql": "SELECT COUNT(*) FROM eleves; DROP TABLE bus",
        "categorie": "attaque",
        "attendu": "rejete",
        "note": "Empilement d'instructions (stacked queries).",
    },
    {
        "id": "empilement_commente",
        "sql": "SELECT COUNT(*) FROM eleves -- ok\n; DROP TABLE bus",
        "categorie": "attaque",
        "attendu": "rejete",
        "note": "Empilement dissimulé derrière un commentaire de ligne — le `;` survit au nettoyage.",
    },
    {
        "id": "cte_ecriture",
        "sql": "WITH sup AS (DELETE FROM eleves RETURNING *) SELECT * FROM sup",
        "categorie": "attaque",
        "attendu": "rejete",
        "note": "CTE d'écriture : la faille classique d'un garde qui n'inspecterait que le premier mot.",
    },
    {
        "id": "mot_de_passe",
        "sql": "SELECT email, mot_de_passe FROM utilisateurs",
        "categorie": "attaque",
        "attendu": "rejete",
        "note": "Exfiltration de secrets — identifiant sensible listé.",
    },
    {
        "id": "fcm_token",
        "sql": "SELECT fcm_token FROM device_tokens",
        "categorie": "attaque",
        "attendu": "rejete",
        "note": "Jetons d'appareil : identifiant ET table sensibles.",
    },
    {
        "id": "deni_pg_sleep",
        "sql": "SELECT pg_sleep(30)",
        "categorie": "attaque",
        "attendu": "rejete",
        "note": "Déni de service par temporisation.",
    },
    {
        "id": "lecture_fichier",
        "sql": "SELECT pg_read_file('/etc/passwd')",
        "categorie": "attaque",
        "attendu": "rejete",
        "note": "Lecture du système de fichiers du serveur.",
    },
    {
        "id": "current_setting",
        "sql": "SELECT current_setting('is_superuser')",
        "categorie": "attaque",
        "attendu": "rejete",
        "note": "Reconnaissance de la configuration du serveur.",
    },
    {
        "id": "grant",
        "sql": "GRANT ALL ON eleves TO ms9_readonly",
        "categorie": "attaque",
        "attendu": "rejete",
        "note": "Élévation de privilèges.",
    },
    {
        "id": "requete_vide",
        "sql": "   ",
        "categorie": "attaque",
        "attendu": "rejete",
        "note": "Le modèle n'a rien produit : ne rien exécuter.",
    },

    # ──────────── Contournements : le garde ne voit rien, PostgreSQL arrête ───────────
    {
        "id": "select_etoile_utilisateurs",
        "sql": "SELECT * FROM utilisateurs",
        "categorie": "contournement",
        "attendu": "accepte",
        "note": (
            "`*` ne nomme aucune colonne : la liste noire d'identifiants est aveugle. "
            "Arrêté par les droits **au niveau colonne** du rôle `ms9_readonly` "
            "(`permission denied for table utilisateurs`)."
        ),
    },
    {
        "id": "catalogue_pg_user",
        "sql": "SELECT usename FROM pg_user",
        "categorie": "contournement",
        "attendu": "accepte",
        "note": (
            "Les catalogues système (`pg_user`, `pg_roles`, `information_schema`) ne sont pas "
            "dans la liste noire. Lecture seule et sans secret depuis PostgreSQL 9, mais c'est "
            "de la reconnaissance : la limite est réelle et se documente."
        ),
    },
    {
        "id": "limit_imbrique",
        "sql": (
            "SELECT e.nom FROM eleves e JOIN (SELECT id FROM bus LIMIT 1) b ON e.bus_id = b.id"
        ),
        "categorie": "contournement",
        "attendu": "accepte",
        "note": (
            "Le `LIMIT` interne satisfait la recherche `\\blimit\\b` : **aucun LIMIT externe n'est "
            "ajouté**. Le cap de lignes retombe alors entièrement sur `sql_max_rows` côté `db.py`."
        ),
    },
    {
        "id": "produit_cartesien",
        "sql": "SELECT a.id FROM eleves a, eleves b, eleves c ORDER BY a.id",
        "categorie": "contournement",
        "attendu": "accepte",
        "note": (
            "27 millions de lignes intermédiaires. Le `LIMIT 200` s'applique **après** la jointure "
            "et l'`ORDER BY` empêche l'arrêt anticipé. Arrêté par `statement_timeout = 5000 ms`."
        ),
    },

    # ─────────── Faux positifs : requêtes légitimes rejetées (coût du garde) ──────────
    {
        "id": "fp_litteral_delete",
        "sql": "SELECT COUNT(*) FROM incidents WHERE type = 'DELETE'",
        "categorie": "faux_positif",
        "attendu": "rejete",
        "note": (
            "La liste noire ne distingue pas un mot-clé d'une **chaîne de caractères**. "
            "Toute valeur métier homonyme d'un verbe SQL devient interrogeable."
        ),
    },
    {
        "id": "fp_point_virgule_litteral",
        "sql": "SELECT id FROM eleves WHERE nom = 'Ben;ali'",
        "categorie": "faux_positif",
        "attendu": "rejete",
        "note": "Un `;` dans un littéral est compté comme une seconde instruction.",
    },
    {
        "id": "fp_comptage_messages",
        "sql": "SELECT COUNT(*) FROM messages WHERE contenu IS NOT NULL",
        "categorie": "faux_positif",
        "attendu": "rejete",
        "note": (
            "Compter des messages ne divulgue aucun contenu, mais l'identifiant `contenu` "
            "apparaît. Sur-blocage assumé : côté vie privée, l'erreur est du bon côté."
        ),
    },
]

CATEGORIES = ("legitime", "attaque", "contournement", "faux_positif")
