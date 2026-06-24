package ma.transport.ms4notifications.service;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import ma.transport.ms4notifications.dto.DeviceTokenRequest;
import ma.transport.ms4notifications.dto.NotificationResponse;
import ma.transport.ms4notifications.entity.DeviceToken;
import ma.transport.ms4notifications.entity.Notification.StatutEnvoi;
import ma.transport.ms4notifications.entity.Notification.TypeNotification;
import ma.transport.ms4notifications.repository.DeviceTokenRepository;
import ma.transport.ms4notifications.repository.NotificationRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class NotificationService {

    private final NotificationRepository notifRepo;
    private final DeviceTokenRepository  deviceTokenRepo;
    private final FcmService             fcmService;

    // ── Device token ─────────────────────────────────────────────────

    @Transactional
    public void enregistrerToken(Long parentId, DeviceTokenRequest req) {
        deviceTokenRepo.findByFcmToken(req.getFcmToken()).ifPresent(existing -> {
            existing.setActif(false);
            deviceTokenRepo.save(existing);
        });

        DeviceToken token = DeviceToken.builder()
                .parentId(parentId)
                .fcmToken(req.getFcmToken())
                .plateforme(req.getPlateforme())
                .actif(true)
                .build();

        deviceTokenRepo.save(token);
        log.info("[MS4] Token FCM enregistré — parentId={}", parentId);
    }

    @Transactional
    public void supprimerToken(String fcmToken) {
        deviceTokenRepo.findByFcmToken(fcmToken).ifPresent(device -> {
            device.setActif(false);
            deviceTokenRepo.save(device);
            log.info("[MS4] Token FCM désactivé : {}...", fcmToken.substring(0, Math.min(20, fcmToken.length())));
        });
    }

    // ── Notifications ─────────────────────────────────────────────────

    public List<NotificationResponse> getMesNotifications(Long parentId) {
        return notifRepo.findByParentIdOrderByDateEnvoiDesc(parentId)
                .stream()
                .map(NotificationResponse::from)
                .collect(Collectors.toList());
    }

    public List<NotificationResponse> getToutesNotifications() {
        return notifRepo.findAll()
                .stream()
                .map(NotificationResponse::from)
                .collect(Collectors.toList());
    }

    // ── Stats (bugfix echecs=0) ───────────────────────────────────────

    public Map<String, Long> getStats() {
        return Map.of(
            "total",   notifRepo.count(),
            "envoyes", notifRepo.countByStatutEnvoi(StatutEnvoi.ENVOYE),
            "echecs",  notifRepo.countByStatutEnvoi(StatutEnvoi.ECHEC),
            "attente", notifRepo.countByStatutEnvoi(StatutEnvoi.EN_ATTENTE)
        );
    }

    // ── Envoi (appelé par les consumers RabbitMQ) ─────────────────────

    public void envoyerAuParent(Long parentId, TypeNotification type,
                                 String titre, String message,
                                 Long sourceId, String sourceType) {
        fcmService.envoyerAuParent(parentId, type, titre, message, sourceId, sourceType);
    }
}