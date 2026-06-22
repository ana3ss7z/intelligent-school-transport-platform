package ma.transport.ms3localisation.controller;

import java.util.List;
import java.util.Map;

import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import ma.transport.ms3localisation.dto.PositionRequest;
import ma.transport.ms3localisation.dto.PositionResponse;
import ma.transport.ms3localisation.entity.PositionGPS.TypeCible;
import ma.transport.ms3localisation.service.GpsService;

@RestController
@RequestMapping("/api/gps")
@RequiredArgsConstructor
@CrossOrigin(origins = "*")
public class GpsController {

    private final GpsService service;

    /**
     * POST /api/gps/position
     * Publier une nouvelle position GPS (bus ou élève).
     * Appelé par le device embarqué dans le bus ou l'app chauffeur.
     * CHAUFFEUR et ADMIN uniquement.
     */
    @PostMapping("/position")
    @PreAuthorize("hasAnyRole('ADMIN', 'CHAUFFEUR')")
    public ResponseEntity<PositionResponse> publierPosition(
            @Valid @RequestBody PositionRequest req) {
        return ResponseEntity.ok(service.publierPosition(req));
    }

    /**
     * GET /api/gps/bus/{busId}/derniere
     * Dernière position connue d'un bus.
     */
    @GetMapping("/bus/{busId}/derniere")
    public ResponseEntity<PositionResponse> dernierePositionBus(
            @PathVariable Long busId) {
        return service.getDernierePosition(TypeCible.BUS, busId)
                .map(ResponseEntity::ok)
                .orElse(ResponseEntity.notFound().build());
    }

    /**
     * GET /api/gps/bus/{busId}/historique
     * Historique complet des positions d'un bus.
     */
    @GetMapping("/bus/{busId}/historique")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<List<PositionResponse>> historiqueBus(
            @PathVariable Long busId) {
        return ResponseEntity.ok(service.getHistorique(TypeCible.BUS, busId));
    }

    /**
     * GET /api/gps/bus/tous
     * Dernières positions de tous les bus (vue carte admin).
     */
    @GetMapping("/bus/tous")
    public ResponseEntity<List<PositionResponse>> tousLesBus() {
        return ResponseEntity.ok(service.getDernieresPositionsBus());
    }

    /**
     * GET /api/gps/eleve/{eleveId}/derniere
     * Dernière position connue d'un élève.
     */
    @GetMapping("/eleve/{eleveId}/derniere")
    public ResponseEntity<PositionResponse> dernierePositionEleve(
            @PathVariable Long eleveId) {
        return service.getDernierePosition(TypeCible.ELEVE, eleveId)
                .map(ResponseEntity::ok)
                .orElse(ResponseEntity.notFound().build());
    }

    /**
     * GET /api/gps/eleve/{eleveId}/historique
     * Historique des positions d'un élève.
     */
    @GetMapping("/eleve/{eleveId}/historique")
    @PreAuthorize("hasAnyRole('ADMIN', 'PARENT')")
    public ResponseEntity<List<PositionResponse>> historiqueEleve(
            @PathVariable Long eleveId) {
        return ResponseEntity.ok(service.getHistorique(TypeCible.ELEVE, eleveId));
    }

    /**
     * GET /api/gps/stats
     * Nombre de clients WebSocket connectés.
     */
    @GetMapping("/stats")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<Map<String, Object>> stats() {
        return ResponseEntity.ok(Map.of(
                "service", "MS3-Localisation",
                "websocketClients", service.getNbClientsWebSocket()
        ));
    }
}