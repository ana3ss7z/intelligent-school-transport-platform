package ma.transport.ms2eleves.service;

import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.stereotype.Service;

import com.fasterxml.jackson.databind.ObjectMapper;

import jakarta.transaction.Transactional;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import ma.transport.ms2eleves.dto.EleveRequest;
import ma.transport.ms2eleves.dto.EleveResponse;
import ma.transport.ms2eleves.entity.Eleve;
import ma.transport.ms2eleves.repository.EleveRepository;

@Slf4j
@Service
@RequiredArgsConstructor
public class EleveService {

    private final EleveRepository repo;
    private final RabbitTemplate rabbitTemplate;
    private final ObjectMapper objectMapper;

    // ── Créer un élève ───────────────────────────────────────────────
    public EleveResponse creer(EleveRequest req) {
        Eleve eleve = Eleve.builder()
                .nom(req.getNom())
                .prenom(req.getPrenom())
                .latitude(req.getLatitude())
                .longitude(req.getLongitude())
                .parentId(req.getParentId())
                .busId(req.getBusId())
                .groupeId(req.getGroupeId())
                .build();

        Eleve saved = repo.save(eleve);

        rabbitTemplate.convertAndSend("transport.exchange", "eleve.created", "eleveId:" + saved.getId());
        log.info("[MS2] Élève créé — id={} nom={} {}", saved.getId(), saved.getNom(), saved.getPrenom());

        return toResponse(saved);
    }

    // ── Lister tous les élèves ───────────────────────────────────────
    public List<EleveResponse> listerTous() {
        return repo.findAll().stream()
                .map(this::toResponse)
                .collect(Collectors.toList());
    }

    // ── Élèves d'un parent ───────────────────────────────────────────
    public List<EleveResponse> parParent(Long parentId) {
        return repo.findByParentId(parentId).stream()
                .map(this::toResponse)
                .collect(Collectors.toList());
    }

    // ── Élèves d'un groupe ───────────────────────────────────────────
    public List<EleveResponse> parGroupe(Long groupeId) {
        return repo.findByGroupeId(groupeId).stream()
                .map(this::toResponse)
                .collect(Collectors.toList());
    }

    // ── Élèves sans groupe (point de départ clustering MS6) ──────────
    public List<EleveResponse> sanGroupe() {
        return repo.findByGroupeIdIsNull().stream()
                .map(this::toResponse)
                .collect(Collectors.toList());
    }

    // ── Obtenir un élève ─────────────────────────────────────────────
    public EleveResponse getById(Long id) {
        return toResponse(repo.findById(id)
                .orElseThrow(() -> new RuntimeException("Élève non trouvé : " + id)));
    }

    /**
     * Route INTERNE — appelée par MS4 (sans JWT) pour récupérer les parents
     * des élèves d'un bus, afin d'envoyer des notifications FCM.
     */
    public List<Long> getParentIdsParBus(Long busId) {
        return repo.findByBusId(busId).stream()
                .map(Eleve::getParentId)
                .filter(java.util.Objects::nonNull)
                .distinct()
                .collect(Collectors.toList());
    }

    // ── Modifier un élève (PUT complet) ──────────────────────────────
    public EleveResponse modifier(Long id, EleveRequest req) {
        Eleve eleve = repo.findById(id)
                .orElseThrow(() -> new RuntimeException("Élève non trouvé : " + id));

        boolean gpsModifie =
            !eleve.getLatitude().equals(req.getLatitude()) ||
            !eleve.getLongitude().equals(req.getLongitude());

        eleve.setNom(req.getNom());
        eleve.setPrenom(req.getPrenom());
        eleve.setLatitude(req.getLatitude());
        eleve.setLongitude(req.getLongitude());
        eleve.setParentId(req.getParentId());

        // Mise à jour optionnelle de busId / groupeId si fournis dans la requête
        if (req.getBusId() != null)    eleve.setBusId(req.getBusId());
        if (req.getGroupeId() != null) eleve.setGroupeId(req.getGroupeId());

        Eleve saved = repo.save(eleve);

        if (gpsModifie) {
            rabbitTemplate.convertAndSend("transport.exchange", "eleve.gps.updated", "eleveId:" + saved.getId());
        }

        return toResponse(saved);
    }

    /**
     * Assigner un bus à un élève — appelé via PATCH /api/eleves/{id}/bus
     * Utilisé après le clustering MS6 ou par l'admin directement.
     */
    public EleveResponse assignerBus(Long id, Long busId) {
        Eleve eleve = repo.findById(id)
                .orElseThrow(() -> new RuntimeException("Élève non trouvé : " + id));

        eleve.setBusId(busId);
        Eleve saved = repo.save(eleve);
        log.info("[MS2] Bus assigné — élève={} bus={}", id, busId);

        return toResponse(saved);
    }

    /**
     * Assigner un groupe à un élève — appelé via PATCH /api/eleves/{id}/groupe
     * Appelé par MS6 ClusteringService après K-Means / DBSCAN.
     * Route interne : pas de JWT requis (voir SecurityConfig).
     */
    public EleveResponse assignerGroupe(Long id, Long groupeId) {
        Eleve eleve = repo.findById(id)
                .orElseThrow(() -> new RuntimeException("Élève non trouvé : " + id));

        eleve.setGroupeId(groupeId);
        Eleve saved = repo.save(eleve);
        log.info("[MS2] Groupe assigné — élève={} groupe={}", id, groupeId);

        return toResponse(saved);
    }

    // ── Mettre à jour présence ───────────────────────────────────────
    public void mettreAJourPresence(Long id, Boolean present) {
        Eleve eleve = repo.findById(id)
                .orElseThrow(() -> new RuntimeException("Élève non trouvé : " + id));
        eleve.setStatutPresence(present);
        repo.save(eleve);

        // Montée confirmée → notifier le parent (« enfant à bord »). MS4 consomme eleve.presence.updated.
        if (Boolean.TRUE.equals(present) && eleve.getParentId() != null) {
            try {
                Map<String, Object> payload = new java.util.HashMap<>();
                payload.put("eleveId", eleve.getId());
                payload.put("parentId", eleve.getParentId());
                payload.put("busId", eleve.getBusId());
                payload.put("nom", eleve.getPrenom() + " " + eleve.getNom());
                payload.put("present", true);
                rabbitTemplate.convertAndSend("transport.exchange", "eleve.presence.updated",
                        objectMapper.writeValueAsString(payload));
                log.info("[MS2] Présence publiée — élève={} parent={}", eleve.getId(), eleve.getParentId());
            } catch (Exception e) {
                log.warn("[MS2] Publication eleve.presence.updated échouée : {}", e.getMessage());
            }
        }
    }

    // ── Supprimer un élève ───────────────────────────────────────────
    public void supprimer(Long id) {
        if (!repo.existsById(id)) {
            throw new RuntimeException("Élève non trouvé : " + id);
        }
        repo.deleteById(id);
        rabbitTemplate.convertAndSend("transport.exchange", "eleve.deleted", "eleveId:" + id);
        log.info("[MS2] Élève {} supprimé", id);
    }

    // ── Mapper entité → DTO ──────────────────────────────────────────
    private EleveResponse toResponse(Eleve e) {
        return EleveResponse.builder()
                .id(e.getId())
                .nom(e.getNom())
                .prenom(e.getPrenom())
                .latitude(e.getLatitude())
                .longitude(e.getLongitude())
                .parentId(e.getParentId())
                .groupeId(e.getGroupeId())
                .busId(e.getBusId())
                .statutPresence(e.getStatutPresence())
                .build();
    }

    // ── Ajouter dans EleveService.java ───────────────────────────────────

/**
 * Mise à jour en masse des groupeId — appelé par MS6 après clustering.
 * Une seule transaction pour les N élèves au lieu de N requêtes HTTP.
 */
@Transactional
public int assignerGroupesBulk(Map<Long, Long> eleveGroupeMap) {
    List<Eleve> eleves = repo.findAllById(eleveGroupeMap.keySet());

    for (Eleve eleve : eleves) {
        Long groupeId = eleveGroupeMap.get(eleve.getId());
        if (groupeId != null && groupeId > 0) {
            eleve.setGroupeId(groupeId);
        } else {
            eleve.setGroupeId(null); // groupeId=0 → reset
        }
    }

    repo.saveAll(eleves);
    log.info("[MS2] Bulk update groupeId — {} élèves mis à jour", eleves.size());
    return eleves.size();
}

/**
 * Mise à jour en masse des busId — liaison groupe↔bus, appelée par MS6 après clustering.
 * Une seule transaction pour les N élèves.
 */
@Transactional
public int assignerBusBulk(Map<Long, Long> eleveBusMap) {
    List<Eleve> eleves = repo.findAllById(eleveBusMap.keySet());
    for (Eleve eleve : eleves) {
        Long busId = eleveBusMap.get(eleve.getId());
        eleve.setBusId(busId != null && busId > 0 ? busId : null); // 0/absent → reset
    }
    repo.saveAll(eleves);
    log.info("[MS2] Bulk update busId — {} élèves liés à un bus", eleves.size());
    return eleves.size();
}
}