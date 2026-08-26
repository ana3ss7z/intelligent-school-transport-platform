package ma.transport.ms10incidents.controller;

import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import ma.transport.ms10incidents.dto.IncidentRequest;
import ma.transport.ms10incidents.dto.IncidentResponse;
import ma.transport.ms10incidents.dto.StatutRequest;
import ma.transport.ms10incidents.entity.Incident.StatutIncident;
import ma.transport.ms10incidents.service.IncidentService;
import ma.transport.ms10incidents.service.PorteeService;
import ma.transport.mscommon.security.UserPrincipal;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.net.URI;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/incidents")
@RequiredArgsConstructor
public class IncidentController {

    private final IncidentService service;
    private final PorteeService portee;

    /**
     * POST /api/incidents
     * Signaler un incident. ADMIN et CHAUFFEUR.
     */
    @PostMapping
    @PreAuthorize("hasAnyRole('ADMIN', 'CHAUFFEUR')")
    public ResponseEntity<IncidentResponse> creer(
            @Valid @RequestBody IncidentRequest req,
            @AuthenticationPrincipal UserPrincipal principal) {

        // Le busId vient du corps : sans ce controle, un chauffeur signale un incident sur le
        // bus d'un collegue, et ce sont les parents de CE bus qui recoivent l'alerte (P5).
        portee.exigerAccesAuBus(principal, req.getBusId());
        IncidentResponse response = service.creer(req, principal.getUserId());
        return ResponseEntity
                .created(URI.create("/api/incidents/" + response.getId()))
                .body(response);
    }

    /**
     * GET /api/incidents
     * Tous les incidents. ADMIN seulement.
     */
    @GetMapping
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<List<IncidentResponse>> getTous() {
        return ResponseEntity.ok(service.getTous());
    }

    /**
     * GET /api/incidents/{id}
     */
    @GetMapping("/{id}")
    @PreAuthorize("hasAnyRole('ADMIN', 'CHAUFFEUR')")
    public ResponseEntity<IncidentResponse> getById(@PathVariable Long id) {
        return ResponseEntity.ok(service.getById(id));
    }

    /**
     * GET /api/incidents/bus/{busId}
     * Incidents d'un bus spécifique.
     */
    @GetMapping("/bus/{busId}")
    @PreAuthorize("hasAnyRole('ADMIN', 'CHAUFFEUR', 'PARENT')")
    public ResponseEntity<List<IncidentResponse>> getParBus(
            @AuthenticationPrincipal UserPrincipal user,
            @PathVariable Long busId) {
        // La portée était réputée « appliquée en amont par MS9 » : vrai pour le chatbot,
        // faux pour un appel HTTP direct — tout parent lisait toute la flotte (défaut P6).
        portee.exigerAccesAuBus(user, busId);
        return ResponseEntity.ok(service.getParBus(busId));
    }

    /**
     * GET /api/incidents/statut/{statut}
     * Filtrer par statut.
     */
    @GetMapping("/statut/{statut}")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<List<IncidentResponse>> getParStatut(
            @PathVariable StatutIncident statut) {
        return ResponseEntity.ok(service.getParStatut(statut));
    }

    /**
     * PATCH /api/incidents/{id}/statut
     * Changer le statut. ADMIN seulement.
     * RESOLU → publie RabbitMQ → MS4 notifie les parents.
     */
    @PatchMapping("/{id}/statut")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<IncidentResponse> changerStatut(
            @PathVariable Long id,
            @Valid @RequestBody StatutRequest req) {
        return ResponseEntity.ok(service.changerStatut(id, req));
    }

    /**
     * DELETE /api/incidents/{id}
     * ADMIN seulement.
     */
    @DeleteMapping("/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<Void> supprimer(@PathVariable Long id) {
        service.supprimer(id);
        return ResponseEntity.noContent().build();
    }

    /**
     * GET /api/incidents/stats
     * Statistiques des incidents par statut.
     */
    @GetMapping("/stats")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<Map<String, Long>> getStats() {
        return ResponseEntity.ok(service.getStats());
    }
}
