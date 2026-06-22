package ma.transport.ms2eleves.controller;

import java.util.List;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.CrossOrigin;
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
import org.springframework.security.access.prepost.PreAuthorize;

@RestController
@RequestMapping("/api/eleves")
@RequiredArgsConstructor
@CrossOrigin(origins = "*")
public class EleveController {

    private final EleveService service;

    @PostMapping
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<EleveResponse> creer(
            @Valid @RequestBody EleveRequest req) {
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(service.creer(req));
    }

    @GetMapping
    public ResponseEntity<List<EleveResponse>> listerTous() {
        return ResponseEntity.ok(service.listerTous());
    }

    @GetMapping("/{id}")
    public ResponseEntity<EleveResponse> getById(
            @PathVariable Long id) {
        return ResponseEntity.ok(service.getById(id));
    }

    @GetMapping("/parent/{parentId}")
    public ResponseEntity<List<EleveResponse>> parParent(
            @PathVariable Long parentId) {
        return ResponseEntity.ok(service.parParent(parentId));
    }

    @GetMapping("/groupe/{groupeId}")
    public ResponseEntity<List<EleveResponse>> parGroupe(
            @PathVariable Long groupeId) {
        return ResponseEntity.ok(service.parGroupe(groupeId));
    }

    @GetMapping("/sans-groupe")
    public ResponseEntity<List<EleveResponse>> sansGroupe() {
        return ResponseEntity.ok(service.sanGroupe());
    }

    /**
     * Route INTERNE — appelée directement par MS4 (port 8082, sans passer par Gateway).
     * Pas de JWT requis : voir SecurityConfig (permitAll sur "/api/eleves/bus/*").
     * Retourne la liste des parentId (dédupliquée) des élèves assignés à un bus.
     */
    @GetMapping("/bus/{busId}/parents")
    public ResponseEntity<List<Long>> parentsParBus(
            @PathVariable Long busId) {
        return ResponseEntity.ok(service.getParentIdsParBus(busId));
    }

    @PutMapping("/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<EleveResponse> modifier(
            @PathVariable Long id,
            @Valid @RequestBody EleveRequest req) {
        return ResponseEntity.ok(service.modifier(id, req));
    }

    @PatchMapping("/{id}/presence")
    @PreAuthorize("hasAnyRole('ADMIN', 'CHAUFFEUR')")
    public ResponseEntity<Void> presence(
            @PathVariable Long id,
            @RequestParam Boolean present) {
        service.mettreAJourPresence(id, present);
        return ResponseEntity.ok().build();
    }

    @DeleteMapping("/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<Void> supprimer(@PathVariable Long id) {
        service.supprimer(id);
        return ResponseEntity.noContent().build();
    }
}