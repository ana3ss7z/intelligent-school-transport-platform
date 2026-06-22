package ma.transport.ms2eleves.service;

import java.util.List;
import java.util.stream.Collectors;

import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.stereotype.Service;

import lombok.RequiredArgsConstructor;
import ma.transport.ms2eleves.dto.EleveRequest;
import ma.transport.ms2eleves.dto.EleveResponse;
import ma.transport.ms2eleves.entity.Eleve;
import ma.transport.ms2eleves.repository.EleveRepository;

@Service
@RequiredArgsConstructor
public class EleveService {

    private final EleveRepository repo;
    private final RabbitTemplate rabbitTemplate;

    // ── Créer un élève ───────────────────────────────────────────────
    public EleveResponse creer(EleveRequest req) {
        Eleve eleve = Eleve.builder()
                .nom(req.getNom())
                .prenom(req.getPrenom())
                .latitude(req.getLatitude())
                .longitude(req.getLongitude())
                .parentId(req.getParentId())
                .build();

        Eleve saved = repo.save(eleve);

        // Publier événement RabbitMQ → MS6 clustering
        rabbitTemplate.convertAndSend(
            "transport.exchange",
            "eleve.created",
            "eleveId:" + saved.getId()
        );

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

    // ── Élèves sans groupe (pour clustering) ─────────────────────────
    public List<EleveResponse> sanGroupe() {
        return repo.findByGroupeIdIsNull().stream()
                .map(this::toResponse)
                .collect(Collectors.toList());
    }

    // ── Obtenir un élève ─────────────────────────────────────────────
    public EleveResponse getById(Long id) {
        return toResponse(repo.findById(id)
                .orElseThrow(() ->
                    new RuntimeException("Élève non trouvé : " + id)));
    }

    /**
     * Liste des parentId (dédupliquée, sans null) des élèves assignés à un bus.
     * Appelée directement par MS4 (route interne, sans JWT) pour les notifications.
     */
    public List<Long> getParentIdsParBus(Long busId) {
        return repo.findByBusId(busId).stream()
                .map(Eleve::getParentId)
                .filter(java.util.Objects::nonNull)
                .distinct()
                .collect(Collectors.toList());
    }

    // ── Modifier un élève ────────────────────────────────────────────
    public EleveResponse modifier(Long id, EleveRequest req) {
        Eleve eleve = repo.findById(id)
                .orElseThrow(() ->
                    new RuntimeException("Élève non trouvé : " + id));

        boolean gpsModifie =
            !eleve.getLatitude().equals(req.getLatitude()) ||
            !eleve.getLongitude().equals(req.getLongitude());

        eleve.setNom(req.getNom());
        eleve.setPrenom(req.getPrenom());
        eleve.setLatitude(req.getLatitude());
        eleve.setLongitude(req.getLongitude());
        eleve.setParentId(req.getParentId());

        Eleve saved = repo.save(eleve);

        // Si GPS modifié → événement RabbitMQ → recalcul clustering
        if (gpsModifie) {
            rabbitTemplate.convertAndSend(
                "transport.exchange",
                "eleve.gps.updated",
                "eleveId:" + saved.getId()
            );
        }

        return toResponse(saved);
    }

    // ── Mettre à jour présence ───────────────────────────────────────
    public void mettreAJourPresence(Long id, Boolean present) {
        Eleve eleve = repo.findById(id)
                .orElseThrow(() ->
                    new RuntimeException("Élève non trouvé : " + id));
        eleve.setStatutPresence(present);
        repo.save(eleve);
    }

    // ── Supprimer un élève ───────────────────────────────────────────
    public void supprimer(Long id) {
        if (!repo.existsById(id)) {
            throw new RuntimeException("Élève non trouvé : " + id);
        }
        repo.deleteById(id);

        // Événement RabbitMQ → recalcul clustering
        rabbitTemplate.convertAndSend(
            "transport.exchange",
            "eleve.deleted",
            "eleveId:" + id
        );
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
}