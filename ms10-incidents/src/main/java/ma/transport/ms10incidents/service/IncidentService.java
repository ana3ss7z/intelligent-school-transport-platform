package ma.transport.ms10incidents.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import ma.transport.ms10incidents.dto.IncidentRequest;
import ma.transport.ms10incidents.dto.IncidentResponse;
import ma.transport.ms10incidents.dto.StatutRequest;
import ma.transport.ms10incidents.entity.Incident;
import ma.transport.ms10incidents.entity.Incident.StatutIncident;
import ma.transport.ms10incidents.repository.IncidentRepository;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

@Slf4j
@Service
@RequiredArgsConstructor
public class IncidentService {

    private final IncidentRepository repo;
    private final RabbitTemplate     rabbitTemplate;
    private final ObjectMapper       objectMapper;

    // ─── Créer ───────────────────────────────────────────────────────────────

    public IncidentResponse creer(IncidentRequest req, Long signalePar) {
        Incident incident = Incident.builder()
                .type(req.getType())
                .busId(req.getBusId())
                .description(req.getDescription())
                .latitude(req.getLatitude())
                .longitude(req.getLongitude())
                .signalePar(signalePar)
                .statut(StatutIncident.SIGNALE)
                .dateSignalement(LocalDateTime.now())
                .build();

        Incident saved = repo.save(incident);
        log.info("[MS10] Incident créé — id={} type={} bus={}", saved.getId(), saved.getType(), saved.getBusId());

        // Publier événement RabbitMQ → MS4 peut notifier l'admin
        publierEvenement("incident.signale", saved);

        return IncidentResponse.from(saved);
    }

    // ─── Lire ────────────────────────────────────────────────────────────────

    public List<IncidentResponse> getTous() {
        return repo.findAllByOrderByDateSignalementDesc()
                .stream().map(IncidentResponse::from).toList();
    }

    public IncidentResponse getById(Long id) {
        return IncidentResponse.from(findOrThrow(id));
    }

    public List<IncidentResponse> getParBus(Long busId) {
        return repo.findByBusIdOrderByDateSignalementDesc(busId)
                .stream().map(IncidentResponse::from).toList();
    }

    public List<IncidentResponse> getParStatut(StatutIncident statut) {
        return repo.findByStatutOrderByDateSignalementDesc(statut)
                .stream().map(IncidentResponse::from).toList();
    }

    // ─── Changer statut ──────────────────────────────────────────────────────

    public IncidentResponse changerStatut(Long id, StatutRequest req) {
        Incident incident = findOrThrow(id);
        StatutIncident ancienStatut = incident.getStatut();
        incident.setStatut(req.getStatut());

        // Si résolu : enregistrer date + notes
        if (req.getStatut() == StatutIncident.RESOLU) {
            incident.setDateResolution(LocalDateTime.now());
            if (req.getNotesResolution() != null) {
                incident.setNotesResolution(req.getNotesResolution());
            }
        }

        Incident saved = repo.save(incident);
        log.info("[MS10] Statut incident {} : {} → {}", id, ancienStatut, req.getStatut());

        // Publier événement RabbitMQ si résolu → MS4 notifie les parents
        if (req.getStatut() == StatutIncident.RESOLU) {
            publierEvenement("incident.resolu", saved);
        }

        return IncidentResponse.from(saved);
    }

    // ─── Supprimer ───────────────────────────────────────────────────────────

    public void supprimer(Long id) {
        Incident incident = findOrThrow(id);
        repo.delete(incident);
        log.info("[MS10] Incident {} supprimé", id);
    }

    // ─── Stats ───────────────────────────────────────────────────────────────

    public Map<String, Long> getStats() {
        return Map.of(
            "total",         repo.count(),
            "signale",       repo.countByStatut(StatutIncident.SIGNALE),
            "confirme",      repo.countByStatut(StatutIncident.CONFIRME),
            "en_traitement", repo.countByStatut(StatutIncident.EN_TRAITEMENT),
            "resolu",        repo.countByStatut(StatutIncident.RESOLU)
        );
    }

    // ─── Helpers ─────────────────────────────────────────────────────────────

    private Incident findOrThrow(Long id) {
        return repo.findById(id)
                .orElseThrow(() -> new RuntimeException("Incident non trouvé : " + id));
    }

    private void publierEvenement(String routingKey, Incident incident) {
        try {
            String json = objectMapper.writeValueAsString(Map.of(
                "incidentId",      incident.getId(),
                "type",            incident.getType().name(),
                "statut",          incident.getStatut().name(),
                "busId",           incident.getBusId(),
                "description",     incident.getDescription(),
                "dateSignalement", incident.getDateSignalement().toString()
            ));
            rabbitTemplate.convertAndSend("transport.exchange", routingKey, json);
            log.debug("[MS10] Événement publié : {}", routingKey);
        } catch (Exception e) {
            log.warn("[MS10] RabbitMQ échoué : {}", e.getMessage());
        }
    }
}
