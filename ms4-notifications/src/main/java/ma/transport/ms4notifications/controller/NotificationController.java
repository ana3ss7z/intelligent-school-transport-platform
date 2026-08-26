package ma.transport.ms4notifications.controller;

import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import ma.transport.ms4notifications.dto.DeviceTokenRequest;
import ma.transport.ms4notifications.dto.NotificationResponse;
import ma.transport.ms4notifications.dto.PageResponse;
import ma.transport.ms4notifications.service.NotificationService;
import ma.transport.mscommon.security.UserPrincipal;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/notifications")
@RequiredArgsConstructor
public class NotificationController {

    private final NotificationService service;

    /**
     * POST /api/notifications/device-token
     * Enregistrer le token FCM de l'appareil (appelé au login des clients).
     *
     * <p>Ouvert à CHAUFFEUR en plus de PARENT : MS4 envoie déjà des notifications aux
     * chauffeurs (incident résolu sur leur bus, message de l'administration) et
     * {@code /mes-notifications} leur est ouvert depuis l'origine. Seul cet endpoint restait
     * réservé aux parents, ce qui rendait le push structurellement impossible pour eux.
     */
    @PostMapping("/device-token")
    @PreAuthorize("hasAnyRole('PARENT','CHAUFFEUR')")
    public ResponseEntity<Void> enregistrerToken(
            @Valid @RequestBody DeviceTokenRequest req,
            @AuthenticationPrincipal UserPrincipal principal) {
        service.enregistrerToken(principal.getUserId(), req);
        return ResponseEntity.ok().build();
    }

    /**
     * DELETE /api/notifications/device-token/{token}
     * Désactiver un token (logout des clients) — mêmes rôles que l'enregistrement.
     */
    @DeleteMapping("/device-token/{token}")
    @PreAuthorize("hasAnyRole('PARENT','CHAUFFEUR')")
    public ResponseEntity<Void> supprimerToken(
            @AuthenticationPrincipal UserPrincipal principal,
            @PathVariable String token) {
        // Le jeton etait desactive sur sa seule valeur : n'importe quel compte pouvait
        // couper les notifications d'un autre en connaissant son jeton (defaut P13).
        service.supprimerToken(token, principal.getUserId());
        return ResponseEntity.noContent().build();
    }

    /**
     * GET /api/notifications/mes-notifications
     * Historique des notifications du parent connecté.
     */
    @GetMapping("/mes-notifications")
    @PreAuthorize("hasAnyRole('PARENT','CHAUFFEUR')")
    public ResponseEntity<List<NotificationResponse>> getMesNotifications(
            @AuthenticationPrincipal UserPrincipal principal) {
        return ResponseEntity.ok(service.getMesNotifications(principal.getUserId()));
    }

    /**
     * GET /api/notifications
     * Toutes les notifications. ADMIN seulement.
     */
    @GetMapping
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<PageResponse<NotificationResponse>> getToutesNotifications(
            @RequestParam(defaultValue = "0")     int page,
            @RequestParam(defaultValue = "25")    int size,
            @RequestParam(defaultValue = "id")    String tri,
            @RequestParam(defaultValue = "desc")  String sens,
            @RequestParam(defaultValue = "false") boolean adminSeulement) {
        return ResponseEntity.ok(service.getToutesNotifications(page, size, tri, sens, adminSeulement));
    }

    /**
     * GET /api/notifications/stats
     */
    @GetMapping("/stats")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<Map<String, Long>> getStats() {
        return ResponseEntity.ok(service.getStats());
    }
}
