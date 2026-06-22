package ma.transport.ms4notifications.service;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import ma.transport.ms4notifications.dto.DeviceTokenRequest;
import ma.transport.ms4notifications.dto.NotificationResponse;
import ma.transport.ms4notifications.entity.DeviceToken;
import ma.transport.ms4notifications.entity.Notification;
import ma.transport.ms4notifications.repository.DeviceTokenRepository;
import ma.transport.ms4notifications.repository.NotificationRepository;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

@Slf4j
@Service
@RequiredArgsConstructor
public class NotificationService {

    private final NotificationRepository notifRepo;
    private final DeviceTokenRepository  deviceTokenRepo;

    // ─── Historique notifications ─────────────────────────────────────────────

    public List<NotificationResponse> getMesNotifications(Long parentId) {
        return notifRepo.findByParentIdOrderByDateEnvoiDesc(parentId)
                .stream().map(NotificationResponse::from).toList();
    }

    public List<NotificationResponse> getToutesNotifications() {
        return notifRepo.findAll().stream()
                .map(NotificationResponse::from).toList();
    }

    // ─── Device tokens FCM ───────────────────────────────────────────────────

    public void enregistrerToken(Long parentId, DeviceTokenRequest req) {
        if (deviceTokenRepo.existsByFcmToken(req.getFcmToken())) {
            log.debug("[MS4] Token déjà enregistré pour parent {}", parentId);
            return;
        }

        DeviceToken token = DeviceToken.builder()
                .parentId(parentId)
                .fcmToken(req.getFcmToken())
                .plateforme(req.getPlateforme() != null ? req.getPlateforme() : "ANDROID")
                .build();

        deviceTokenRepo.save(token);
        log.info("[MS4] Token FCM enregistré pour parent {}", parentId);
    }

    public void supprimerToken(String fcmToken) {
        deviceTokenRepo.findByFcmToken(fcmToken).ifPresent(t -> {
            t.setActif(false);
            deviceTokenRepo.save(t);
            log.info("[MS4] Token FCM désactivé");
        });
    }

    // ─── Stats ───────────────────────────────────────────────────────────────

    public Map<String, Long> getStats() {
        return Map.of(
            "total",         notifRepo.count(),
            "envoyees",      notifRepo.countByParentIdAndStatutEnvoi(null,
                             Notification.StatutEnvoi.ENVOYE),
            "echecs",        notifRepo.countByParentIdAndStatutEnvoi(null,
                             Notification.StatutEnvoi.ECHEC),
            "devices_actifs", deviceTokenRepo.count()
        );
    }
}
