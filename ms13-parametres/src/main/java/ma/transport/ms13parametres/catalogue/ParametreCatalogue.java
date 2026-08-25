package ma.transport.ms13parametres.catalogue;

import ma.transport.ms13parametres.entity.Parametre.Groupe;
import ma.transport.ms13parametres.entity.Parametre.Impact;
import ma.transport.ms13parametres.entity.Parametre.TypeParam;

import java.util.List;

import static ma.transport.ms13parametres.entity.Parametre.Groupe.*;
import static ma.transport.ms13parametres.entity.Parametre.Impact.*;

/**
 * Catalogue des paramètres — la déclaration fait autorité, la base ne stocke que les valeurs.
 * ===========================================================================================
 *
 * <p><b>Règle absolue : les défauts ci-dessous doivent refléter EXACTEMENT ce que contiennent
 * aujourd'hui les `config.py` / `application.properties` / constantes Java.</b> Le catalogue est
 * un miroir de l'état courant, pas une occasion de corriger discrètement une valeur : un défaut
 * qui diverge du code produirait, au premier démarrage de MS13, un changement de comportement
 * que personne n'a demandé et que rien n'expliquerait dans le journal.
 *
 * <p>Deux conséquences pratiques :
 * <ul>
 *   <li>{@code ms9.gemini_model} vaut bien {@code gemini-2.0-flash} — modèle pourtant mort
 *       (404 sur 36/36 appels, mesuré le 23/08). Ce n'est pas un oubli : le corriger ici
 *       masquerait la panne. L'admin le corrige depuis l'écran, ce qui est précisément le
 *       problème que MS13 résout ;</li>
 *   <li>{@code ms11.vitesse_pings_consecutifs} vaut {@code 1}, c'est-à-dire le comportement
 *       actuel (aucun anti-rebond) et non la valeur recommandée.</li>
 * </ul>
 *
 * <p>Les valeurs d'énumération météo/trafic sont recopiées de {@code ms12-prediction/features.py}
 * ({@code METEO_CATS}, {@code TRAFIC_CATS}). Toute divergence produirait un vecteur one-hot
 * entièrement nul — c'est-à-dire une prédiction silencieusement fausse, sans erreur.
 */
public final class ParametreCatalogue {

    private ParametreCatalogue() {}

    /**
     * Définition d'un paramètre. {@code min}/{@code max} ne concernent que {@link TypeParam#NUMBER},
     * {@code options} que {@link TypeParam#ENUM}.
     */
    public record Def(
            String cle, Groupe groupe, TypeParam type, String defaut,
            Double min, Double max, String options,
            String libelle, String description, String unite,
            boolean sensible, Impact impact
    ) {}

    // ── Fabriques : rendent la liste lisible d'un coup d'œil ──────────────────

    private static Def num(String cle, Groupe g, String defaut, double min, double max,
                           String unite, String libelle, String desc, Impact im) {
        return new Def(cle, g, TypeParam.NUMBER, defaut, min, max, null, libelle, desc, unite, false, im);
    }

    private static Def bool(String cle, Groupe g, String defaut, String libelle, String desc, Impact im) {
        return new Def(cle, g, TypeParam.BOOLEAN, defaut, null, null, null, libelle, desc, null, false, im);
    }

    private static Def enumere(String cle, Groupe g, String defaut, String options,
                               String libelle, String desc, Impact im) {
        return new Def(cle, g, TypeParam.ENUM, defaut, null, null, options, libelle, desc, null, false, im);
    }

    private static Def texte(String cle, Groupe g, String defaut, String libelle, String desc, Impact im) {
        return new Def(cle, g, TypeParam.STRING, defaut, null, null, null, libelle, desc, null, false, im);
    }

    private static Def secret(String cle, Groupe g, String libelle, String desc) {
        return new Def(cle, g, TypeParam.SECRET, "", null, null, null, libelle, desc, null, true, IMMEDIAT);
    }

    /** L'ordre de cette liste est l'ordre d'affichage dans chaque onglet. */
    public static final List<Def> DEFS = List.of(

        // ══ ÉCOLE ══════════════════════════════════════════════════════════════
        texte("ecole.nom", ECOLE, "École Al Massira",
              "Nom de l'école",
              "Affiché dans les applications parent et chauffeur.", IMMEDIAT),
        num("ecole.lat", ECOLE, "33.893", 27.0, 36.0, "°",
            "Latitude de l'école",
            "Destination des tournées (MS5), cible de l'ETA (MS12) et point de déclenchement de la "
            + "notification « bus arrivé » (MS4). MS4 utilisait auparavant 33.8850, soit ~900 m plus "
            + "au sud que les cinq autres services — cette clé unique supprime la divergence.", IMMEDIAT),
        num("ecole.lng", ECOLE, "-5.5455", -14.0, -1.0, "°",
            "Longitude de l'école", "Voir la latitude.", IMMEDIAT),
        num("ecole.rayon_arrivee_m", ECOLE, "150", 20, 2000, "m",
            "Rayon d'arrivée à l'école",
            "En deçà de cette distance, MS4 considère le bus arrivé et notifie les parents. "
            + "Trop petit, un ping GPS imprécis fait manquer l'arrivée ; trop grand, la notification "
            + "part alors que le bus est encore dans le quartier.", IMMEDIAT),

        // ══ REGROUPEMENT (MS6) ═════════════════════════════════════════════════
        num("ms6.bus_capacity", REGROUPEMENT, "50", 10, 100, "places",
            "Capacité d'un bus",
            "Contrainte dure de l'affectation capacitaire. Le nombre de bus en découle "
            + "(k ≥ ⌈N/capacité⌉), il n'est jamais fixé à la main. ⚠️ La changer redistribue les "
            + "élèves entre bus et invalide la référence du garde-fou qualité.", PROCHAIN_CALCUL),
        num("ms6.rayon_max_m", REGROUPEMENT, "0", 0, 10000, "m",
            "Rayon maximal élève → médoïde",
            "Contrainte dure de compacité : au-delà, l'arc est interdit et l'élève bascule en "
            + "ramassage individuel (groupe 999). 0 désactive la contrainte. Mesuré : R=1500 laisse "
            + "~3 dispersés, R=1000 en laisse ~40. ⚠️ Invalide aussi la référence qualité.", PROCHAIN_CALCUL),
        bool("ms6.use_road_distance", REGROUPEMENT, "true",
             "Distance routière (OSRM)",
             "La distance à vol d'oiseau sous-estime le trajet réel de 1,5 à 1,7×. Mesuré par "
             + "ablation : la matrice routière ne gagne que +0,002 de silhouette, mais −1,7 min de "
             + "temps à bord par enfant (−9,7 %). Désactiver = repli euclidien projeté, plus rapide.",
             PROCHAIN_CALCUL),
        bool("ms6.use_road_for_auto", REGROUPEMENT, "false",
             "Distance routière aussi pour le recalcul automatique",
             "Le recalcul déclenché par RabbitMQ (inscription, déménagement, nouveau bus) utilise "
             + "l'euclidien par défaut, bien plus rapide. Activer si la qualité prime sur la latence.",
             PROCHAIN_CALCUL),
        num("ms6.k_margin", REGROUPEMENT, "3", 0, 10, "bus",
            "Marge d'exploration du nombre de bus",
            "Nombre de bus explorés au-delà du minimum ⌈N/capacité⌉ pour tracer la courbe de Pareto.",
            PROCHAIN_CALCUL),
        bool("ms6.recalcul_auto", REGROUPEMENT, "true",
             "Recalcul automatique sur événement",
             "Coupe le consumer RabbitMQ sans arrêter le service. Utile pendant une campagne "
             + "d'inscriptions : chaque élève ajouté déclenche sinon un recalcul, et un changement "
             + "du nombre de bus déplace des enfants dont rien n'a changé.", IMMEDIAT),
        num("ms6.quality_sil_drop_rel", REGROUPEMENT, "0.15", 0, 1, null,
            "Chute relative de silhouette tolérée",
            "Au-delà de cette baisse relative face à la référence, le verdict passe à DEGRADE.",
            PROCHAIN_CALCUL),
        num("ms6.quality_sil_drop_abs", REGROUPEMENT, "0.05", 0, 1, null,
            "Chute absolue minimale pour déclencher",
            "Garde-fou anti-bruit : une baisse relative n'est retenue que si elle dépasse aussi "
            + "cet écart absolu.", PROCHAIN_CALCUL),
        num("ms6.quality_sil_floor_rel", REGROUPEMENT, "0.75", 0, 1, null,
            "Plancher de silhouette (× l'ancre)",
            "En deçà de plancher × silhouette de conception, le verdict est CRITIQUE. "
            + "Ancre actuelle 0,4256 ⇒ plancher ≈ 0,319.", PROCHAIN_CALCUL),
        num("ms6.quality_comp_inc_rel", REGROUPEMENT, "0.25", 0, 3, null,
            "Hausse relative de compacité max tolérée",
            "Au-delà, le verdict passe à DEGRADE : les groupes se sont étalés.", PROCHAIN_CALCUL),
        num("ms6.quality_disperses_inc", REGROUPEMENT, "15", 0, 300, "élèves",
            "Hausse du nombre de dispersés tolérée",
            "Nombre d'élèves isolés supplémentaires acceptés avant de signaler une dégradation.",
            PROCHAIN_CALCUL),

        // ══ TOURNÉES (MS5) ═════════════════════════════════════════════════════
        num("ms5.vrp_time_limit_s", TOURNEES, "5", 1, 60, "s",
            "Budget de calcul OR-Tools par tournée",
            "Temps laissé à la recherche locale guidée pour chaque bus. Les tournées de la flotte "
            + "sont calculées en parallèle : augmenter ce budget allonge surtout le calcul du bus le "
            + "plus lent, pas la somme.", PROCHAIN_CALCUL),

        // ══ ETA (MS12) ═════════════════════════════════════════════════════════
        num("ms12.eta_alert_min", ETA, "10", 1, 60, "min",
            "Seuil d'alerte « arrivée imminente »",
            "Dès que l'ETA bus → école passe sous ce seuil, MS12 publie l'événement qui déclenche "
            + "la notification aux parents.", IMMEDIAT),
        num("ms12.eta_check_throttle_s", ETA, "20", 5, 300, "s",
            "Fréquence maximale de recalcul par bus",
            "MS12 reçoit un ping GPS toutes les quelques secondes ; sans ce throttle, il "
            + "recalculerait un ETA à chaque ping.", IMMEDIAT),
        num("ms12.eta_alert_cooldown_s", ETA, "1800", 60, 7200, "s",
            "Délai minimal entre deux alertes d'un même bus",
            "Évite de renotifier les mêmes familles en boucle pendant l'approche.", IMMEDIAT),
        enumere("ms12.weather_provider", ETA, "open-meteo", "open-meteo,off",
                "Source météo",
                "open-meteo : API gratuite sans clé. off : repli sur la climatologie saisonnière "
                + "de Meknès.", IMMEDIAT),
        enumere("ms12.traffic_provider", ETA, "heuristic", "heuristic,tomtom",
                "Source trafic",
                "heuristic : niveau déduit de l'heure et du jour. tomtom : nécessite une clé "
                + "(intégration non activée à ce jour, repli heuristique).", IMMEDIAT),
        secret("ms12.tomtom_key", ETA, "Clé API TomTom",
               "Optionnelle. Laisser vide conserve la valeur enregistrée."),

        // ══ CONTEXTE DES PRÉDICTIONS (MS12) ════════════════════════════════════
        enumere("ms12.contexte_mode", CONTEXTE_PRED, "auto", "auto,manuel",
                "Mode d'approvisionnement du contexte",
                "auto : météo depuis Open-Meteo, trafic depuis l'heure, ramadan et souk depuis le "
                + "calendrier. manuel : les valeurs ci-dessous s'imposent. Le champ « sources » de "
                + "la réponse indique alors « manuel (admin) » — la prédiction reste traçable.",
                IMMEDIAT),
        enumere("ms12.meteo_manuelle", CONTEXTE_PRED, "ensoleille",
                "ensoleille,nuageux,pluie,brouillard",
                "Météo imposée",
                "Utilisée uniquement en mode manuel. Catégories identiques à celles vues par le "
                + "modèle à l'entraînement.", IMMEDIAT),
        enumere("ms12.trafic_manuel", CONTEXTE_PRED, "fluide",
                "fluide,modere,dense,embouteillage",
                "Trafic imposé",
                "Utilisé uniquement en mode manuel. L'écart entre « fluide » et « embouteillage » "
                + "combiné à la pluie porte le facteur d'inflation de ×1,32 à ×2,36.", IMMEDIAT),
        enumere("ms12.ramadan_manuel", CONTEXTE_PRED, "auto", "auto,0,1",
                "Ramadan",
                "auto : déduit du calendrier marocain intégré. Forcer permet de couvrir un décalage "
                + "d'observation lunaire.", IMMEDIAT),
        enumere("ms12.jour_souk_manuel", CONTEXTE_PRED, "auto", "auto,0,1",
                "Jour de souk",
                "auto : déduit du calendrier. Forcer permet de tenir compte d'un souk exceptionnel.",
                IMMEDIAT),
        bool("ms12.travaux_prevus", CONTEXTE_PRED, "false",
             "Travaux en cours sur le réseau",
             "Aucune source automatique n'existe pour cette feature : sans déclaration, elle vaut "
             + "toujours 0. L'activer pendant un chantier permet au modèle d'en tenir compte.",
             IMMEDIAT),

        // ══ ANOMALIES (MS11) ═══════════════════════════════════════════════════
        num("ms11.seuil_vitesse_kmh", ANOMALIES, "90", 20, 200, "km/h",
            "Seuil de vitesse anormale",
            "Au-delà, une alerte VITESSE_EXCESSIVE est levée. ⚠️ Les positions sont exprimées en "
            + "km/h par toutes les sources (simulateur et application chauffeur, qui convertit les "
            + "m/s de son GPS).", IMMEDIAT),
        num("ms11.vitesse_pings_consecutifs", ANOMALIES, "1", 1, 10, "pings",
            "Pings consécutifs avant alerte de vitesse",
            "Anti-rebond. À 1 (valeur historique), un seul ping GPS aberrant suffit à lever une "
            + "alerte critique — contrairement à la déviation, qui en exige 2 depuis l'origine. "
            + "Mesuré sur la déviation : passer de 1 à 2 supprime 3,34 fausses alarmes par heure "
            + "pour 5 secondes de détection en plus.", IMMEDIAT),
        num("ms11.seuil_arret_min", ANOMALIES, "5", 1, 120, "min",
            "Durée d'immobilité avant alerte",
            "Un bus immobile plus longtemps déclenche ARRET_PROLONGE.", IMMEDIAT),
        num("ms11.arret_rayon_m", ANOMALIES, "30", 5, 500, "m",
            "Rayon d'immobilité",
            "Déplacement en deçà duquel le bus est considéré à l'arrêt. Doit rester supérieur au "
            + "bruit GPS, sinon un bus garé « bouge » et le compteur ne démarre jamais.", IMMEDIAT),
        num("ms11.seuil_deviation_m", ANOMALIES, "250", 50, 3000, "m",
            "Écart maximal à l'itinéraire planifié",
            "Mesuré le 23/08 sur une tournée réelle de 753 points : à 250 m, un détour n'est "
            + "détecté que sur 9,6 % du parcours — la tournée repasse dans le même quartier, donc "
            + "le bus reste proche d'une autre portion de sa propre polyligne. À 120 m, la "
            + "couverture double sans aucune fausse alarme jusqu'à 30 m de bruit GPS.", PROCHAIN_TRAJET),
        num("ms11.deviation_pings_consecutifs", ANOMALIES, "2", 1, 10, "pings",
            "Pings hors couloir avant alerte de déviation",
            "Anti-rebond de la déviation. 2 est la valeur mesurée optimale.", IMMEDIAT),

        // ══ NOTIFICATIONS (MS4) ════════════════════════════════════════════════
        bool("ms4.notif_arrivee_ecole", NOTIFICATIONS, "true",
             "Notifier l'arrivée à l'école",
             "Envoyée aux parents des élèves du bus quand il entre dans le rayon d'arrivée.", IMMEDIAT),
        bool("ms4.notif_enfant_a_bord", NOTIFICATIONS, "true",
             "Notifier la montée et la dépose",
             "Envoyée au parent concerné lors d'un pointage par le chauffeur.", IMMEDIAT),
        bool("ms4.notif_eta", NOTIFICATIONS, "true",
             "Notifier l'arrivée imminente",
             "« Le bus arrive dans ~N min », déclenchée par le seuil d'alerte ETA.", IMMEDIAT),
        bool("ms4.notif_admin_qualite", NOTIFICATIONS, "true",
             "Alerter l'administration en cas de qualité dégradée",
             "Verdict DEGRADE ou CRITIQUE du garde-fou de regroupement.", IMMEDIAT),
        bool("ms4.notif_admin_anomalie", NOTIFICATIONS, "true",
             "Alerter l'administration en cas d'anomalie",
             "Vitesse excessive, arrêt prolongé, déviation d'itinéraire.", IMMEDIAT),

        // ══ ASSISTANT (MS9) ════════════════════════════════════════════════════
        enumere("ms9.primary_provider", ASSISTANT, "groq", "groq,gemini",
                "Fournisseur principal",
                "Premier étage de la cascade. Les étages suivants prennent le relais sur saturation "
                + "de quota ou erreur serveur.", IMMEDIAT),
        texte("ms9.groq_model", ASSISTANT, "openai/gpt-oss-120b",
              "Modèle Groq principal",
              "Doit savoir appeler des outils, sans quoi l'assistant ne peut rien interroger. "
              + "Vérifié : gpt-oss 120b et 20b émettent bien des appels d'outils ; qwen3.6-27b "
              + "a répondu sans appeler l'outil et a été écarté.", IMMEDIAT),
        texte("ms9.groq_fallback_model", ASSISTANT, "openai/gpt-oss-20b",
              "Modèle Groq de repli",
              "Budget journalier distinct du modèle principal : ce second étage prend le relais "
              + "quand le premier est saturé. Mesuré 88,2 % de réussite contre 100 %, avec une "
              + "faiblesse marquée en darija.", IMMEDIAT),
        texte("ms9.gemini_model", ASSISTANT, "gemini-2.0-flash",
              "Modèle Gemini (dernier étage)",
              "⚠️ La valeur par défaut répond 404 : aucun modèle « 2.0 » n'est plus servi. "
              + "Préférer un alias comme gemini-flash-latest, qui survit par construction aux "
              + "changements de génération. Utiliser le bouton « Tester les modèles » ci-dessous.",
              IMMEDIAT),
        secret("ms9.groq_api_key", ASSISTANT, "Clé API Groq",
               "Laisser vide conserve la clé enregistrée. Jamais renvoyée en clair au navigateur."),
        secret("ms9.gemini_api_key", ASSISTANT, "Clé API Gemini",
               "Laisser vide conserve la clé enregistrée. Jamais renvoyée en clair au navigateur."),
        num("ms9.temperature", ASSISTANT, "0.2", 0, 2, null,
            "Température",
            "Basse pour un agent opérationnel : on veut des réponses reproductibles, pas créatives.",
            IMMEDIAT),
        num("ms9.max_tokens", ASSISTANT, "800", 100, 8000, "jetons",
            "Jetons maximum par réponse",
            "⚠️ Ce budget est partagé avec les jetons de raisonnement des modèles gpt-oss : sur un "
            + "tour à plusieurs outils, la réponse visible peut être tronquée. Monter vers 1200 si "
            + "des réponses se terminent au milieu d'une phrase.", IMMEDIAT),
        num("ms9.max_tool_iters", ASSISTANT, "5", 1, 10, "tours",
            "Tours d'appels d'outils maximum",
            "Plafonne la boucle de l'agent pour éviter qu'il ne s'enferme dans un cycle d'appels.",
            IMMEDIAT),
        num("ms9.history_max_turns", ASSISTANT, "6", 1, 20, "tours",
            "Tours de conversation conservés",
            "Au-delà, les plus anciens sont oubliés pour contenir le coût de chaque requête.",
            IMMEDIAT),
        bool("ms9.school_facts_enabled", ASSISTANT, "true",
             "Injecter le socle de connaissances école",
             "Faits vérifiés (horaires, règlement) placés dans le prompt système. Désactiver permet "
             + "de mesurer l'écart : sans socle, le modèle répond de mémoire, c'est-à-dire qu'il invente.",
             IMMEDIAT),
        num("ms9.sql_max_rows", ASSISTANT, "200", 10, 2000, "lignes",
            "Lignes maximum renvoyées par une requête NL2SQL",
            "Cap appliqué au résultat de l'assistant d'administration.", IMMEDIAT),
        num("ms9.sql_timeout_ms", ASSISTANT, "5000", 500, 60000, "ms",
            "Délai maximal d'une requête NL2SQL",
            "statement_timeout appliqué à la transaction en lecture seule.", IMMEDIAT),

        // ══ INTERFACE (web + mobile) ═══════════════════════════════════════════
        num("ui.poll_trajet_s", INTERFACE, "15", 5, 300, "s",
            "Rafraîchissement du trajet en cours",
            "Utilisé par les espaces parent et chauffeur pour savoir si un trajet est démarré.",
            IMMEDIAT),
        num("ui.poll_eta_s", INTERFACE, "30", 5, 600, "s",
            "Rafraîchissement de l'ETA",
            "Fréquence de recalcul du compte à rebours affiché aux familles.", IMMEDIAT),
        num("ui.poll_inbox_s", INTERFACE, "15", 5, 300, "s",
            "Rafraîchissement de la messagerie", "Réception des messages et diffusions.", IMMEDIAT),
        num("ui.poll_unread_s", INTERFACE, "20", 5, 300, "s",
            "Rafraîchissement du badge non-lus", "Pastille de la barre de navigation.", IMMEDIAT),
        num("ui.poll_liste_s", INTERFACE, "10", 5, 300, "s",
            "Rafraîchissement des listes d'administration",
            "Incidents, notifications, trajets en cours. ⚠️ La passerelle plafonne à 20 requêtes par "
            + "seconde et par adresse : des intervalles très courts multipliés par le nombre "
            + "d'onglets ouverts peuvent déclencher un refus.", IMMEDIAT),
        num("ui.carte_zoom", INTERFACE, "13", 8, 18, null,
            "Zoom initial des cartes", "Niveau de zoom Leaflet à l'ouverture d'une carte.", IMMEDIAT),
        num("ui.page_size", INTERFACE, "25", 10, 200, "lignes",
            "Lignes par page", "Pagination des tableaux d'administration.", IMMEDIAT)
    );
}
