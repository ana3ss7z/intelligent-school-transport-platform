package ma.transport.ms3localisation.controller;

import java.util.List;
import java.util.Map;

import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
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
import ma.transport.ms3localisation.service.PorteeService;
import ma.transport.mscommon.security.UserPrincipal;

@RestController
@RequestMapping("/api/gps")
@RequiredArgsConstructor
public class GpsController {

    private final GpsService service;
    private final PorteeService portee;

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
    @PreAuthorize("hasAnyRole('ADMIN','CHAUFFEUR','PARENT')")
    public ResponseEntity<PositionResponse> dernierePositionBus(
            @AuthenticationPrincipal UserPrincipal user,
            @PathVariable Long busId) {
        portee.exigerAccesAuBus(user, busId);
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
    @PreAuthorize("hasAnyRole('ADMIN','CHAUFFEUR','PARENT')")
    public ResponseEntity<List<PositionResponse>> tousLesBus(
            @AuthenticationPrincipal UserPrincipal user) {
        // La vue « toute la flotte » est une vue d'exploitation. Un chauffeur ou un parent
        // reçoit la même route, mais filtrée aux bus qui le concernent : sans ce filtre, un
        // parent d'un seul enfant obtenait les 14 positions de la flotte (défaut P12).
        List<PositionResponse> toutes = service.getDernieresPositionsBus();
        return ResponseEntity.ok(portee.filtrerAuxBusAutorises(user, toutes));
    }

    /*
     * Les routes /api/gps/eleve/{id}/derniere et /historique ont été SUPPRIMÉES le 26/08.
     *
     * Elles servaient l'historique de géolocalisation d'un élève à tout PARENT, sans vérifier
     * qu'il s'agissait du sien — n'importe quelle famille pouvait suivre l'enfant d'une autre
     * (défaut P2 de la recette). Or aucun client ne les appelait : vérification faite sur les
     * trois frontends (console web, applications parent et chauffeur) et sur les cinq services
     * Python. Le seul appelant était le script de recette qui les a mises au jour.
     *
     * Supprimer valait mieux que garder : une route morte ne rend aucun service et se contente
     * d'exposer une surface. Le suivi d'un élève passe par la position de SON bus, déjà scopée.
     */

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