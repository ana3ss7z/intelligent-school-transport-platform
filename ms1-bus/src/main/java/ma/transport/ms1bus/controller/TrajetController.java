package ma.transport.ms1bus.controller;

import java.util.List;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import ma.transport.ms1bus.dto.TrajetRequest;
import ma.transport.ms1bus.dto.TrajetResponse;
import ma.transport.ms1bus.dto.TrajetRouteResponse;
import ma.transport.ms1bus.service.TrajetService;
import ma.transport.mscommon.security.UserPrincipal;

@RestController
@RequestMapping("/api/trajets")
@RequiredArgsConstructor
public class TrajetController {

    private final TrajetService service;
    private final ma.transport.ms1bus.service.PorteeService portee;

    @PostMapping("/demarrer")
    @PreAuthorize("hasAnyRole('CHAUFFEUR', 'ADMIN')")
    public ResponseEntity<TrajetResponse> demarrer(
            @AuthenticationPrincipal UserPrincipal user,
            @Valid @RequestBody TrajetRequest req) {
        // Le busId vient du corps de la requete : sans ce controle, un chauffeur demarre un
        // trajet sur le bus d'un collegue, ce qui arme la surveillance MS11 et notifie
        // l'administration pour un vehicule qu'il ne conduit pas (defaut P9).
        portee.exigerBusDuChauffeur(user, req.getBusId());
        return ResponseEntity.status(HttpStatus.CREATED).body(service.demarrer(user.getUserId(), req));
    }

    @PostMapping("/{id}/terminer")
    @PreAuthorize("hasAnyRole('CHAUFFEUR', 'ADMIN')")
    public ResponseEntity<TrajetResponse> terminer(
            @AuthenticationPrincipal UserPrincipal user,
            @PathVariable Long id) {
        return ResponseEntity.ok(service.terminer(id, user.getUserId(), user.getRole()));
    }

    @GetMapping("/actifs")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<List<TrajetResponse>> actifs() {
        return ResponseEntity.ok(service.actifs());
    }

    @GetMapping("/mon-actif")
    @PreAuthorize("hasAnyRole('CHAUFFEUR', 'ADMIN')")
    public ResponseEntity<TrajetResponse> monActif(@AuthenticationPrincipal UserPrincipal user) {
        TrajetResponse t = service.monActif(user.getUserId());
        return t == null ? ResponseEntity.noContent().build() : ResponseEntity.ok(t);
    }

    @GetMapping("/mes-trajets")
    @PreAuthorize("hasAnyRole('CHAUFFEUR', 'ADMIN')")
    public ResponseEntity<List<TrajetResponse>> mesTrajets(@AuthenticationPrincipal UserPrincipal user) {
        return ResponseEntity.ok(service.mesTrajets(user.getUserId()));
    }

    /** Trajet EN_COURS d'un bus (suivi parent : ETA selon le sens). 204 si aucun. */
    @GetMapping("/bus/{busId}/actif")
    @PreAuthorize("hasAnyRole('ADMIN', 'CHAUFFEUR', 'PARENT')")
    public ResponseEntity<TrajetResponse> actifParBus(
            @AuthenticationPrincipal UserPrincipal user,
            @PathVariable Long busId) {
        portee.exigerAccesAuBus(user, busId);
        TrajetResponse t = service.actifParBus(busId);
        return t == null ? ResponseEntity.noContent().build() : ResponseEntity.ok(t);
    }

    /**
     * Tournée figée du trajet en cours d'un bus (polyligne + totaux OSRM). 204 si aucun trajet.
     *
     * <p>Permet aux fronts de mesurer la distance <b>restante le long du circuit</b> au lieu du
     * vol d'oiseau : le bus s'éloigne de l'école pendant le ramassage, un ETA point-à-point
     * augmenterait au lieu de décroître. Ouvert au PARENT (lecture seule, déjà scopé par bus).</p>
     */
    @GetMapping("/bus/{busId}/route")
    @PreAuthorize("hasAnyRole('ADMIN', 'CHAUFFEUR', 'PARENT')")
    public ResponseEntity<TrajetRouteResponse> routeParBus(
            @AuthenticationPrincipal UserPrincipal user,
            @PathVariable Long busId) {
        // La polyligne trace la rue de chaque famille du bus : la lecture doit etre
        // reservee aux familles concernees, pas ouverte a tout parent (defaut P7).
        portee.exigerAccesAuBus(user, busId);
        TrajetRouteResponse r = service.routeParBus(busId);
        return r == null ? ResponseEntity.noContent().build() : ResponseEntity.ok(r);
    }
}
