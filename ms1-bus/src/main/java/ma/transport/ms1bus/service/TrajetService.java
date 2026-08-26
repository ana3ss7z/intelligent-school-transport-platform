package ma.transport.ms1bus.service;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.stereotype.Service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import ma.transport.ms1bus.config.RabbitMQConfig;
import ma.transport.ms1bus.dto.TrajetRequest;
import ma.transport.ms1bus.dto.TrajetResponse;
import ma.transport.ms1bus.dto.TrajetRouteResponse;
import ma.transport.ms1bus.entity.Bus;
import ma.transport.ms1bus.entity.Trajet;
import ma.transport.ms1bus.entity.Trajet.StatutTrajet;
import ma.transport.ms1bus.repository.BusRepository;
import ma.transport.ms1bus.repository.TrajetRepository;
import ma.transport.mscommon.enums.Role;

@Slf4j
@Service
@RequiredArgsConstructor
public class TrajetService {

    private final TrajetRepository repo;
    private final BusRepository busRepo;
    private final RabbitTemplate rabbitTemplate;
    private final ObjectMapper objectMapper;

    /** Démarre un trajet pour le chauffeur authentifié. */
    public TrajetResponse demarrer(Long chauffeurId, TrajetRequest req) {
        repo.findFirstByBusIdAndStatut(req.getBusId(), StatutTrajet.EN_COURS).ifPresent(t -> {
            throw new IllegalStateException("Un trajet est déjà en cours pour ce bus (id=" + t.getId() + ").");
        });
        // Géométrie de la tournée (référence de déviation MS11), sérialisée en JSON si fournie
        String geoJson = null;
        if (req.getGeometrie() != null && !req.getGeometrie().isEmpty()) {
            try {
                geoJson = objectMapper.writeValueAsString(req.getGeometrie());
            } catch (Exception e) {
                log.warn("[MS1] Géométrie de tournée non sérialisable : {}", e.getMessage());
            }
        }
        Trajet t = repo.save(Trajet.builder()
                .busId(req.getBusId())
                .chauffeurId(chauffeurId)
                .groupeId(req.getGroupeId())
                .geometrie(geoJson)
                .distancePlanM(req.getDistancePlanM())
                .dureePlanMin(req.getDureePlanMin())
                .sens(req.getSens())
                .statut(StatutTrajet.EN_COURS)
                .heureDebut(LocalDateTime.now())
                .build());
        publier("trajet.demarre", t);
        log.info("[MS1] Trajet démarré id={} bus={} chauffeur={} sens={}", t.getId(), t.getBusId(), chauffeurId, t.getSens());
        return toResponse(t);
    }

    /**
     * Termine un trajet.
     *
     * <p>Le chauffeur ne peut clore que le sien. <b>L'administration, elle, peut clore
     * n'importe lequel</b> : le controleur l'autorisait deja par {@code @PreAuthorize}, mais ce
     * controle de propriete la rejetait ensuite en 400 — une autorisation creuse. Comme le
     * demarrage n'est pas idempotent, un trajet reste EN_COURS (telephone hors service,
     * chauffeur parti) bloquait le bus <b>definitivement, sans aucun recours par l'API</b>.
     * Rencontre pour de vrai pendant la recette du 26/08 (defaut C1).
     */
    public TrajetResponse terminer(Long id, Long userId, Role role) {
        Trajet t = repo.findById(id).orElseThrow(() -> new RuntimeException("Trajet introuvable : " + id));
        if (role != Role.ADMIN && !t.getChauffeurId().equals(userId)) {
            throw new IllegalStateException("Ce trajet n'appartient pas à ce chauffeur.");
        }
        t.setStatut(StatutTrajet.TERMINE);
        t.setHeureFin(LocalDateTime.now());
        repo.save(t);
        publier("trajet.termine", t);
        log.info("[MS1] Trajet terminé id={}", id);
        return toResponse(t);
    }

    public List<TrajetResponse> actifs() {
        return repo.findByStatutOrderByHeureDebutDesc(StatutTrajet.EN_COURS)
                .stream().map(this::toResponse).toList();
    }

    public TrajetResponse monActif(Long chauffeurId) {
        return repo.findFirstByChauffeurIdAndStatut(chauffeurId, StatutTrajet.EN_COURS)
                .map(this::toResponse).orElse(null);
    }

    /** Trajet EN_COURS d'un bus (pour le suivi parent : compte à rebours ETA selon le sens). */
    public TrajetResponse actifParBus(Long busId) {
        return repo.findFirstByBusIdAndStatut(busId, StatutTrajet.EN_COURS)
                .map(this::toResponse).orElse(null);
    }

    /**
     * Tournée figée du trajet EN_COURS d'un bus (polyligne + totaux OSRM), pour l'ETA
     * « distance restante le long du circuit ». null si aucun trajet en cours.
     */
    public TrajetRouteResponse routeParBus(Long busId) {
        return repo.findFirstByBusIdAndStatut(busId, StatutTrajet.EN_COURS)
                .map(t -> TrajetRouteResponse.builder()
                        .trajetId(t.getId()).busId(t.getBusId()).groupeId(t.getGroupeId())
                        .sens(t.getSens())
                        .geometrie(parseGeometrie(t.getGeometrie()))
                        .distancePlanM(t.getDistancePlanM()).dureePlanMin(t.getDureePlanMin())
                        .build())
                .orElse(null);
    }

    /** Historique des trajets terminés du chauffeur (les plus récents d'abord). */
    public List<TrajetResponse> mesTrajets(Long chauffeurId) {
        return repo.findByChauffeurIdAndStatutOrderByHeureDebutDesc(chauffeurId, StatutTrajet.TERMINE)
                .stream().map(this::toResponse).toList();
    }

    // ── Helpers ──────────────────────────────────────────────────────

    /** Relit la polyligne stockée en JSON ; liste vide si absente ou illisible. */
    private List<List<Double>> parseGeometrie(String json) {
        if (json == null || json.isBlank()) return List.of();
        try {
            return objectMapper.readValue(json, new TypeReference<List<List<Double>>>() {});
        } catch (Exception e) {
            log.warn("[MS1] Géométrie de tournée illisible : {}", e.getMessage());
            return List.of();
        }
    }

    private String matricule(Long busId) {
        return busRepo.findById(busId).map(Bus::getMatricule).orElse("?");
    }

    private void publier(String routingKey, Trajet t) {
        try {
            Map<String, Object> payload = new HashMap<>();
            payload.put("trajetId", t.getId());
            payload.put("busId", t.getBusId());
            payload.put("matricule", matricule(t.getBusId()));
            payload.put("chauffeurId", t.getChauffeurId());
            payload.put("sens", t.getSens().name());
            payload.put("statut", t.getStatut().name());
            payload.put("groupeId", t.getGroupeId());
            // geometrie : chaîne JSON déjà sérialisée (référence de déviation MS11), null si absente
            payload.put("geometrie", t.getGeometrie());
            String json = objectMapper.writeValueAsString(payload);
            rabbitTemplate.convertAndSend(RabbitMQConfig.EXCHANGE, routingKey, json);
            log.info("[MS1] Événement publié : {} (trajet={})", routingKey, t.getId());
        } catch (Exception e) {
            log.warn("[MS1] Publication RabbitMQ échouée ({}) : {}", routingKey, e.getMessage());
        }
    }

    private TrajetResponse toResponse(Trajet t) {
        return TrajetResponse.builder()
                .id(t.getId()).busId(t.getBusId()).matricule(matricule(t.getBusId()))
                .chauffeurId(t.getChauffeurId()).groupeId(t.getGroupeId())
                .sens(t.getSens()).statut(t.getStatut())
                .heureDebut(t.getHeureDebut()).heureFin(t.getHeureFin())
                .build();
    }
}
