package ma.transport.ms1bus.service;
import java.util.List;
import java.util.stream.Collectors;

import org.springframework.stereotype.Service;

import lombok.RequiredArgsConstructor;
import ma.transport.ms1bus.dto.BusRequest;
import ma.transport.ms1bus.dto.BusResponse;
import ma.transport.ms1bus.entity.Bus;
import ma.transport.ms1bus.enums.StatutBus;
import ma.transport.ms1bus.repository.BusRepository;

@Service
@RequiredArgsConstructor
public class BusService {

    private final BusRepository repo;

    // ── Créer un bus ─────────────────────────────────────────────────
    public BusResponse creer(BusRequest req) {
        if (repo.existsByMatricule(req.getMatricule())) {
            throw new RuntimeException(
                "Matricule déjà existant : " + req.getMatricule());
        }
        Bus bus = Bus.builder()
                .matricule(req.getMatricule())
                .capacite(req.getCapacite())
                .statut(req.getStatut())
                .chauffeurId(req.getChauffeurId())
                .build();
        return toResponse(repo.save(bus));
    }

    // ── Lister tous les bus ──────────────────────────────────────────
    public List<BusResponse> listerTous() {
        return repo.findAll().stream()
                .map(this::toResponse)
                .collect(Collectors.toList());
    }

    // ── Lister par statut ────────────────────────────────────────────
    public List<BusResponse> listerParStatut(StatutBus statut) {
        return repo.findByStatut(statut).stream()
                .map(this::toResponse)
                .collect(Collectors.toList());
    }

    // ── Obtenir un bus par ID ────────────────────────────────────────
    public BusResponse getById(Long id) {
        Bus bus = repo.findById(id)
                .orElseThrow(() ->
                    new RuntimeException("Bus non trouvé : " + id));
        return toResponse(bus);
    }

    // ── Modifier un bus ──────────────────────────────────────────────
    public BusResponse modifier(Long id, BusRequest req) {
        Bus bus = repo.findById(id)
                .orElseThrow(() ->
                    new RuntimeException("Bus non trouvé : " + id));
        bus.setMatricule(req.getMatricule());
        bus.setCapacite(req.getCapacite());
        bus.setStatut(req.getStatut());
        bus.setChauffeurId(req.getChauffeurId());
        return toResponse(repo.save(bus));
    }

    // ── Mettre à jour le statut ──────────────────────────────────────
    public BusResponse mettreAJourStatut(Long id, StatutBus statut) {
        Bus bus = repo.findById(id)
                .orElseThrow(() ->
                    new RuntimeException("Bus non trouvé : " + id));
        bus.setStatut(statut);
        return toResponse(repo.save(bus));
    }

    // ── Mettre à jour position GPS ───────────────────────────────────
    public void mettreAJourPosition(Long id,
                                     Double lat, Double lng) {
        Bus bus = repo.findById(id)
                .orElseThrow(() ->
                    new RuntimeException("Bus non trouvé : " + id));
        bus.setLatitude(lat);
        bus.setLongitude(lng);
        repo.save(bus);
    }

    // ── Supprimer un bus ─────────────────────────────────────────────
    public void supprimer(Long id) {
        if (!repo.existsById(id)) {
            throw new RuntimeException("Bus non trouvé : " + id);
        }
        repo.deleteById(id);
    }

    // ── Mapper entité → DTO ──────────────────────────────────────────
    private BusResponse toResponse(Bus bus) {
        return BusResponse.builder()
                .id(bus.getId())
                .matricule(bus.getMatricule())
                .capacite(bus.getCapacite())
                .statut(bus.getStatut())
                .chauffeurId(bus.getChauffeurId())
                .latitude(bus.getLatitude())
                .longitude(bus.getLongitude())
                .capaciteRestante(bus.getCapacite()) // sera calculé avec élèves
                .build();
    }
}