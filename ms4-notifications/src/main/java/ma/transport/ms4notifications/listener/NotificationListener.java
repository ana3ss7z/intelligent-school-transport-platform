package ma.transport.ms4notifications.listener;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import ma.transport.ms4notifications.entity.Notification.TypeNotification;
import ma.transport.ms4notifications.service.FcmService;
import ma.transport.ms4notifications.service.ParentLookupService;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.stereotype.Component;

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
    private final ObjectMapper        objectMapper;

    // Coordonnées de l'école (à adapter selon le projet)
    private static final double ECOLE_LAT  = 33.8850;
    private static final double ECOLE_LNG  = -5.5480;
    private static final double RAYON_METRES = 150.0; // 150m de l'école

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

        } catch (Exception e) {
            log.error("[MS4] Erreur traitement incident.resolu : {}", e.getMessage());
        }
    }

    // ─── 3. Position GPS bus — détection arrivée école ───────────────────────

    @RabbitListener(queues = "ms4.gps.bus.updated.queue")
    public void onGpsBusUpdated(String message) {
        try {
            JsonNode node = objectMapper.readTree(message);
            Long busId    = node.get("cibleId").asLong();
            double lat    = node.get("latitude").asDouble();
            double lng    = node.get("longitude").asDouble();

            // Vérifier si le bus est proche de l'école
            double distance = calculerDistance(lat, lng, ECOLE_LAT, ECOLE_LNG);

            if (distance <= RAYON_METRES) {
                log.info("[MS4] 🏫 Bus {} arrivé à l'école (distance: {}m)", busId, (int)distance);

                String titre = "🏫 Le bus est arrivé à l'école";
                String corps = String.format("Le bus de votre enfant est arrivé à l'école (distance: %dm).", (int)distance);

                parentLookup.getParentsParBus(busId).forEach(parentId ->
                    fcmService.envoyerAuParent(parentId, TypeNotification.BUS_ARRIVE_ECOLE,
                                               titre, corps, busId, "BUS")
                );
            }

        } catch (Exception e) {
            log.error("[MS4] Erreur traitement gps.bus.updated : {}", e.getMessage());
        }
    }

    // ─── 4. ETA temps réel — bus proche de l'école (UC-4) ────────────────────

    @RabbitListener(queues = "ms4.eta.arriving.queue")
    public void onEtaArriving(String message) {
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
