package ma.transport.ms1bus.controller;

import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import ma.transport.ms1bus.dto.*;
import ma.transport.ms1bus.enums.StatutBus;
import ma.transport.ms1bus.service.BusService;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
import java.util.List;
import org.springframework.security.access.prepost.PreAuthorize;

@RestController
@RequestMapping("/api/bus")
@RequiredArgsConstructor
@CrossOrigin(origins = "*")
public class BusController {

    private final BusService service;

    @PostMapping
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<BusResponse> creer(
            @Valid @RequestBody BusRequest req) {
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(service.creer(req));
    }

    @GetMapping
    public ResponseEntity<List<BusResponse>> listerTous() {
        return ResponseEntity.ok(service.listerTous());
    }

    @GetMapping("/{id}")
    public ResponseEntity<BusResponse> getById(@PathVariable Long id) {
        return ResponseEntity.ok(service.getById(id));
    }

    @GetMapping("/statut/{statut}")
    public ResponseEntity<List<BusResponse>> parStatut(
            @PathVariable StatutBus statut) {
        return ResponseEntity.ok(service.listerParStatut(statut));
    }

    @PutMapping("/{id}")
    @PreAuthorize("hasRole('ADMIN')")

    public ResponseEntity<BusResponse> modifier(
            @PathVariable Long id,
            @Valid @RequestBody BusRequest req) {
        return ResponseEntity.ok(service.modifier(id, req));
    }

    @PatchMapping("/{id}/statut")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<BusResponse> mettreAJourStatut(
            @PathVariable Long id,
            @RequestParam StatutBus statut) {
        return ResponseEntity.ok(
            service.mettreAJourStatut(id, statut));
    }

    @PatchMapping("/{id}/position")
    @PreAuthorize("hasAnyRole('ADMIN', 'CHAUFFEUR')")
    public ResponseEntity<Void> mettreAJourPosition(
            @PathVariable Long id,
            @RequestParam Double lat,
            @RequestParam Double lng) {
        service.mettreAJourPosition(id, lat, lng);
        return ResponseEntity.ok().build();
    }

    @DeleteMapping("/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<Void> supprimer(@PathVariable Long id) {
        service.supprimer(id);
        return ResponseEntity.noContent().build();
    }
}