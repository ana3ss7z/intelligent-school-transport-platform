package ma.transport.ms4notifications.controller;

import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import ma.transport.ms4notifications.dto.DeviceTokenRequest;
import ma.transport.ms4notifications.dto.NotificationResponse;
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
     * Enregistrer le token FCM de l'appareil (appelé au login app mobile).
     * PARENT uniquement.
     */
    @PostMapping("/device-token")
    @PreAuthorize("hasRole('PARENT')")
    public ResponseEntity<Void> enregistrerToken(
            @Valid @RequestBody DeviceTokenRequest req,
            @AuthenticationPrincipal UserPrincipal principal) {
        service.enregistrerToken(principal.getUserId(), req);
        return ResponseEntity.ok().build();
    }

    /**
     * DELETE /api/notifications/device-token/{token}
     * Désactiver un token (logout app mobile).
     */
    @DeleteMapping("/device-token/{token}")
    @PreAuthorize("hasRole('PARENT')")
    public ResponseEntity<Void> supprimerToken(@PathVariable String token) {
        service.supprimerToken(token);
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
    public ResponseEntity<List<NotificationResponse>> getToutesNotifications() {
        return ResponseEntity.ok(service.getToutesNotifications());
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
