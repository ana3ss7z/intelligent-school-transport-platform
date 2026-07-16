package ma.transport.ms2eleves.controller;

import java.util.List;
import java.util.Map;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import ma.transport.ms2eleves.dto.EleveRequest;
import ma.transport.ms2eleves.dto.EleveResponse;
import ma.transport.ms2eleves.service.EleveService;

@RestController
@RequestMapping("/api/eleves")
@RequiredArgsConstructor
public class EleveController {

    private final EleveService service;

    // ── POST /api/eleves ─────────────────────────────────────────────
    @PostMapping
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<EleveResponse> creer(
            @Valid @RequestBody EleveRequest req) {
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(service.creer(req));
    }

    // ── GET /api/eleves ──────────────────────────────────────────────
    @GetMapping
    public ResponseEntity<List<EleveResponse>> listerTous() {
        return ResponseEntity.ok(service.listerTous());
    }

    // ── GET /api/eleves/{id} ─────────────────────────────────────────
    @GetMapping("/{id}")
    public ResponseEntity<EleveResponse> getById(@PathVariable Long id) {
        return ResponseEntity.ok(service.getById(id));
    }

    // ── GET /api/eleves/parent/{parentId} ────────────────────────────
    @GetMapping("/parent/{parentId}")
    public ResponseEntity<List<EleveResponse>> parParent(
            @PathVariable Long parentId) {
        return ResponseEntity.ok(service.parParent(parentId));
    }

    // ── GET /api/eleves/bus/{busId} : élèves du bus dans l'ordre de passage (vue chauffeur) ──
    @GetMapping("/bus/{busId}")
    @PreAuthorize("hasAnyRole('ADMIN','CHAUFFEUR')")
    public ResponseEntity<List<EleveResponse>> parBusOrdonne(@PathVariable Long busId) {
        return ResponseEntity.ok(service.parBusOrdonne(busId));
    }

    // ── GET /api/eleves/groupe/{groupeId} ────────────────────────────
    @GetMapping("/groupe/{groupeId}")
    public ResponseEntity<List<EleveResponse>> parGroupe(
            @PathVariable Long groupeId) {
        return ResponseEntity.ok(service.parGroupe(groupeId));
    }

    // ── GET /api/eleves/sans-groupe ──────────────────────────────────
    @GetMapping("/sans-groupe")
    public ResponseEntity<List<EleveResponse>> sansGroupe() {
        return ResponseEntity.ok(service.sanGroupe());
    }

    /**
     * GET /api/eleves/bus/{busId}/parents
     * Route INTERNE (sans JWT) — appelée par MS4 pour les notifications FCM.
     * Retourne la liste dédupliquée des parentId des élèves d'un bus.
     */
    @GetMapping("/bus/{busId}/parents")
    public ResponseEntity<List<Long>> parentsParBus(@PathVariable Long busId) {
        return ResponseEntity.ok(service.getParentIdsParBus(busId));
    }

    // ── PUT /api/eleves/{id} ─────────────────────────────────────────
    @PutMapping("/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<EleveResponse> modifier(
            @PathVariable Long id,
            @Valid @RequestBody EleveRequest req) {
        return ResponseEntity.ok(service.modifier(id, req));
    }

    /**
     * PATCH /api/eleves/{id}/bus?busId=X
     * Assigner un bus à un élève (ADMIN ou résultat clustering MS6).
     */
    @PatchMapping("/{id}/bus")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<EleveResponse> assignerBus(
            @PathVariable Long id,
            @RequestParam Long busId) {
        return ResponseEntity.ok(service.assignerBus(id, busId));
    }

    /**
     * PATCH /api/eleves/{id}/groupe?groupeId=X
     * Assigner un groupe géographique (appelé par MS6 ClusteringService).
     * Route interne — pas de JWT requis (voir SecurityConfig).
     */
    @PatchMapping("/{id}/groupe")
    public ResponseEntity<EleveResponse> assignerGroupe(
            @PathVariable Long id,
            @RequestParam Long groupeId) {
        return ResponseEntity.ok(service.assignerGroupe(id, groupeId));
    }

    // ── PATCH /api/eleves/{id}/presence ──────────────────────────────
    @PatchMapping("/{id}/presence")
    @PreAuthorize("hasAnyRole('ADMIN', 'CHAUFFEUR')")
    public ResponseEntity<Void> presence(
            @PathVariable Long id,
            @RequestParam Boolean present) {
        service.mettreAJourPresence(id, present);
        return ResponseEntity.ok().build();
    }

    // ── DELETE /api/eleves/{id} ──────────────────────────────────────
    @DeleteMapping("/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<Void> supprimer(@PathVariable Long id) {
        service.supprimer(id);
        return ResponseEntity.noContent().build();
    }

    // ── Ajouter dans EleveController.java ────────────────────────────────

/**
 * PUT /api/eleves/groupes/bulk
 * Mise à jour en masse des groupeId après clustering MS6.
 * Une seule requête HTTP au lieu de 300 PATCH simultanés.
 * Route interne — pas de JWT requis (voir SecurityConfig).
 */
@PutMapping("/groupes/bulk")
public ResponseEntity<Map<String, Integer>> assignerGroupesBulk(
        @RequestBody Map<Long, Long> eleveGroupeMap) {
    int updated = service.assignerGroupesBulk(eleveGroupeMap);
    return ResponseEntity.ok(Map.of("updated", updated));
}

/**
 * PUT /api/eleves/bus/bulk
 * Liaison groupe↔bus : propage busId en masse après clustering (MS6 → MS1 → MS2).
 * Route interne — pas de JWT requis (voir SecurityConfig).
 */
@PutMapping("/bus/bulk")
public ResponseEntity<Map<String, Integer>> assignerBusBulk(
        @RequestBody Map<Long, Long> eleveBusMap) {
    int updated = service.assignerBusBulk(eleveBusMap);
    return ResponseEntity.ok(Map.of("updated", updated));
}

/**
 * PUT /api/eleves/ordre/bulk
 * Persistance de l'ordre de passage des tournées (MS5-VRP). Route interne — pas de JWT.
 */
@PutMapping("/ordre/bulk")
public ResponseEntity<Map<String, Integer>> assignerOrdreBulk(
        @RequestBody Map<Long, Long> eleveOrdreMap) {
    int updated = service.assignerOrdreBulk(eleveOrdreMap);
    return ResponseEntity.ok(Map.of("updated", updated));
}
}