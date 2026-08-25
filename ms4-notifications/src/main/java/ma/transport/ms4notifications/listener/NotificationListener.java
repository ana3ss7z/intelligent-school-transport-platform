package ma.transport.ms4notifications.listener;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import ma.transport.ms4notifications.entity.Notification.TypeNotification;
import ma.transport.ms4notifications.service.BusLookupService;
import ma.transport.ms4notifications.service.FcmService;
import ma.transport.ms4notifications.service.ParametresCache;
import ma.transport.ms4notifications.service.ParentLookupService;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.time.LocalDateTime;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * RabbitMQ Listeners — MS4 écoute 3 événements :
 *
 * 1. incident.signale   → notifie l'admin + parents du bus concerné
 * 2. incident.resolu    → notifie les parents que le bus repart
 * 3. gps.bus.updated    → détecte arrivée à l'école et notifie les parents
 * 4. eta.bus.arriving   → ETA temps réel (MS12) : « le bus arrive dans ~10 min » (UC-4)
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class NotificationListener {

    private final FcmService          fcmService;
    private final ParentLookupService parentLookup;
    private final BusLookupService    busLookup;
    private final ObjectMapper        objectMapper;

    /**
     * Coordonnées de l'école et interrupteurs de notification, servis par MS13.
     *
     * <p>Remplace trois constantes compilées ({@code ECOLE_LAT = 33.8850},
     * {@code ECOLE_LNG = -5.5480}, {@code RAYON_METRES = 150}). Les deux premières
     * <b>divergeaient de ~900 m</b> de la valeur utilisée par tous les autres services
     * ({@code 33.893 / -5.5455}) : la notification « bus arrivé à l'école » se déclenchait sur
     * un point qui n'était pas la destination des tournées.
     */
    private final ParametresCache parametres;

    // ─── Verrou d'arrivée à l'école ──────────────────────────────────────────

    /**
     * État d'un bus vis-à-vis du rayon de l'école.
     *
     * <p>{@code dansZone} est un <b>verrou</b> : il est posé au franchissement du rayon et n'est
     * levé que lorsque le bus s'en est franchement éloigné. Sans lui, {@code onGpsBusUpdated}
     * notifiait <b>à chaque ping</b> passé dans le rayon — mesuré en production sur l'export du
     * 24/08 : <b>150 notifications identiques par parent, espacées de 1,2 s</b>, avec un pic à
     * 1110 notifications pour un seul bus en une minute, parce qu'un bus stationné à l'école
     * continue d'émettre sa position. Ces envois échouaient tous faute de device FCM enregistré,
     * ce qui <b>masquait le défaut</b> : le jour où le canal push est raccordé, chaque famille
     * reçoit 150 alertes en trois minutes.
     */
    private static final class EtatArrivee {
        boolean dansZone;
        LocalDateTime derniereNotif;
    }

    /**
     * Marge d'hystérésis pour lever le verrou. Le bus doit s'éloigner à {@code rayon × 1.5}
     * (225 m pour le rayon par défaut de 150 m) avant qu'une nouvelle arrivée puisse être
     * annoncée. Une simple sortie du rayon suffirait à réarmer le verrou sur du bruit GPS
     * (±10 à 30 m), ce qui ferait clignoter l'alerte pour un bus immobile posé sur la frontière.
     */
    private static final double MARGE_SORTIE = 1.5;

    /** Borné par la taille de la flotte (une dizaine d'entrées) — pas de purge nécessaire. */
    private final Map<Long, EtatArrivee> etatsArrivee = new ConcurrentHashMap<>();

    // ─── 1. Incident signalé ─────────────────────────────────────────────────

    @RabbitListener(queues = "ms4.incident.signale.queue")
    public void onIncidentSignale(String message) {
        log.info("[MS4] 📨 incident.signale reçu");
        try {
            JsonNode node   = objectMapper.readTree(message);
            Long busId      = node.get("busId").asLong();
            String type     = node.get("type").asText();
            String desc     = node.get("description").asText();
            Long incidentId = node.get("incidentId").asLong();

            String titre  = "⚠️ Incident sur le bus de votre enfant";
            String corps  = String.format("Incident %s signalé : %s", type, desc);

            // Notifier tous les parents dont l'enfant est sur ce bus
            parentLookup.getParentsParBus(busId).forEach(parentId ->
                fcmService.envoyerAuParent(parentId, TypeNotification.INCIDENT_SIGNALE,
                                           titre, corps, incidentId, "INCIDENT")
            );

        } catch (Exception e) {
            log.error("[MS4] Erreur traitement incident.signale : {}", e.getMessage());
        }
    }

    // ─── 2. Incident résolu ───────────────────────────────────────────────────

    @RabbitListener(queues = "ms4.incident.resolu.queue")
    public void onIncidentResolu(String message) {
        log.info("[MS4] 📨 incident.resolu reçu");
        try {
            JsonNode node   = objectMapper.readTree(message);
            Long busId      = node.get("busId").asLong();
            Long incidentId = node.get("incidentId").asLong();

            String titre = "✅ Incident résolu — bus en route";
            String corps = "L'incident sur le bus de votre enfant est résolu. Le trajet a repris.";

            parentLookup.getParentsParBus(busId).forEach(parentId ->
                fcmService.envoyerAuParent(parentId, TypeNotification.INCIDENT_RESOLU,
                                           titre, corps, incidentId, "INCIDENT")
            );

            // Notifier aussi le chauffeur du bus (il peut reprendre)
            Long chauffeurId = busLookup.getChauffeurParBus(busId);
            if (chauffeurId != null) {
                fcmService.envoyerAuParent(chauffeurId, TypeNotification.INCIDENT_RESOLU,
                        "✅ Incident résolu — bus en route",
                        "L'incident sur votre bus est résolu, vous pouvez reprendre.",
                        incidentId, "CHAUFFEUR");
            }

        } catch (Exception e) {
            log.error("[MS4] Erreur traitement incident.resolu : {}", e.getMessage());
        }
    }

    // ─── 3. Position GPS bus — détection arrivée école ───────────────────────

    @RabbitListener(queues = "ms4.gps.bus.updated.queue")
    public void onGpsBusUpdated(String message) {
        if (!parametres.notifArriveeEcole()) return;
        try {
            JsonNode node = objectMapper.readTree(message);
            Long busId    = node.get("cibleId").asLong();
            double lat    = node.get("latitude").asDouble();
            double lng    = node.get("longitude").asDouble();

            // Coordonnées relues à chaque ping : un changement dans la console d'administration
            // s'applique au ping suivant, sans redémarrage de MS4.
            double rayon    = parametres.rayonArriveeM();
            double distance = calculerDistance(lat, lng, parametres.ecoleLat(), parametres.ecoleLng());

            if (!doitAnnoncerArrivee(busId, distance, rayon)) return;

            log.info("[MS4] 🏫 Bus {} arrivé à l'école (distance: {}m)", busId, (int)distance);

            String titre = "🏫 Le bus est arrivé à l'école";
            String corps = String.format("Le bus de votre enfant est arrivé à l'école (distance: %dm).", (int)distance);

            parentLookup.getParentsParBus(busId).forEach(parentId ->
                fcmService.envoyerAuParent(parentId, TypeNotification.BUS_ARRIVE_ECOLE,
                                           titre, corps, busId, "BUS")
            );

        } catch (Exception e) {
            log.error("[MS4] Erreur traitement gps.bus.updated : {}", e.getMessage());
        }
    }

    // ─── 4. ETA temps réel — bus proche de l'école (UC-4) ────────────────────

    @RabbitListener(queues = "ms4.eta.arriving.queue")
    public void onEtaArriving(String message) {
        if (!parametres.notifEta()) return;
        log.info("[MS4] 📨 eta.bus.arriving reçu");
        try {
            JsonNode node  = objectMapper.readTree(message);
            Long busId     = node.get("busId").asLong();
            double etaMin  = node.get("eta_min").asDouble();
            String heure   = node.hasNonNull("heure_arrivee_estimee")
                    ? node.get("heure_arrivee_estimee").asText() : "";

            String titre = "🚌 Le bus arrive bientôt";
            String corps = heure.isEmpty()
                    ? String.format("Le bus de votre enfant arrivera à l'école dans ~%d min.", Math.round(etaMin))
                    : String.format("Le bus de votre enfant arrivera à l'école dans ~%d min (vers %s).",
                                     Math.round(etaMin), heure);

            parentLookup.getParentsParBus(busId).forEach(parentId ->
                fcmService.envoyerAuParent(parentId, TypeNotification.BUS_EN_ROUTE,
                                           titre, corps, busId, "BUS")
            );

        } catch (Exception e) {
            log.error("[MS4] Erreur traitement eta.bus.arriving : {}", e.getMessage());
        }
    }

    // ─── 5. Présence confirmée — « enfant à bord » (G5, UC-4) ────────────────

    @RabbitListener(queues = "ms4.eleve.presence.queue")
    public void onElevePresence(String message) {
        if (!parametres.notifEnfantABord()) return;
        log.info("[MS4] 📨 eleve.presence.updated reçu");
        try {
            JsonNode node   = objectMapper.readTree(message);
            Long eleveId    = node.get("eleveId").asLong();
            Long parentId   = node.hasNonNull("parentId") ? node.get("parentId").asLong() : null;
            String nom      = node.hasNonNull("nom") ? node.get("nom").asText() : "Votre enfant";
            boolean present = node.path("present").asBoolean(true);
            if (parentId == null) return;

            String titre; String corps; TypeNotification type;
            if (present) {   // montée (matin)
                titre = "🎒 Enfant à bord";
                corps = String.format("%s est bien monté dans le bus.", nom);
                type = TypeNotification.ENFANT_A_BORD;
            } else {         // dépose (soir)
                titre = "🏡 Enfant déposé";
                corps = String.format("%s a été déposé à son arrêt.", nom);
                type = TypeNotification.ENFANT_DEPOSE;
            }
            fcmService.envoyerAuParent(parentId, type, titre, corps, eleveId, "ELEVE");

        } catch (Exception e) {
            log.error("[MS4] Erreur traitement eleve.presence.updated : {}", e.getMessage());
        }
    }

    // ─── 6. Canal admin (D1) — alerte qualité clustering (MS6) ───────────────

    @RabbitListener(queues = "ms4.quality.queue")
    public void onQualiteDegradee(String message) {
        if (!parametres.notifAdminQualite()) return;
        log.info("[MS4] 📨 clustering.quality.low reçu");
        try {
            JsonNode node = objectMapper.readTree(message);
            String niveau = node.path("niveau").asText("DEGRADE");
            String raisons = node.path("raisons").toString();
            String titre = "⚠️ Qualité de clustering " + niveau;
            String corps = String.format("Clustering %s (silhouette=%s, k=%s). Raisons : %s",
                    niveau, node.path("silhouette").asText("?"), node.path("k").asText("?"), raisons);
            // Notif admin historisée (parentId null = destinataire ADMIN, vu via GET /api/notifications)
            fcmService.envoyerAuParent(null, TypeNotification.ALERTE_QUALITE, titre, corps, null, "ADMIN");
        } catch (Exception e) {
            log.error("[MS4] Erreur traitement clustering.quality.low : {}", e.getMessage());
        }
    }

    // ─── 7. Canal admin (D1) — anomalie GPS live (MS11) ──────────────────────

    @RabbitListener(queues = "ms4.anomalie.queue")
    public void onAnomalieDetectee(String message) {
        if (!parametres.notifAdminAnomalie()) return;
        log.info("[MS4] 📨 anomalie.detectee reçu");
        try {
            JsonNode node = objectMapper.readTree(message);
            Long busId  = node.hasNonNull("busId") ? node.get("busId").asLong() : null;
            String type = node.path("type").asText("ANOMALIE");
            String titre = "🚨 Anomalie détectée — bus " + (busId != null ? busId : "?");
            String corps = String.format("Anomalie %s détectée sur le bus %s.", type, busId);
            fcmService.envoyerAuParent(null, TypeNotification.ANOMALIE_DETECTEE, titre, corps, busId, "ADMIN");
        } catch (Exception e) {
            log.error("[MS4] Erreur traitement anomalie.detectee : {}", e.getMessage());
        }
    }

    // ─── 8. Canal admin — trajets démarrés/terminés par les chauffeurs (MS1) ──

    @RabbitListener(queues = "ms4.trajet.queue")
    public void onTrajet(String message) {
        log.info("[MS4] 📨 trajet.* reçu");
        try {
            JsonNode node = objectMapper.readTree(message);
            String statut = node.path("statut").asText("EN_COURS");
            String sens = node.path("sens").asText("");
            Long busId = node.hasNonNull("busId") ? node.get("busId").asLong() : null;
            String matricule = node.path("matricule").asText("?");
            Long chauffeurId = node.hasNonNull("chauffeurId") ? node.get("chauffeurId").asLong() : null;
            boolean demarre = "EN_COURS".equals(statut);
            String titre = demarre ? "🚌 Trajet démarré" : "🏁 Trajet terminé";
            String corps = String.format("Trajet %s %s — chauffeur #%s, bus %s.",
                    sens.toLowerCase(), demarre ? "démarré" : "terminé", chauffeurId, matricule);
            TypeNotification type = demarre ? TypeNotification.TRAJET_DEMARRE : TypeNotification.TRAJET_TERMINE;
            fcmService.envoyerAuParent(null, type, titre, corps, busId, "ADMIN");

            // La tournée part de l'école et y revient : au démarrage, le bus est DANS le rayon
            // d'arrivée. On pose donc le verrou sans notifier, sinon le premier ping du trajet
            // annoncerait une « arrivée » au moment même du départ — le cas se produit à chaque
            // redémarrage de MS4, qui perd les verrous en mémoire.
            if (demarre && busId != null) {
                etatsArrivee.compute(busId, (id, etat) -> {
                    EtatArrivee e = etat != null ? etat : new EtatArrivee();
                    synchronized (e) { e.dansZone = true; }
                    return e;
                });
            }
        } catch (Exception e) {
            log.error("[MS4] Erreur traitement trajet.* : {}", e.getMessage());
        }
    }

    /**
     * Décide si l'arrivée doit être annoncée pour ce ping — une fois par arrivée réelle.
     *
     * <p>Trois filtres successifs, du plus structurant au plus défensif :
     * <ol>
     *   <li><b>hors du rayon</b> — rien à annoncer ; le verrou se lève si le bus a dépassé la
     *       marge d'hystérésis, ce qui autorise la prochaine arrivée (retour du soir) ;</li>
     *   <li><b>verrou déjà posé</b> — le bus était déjà dans le rayon au ping précédent :
     *       l'arrivée a été annoncée, il n'y a pas de nouvelle arrivée ;</li>
     *   <li><b>délai minimal</b> — filet configurable, pour un bus qui ferait des allers-retours
     *       autour de la frontière malgré la marge.</li>
     * </ol>
     *
     * <p>Le verrou est posé dans tous les cas où le bus est dans le rayon, y compris quand le
     * délai minimal a supprimé l'annonce : sans cela, le prochain ping serait à nouveau traité
     * comme une entrée et le filet serait consulté à chaque ping plutôt qu'à chaque arrivée.
     */
    private boolean doitAnnoncerArrivee(Long busId, double distance, double rayon) {
        EtatArrivee etat = etatsArrivee.computeIfAbsent(busId, id -> new EtatArrivee());

        synchronized (etat) {
            if (distance > rayon) {
                if (distance > rayon * MARGE_SORTIE) etat.dansZone = false;
                return false;
            }
            if (etat.dansZone) return false;

            etat.dansZone = true;

            long cooldown = parametres.arriveeEcoleCooldownMin();
            if (cooldown > 0 && etat.derniereNotif != null
                    && Duration.between(etat.derniereNotif, LocalDateTime.now()).toMinutes() < cooldown) {
                log.debug("[MS4] Arrivée du bus {} ignorée — annoncée il y a moins de {} min", busId, cooldown);
                return false;
            }

            etat.derniereNotif = LocalDateTime.now();
            return true;
        }
    }

    // ─── Helper distance Haversine ────────────────────────────────────────────

    private double calculerDistance(double lat1, double lng1,
                                     double lat2, double lng2) {
        final int R = 6371000; // rayon Terre en mètres
        double dLat = Math.toRadians(lat2 - lat1);
        double dLng = Math.toRadians(lng2 - lng1);
        double a = Math.sin(dLat / 2) * Math.sin(dLat / 2)
                 + Math.cos(Math.toRadians(lat1)) * Math.cos(Math.toRadians(lat2))
                 * Math.sin(dLng / 2) * Math.sin(dLng / 2);
        return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    }
}
