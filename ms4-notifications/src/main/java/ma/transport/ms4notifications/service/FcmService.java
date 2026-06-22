package ma.transport.ms4notifications.service;

import com.google.firebase.FirebaseApp;
import com.google.firebase.messaging.*;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import ma.transport.ms4notifications.entity.Notification;
import ma.transport.ms4notifications.entity.Notification.StatutEnvoi;
import ma.transport.ms4notifications.entity.Notification.TypeNotification;
import ma.transport.ms4notifications.entity.DeviceToken;
import ma.transport.ms4notifications.repository.DeviceTokenRepository;
import ma.transport.ms4notifications.repository.NotificationRepository;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.List;

/**
 * FcmService — envoie les push notifications via Firebase Cloud Messaging.
 *
 * Si Firebase n'est pas configuré (placeholder JSON), log un warning
 * mais persiste la notification en DB avec statut ECHEC.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class FcmService {

    private final FirebaseApp           firebaseApp;
    private final DeviceTokenRepository deviceTokenRepo;
    private final NotificationRepository notifRepo;

    /**
     * Envoie une notification push à tous les devices d'un parent.
     */
    public void envoyerAuParent(Long parentId, TypeNotification type,
                                 String titre, String message,
                                 Long sourceId, String sourceType) {

        List<DeviceToken> tokens = deviceTokenRepo.findByParentIdAndActifTrue(parentId);

        if (tokens.isEmpty()) {
            log.debug("[FCM] Aucun device enregistré pour parent {}", parentId);
            // Persister quand même pour l'historique
            sauvegarder(parentId, null, type, titre, message, sourceId, sourceType,
                        StatutEnvoi.ECHEC, "Aucun device FCM enregistré");
            return;
        }

        for (DeviceToken device : tokens) {
            envoyerAuToken(device.getFcmToken(), parentId, type,
                           titre, message, sourceId, sourceType);
        }
    }

    /**
     * Envoie une notification à un token FCM spécifique.
     */
    private void envoyerAuToken(String fcmToken, Long parentId,
                                 TypeNotification type, String titre,
                                 String message, Long sourceId, String sourceType) {

        // Firebase non configuré (placeholder JSON) → mode dégradé
        if (firebaseApp == null) {
            log.warn("[FCM] Firebase non configuré — notification simulée pour parent {}", parentId);
            log.warn("[FCM] Titre: {} | Message: {}", titre, message);
            sauvegarder(parentId, fcmToken, type, titre, message, sourceId, sourceType,
                        StatutEnvoi.ECHEC, "Firebase non configuré — remplacer firebase-service-account.json");
            return;
        }

        try {
            Message fcmMessage = Message.builder()
                    .setToken(fcmToken)
                    .setNotification(com.google.firebase.messaging.Notification.builder()
                            .setTitle(titre)
                            .setBody(message)
                            .build())
                    .putData("type",       type.name())
                    .putData("sourceId",   sourceId != null ? sourceId.toString() : "")
                    .putData("sourceType", sourceType != null ? sourceType : "")
                    .setAndroidConfig(AndroidConfig.builder()
                            .setPriority(AndroidConfig.Priority.HIGH)
                            .build())
                    .build();

            String messageId = FirebaseMessaging.getInstance(firebaseApp).send(fcmMessage);
            log.info("[FCM] ✅ Notification envoyée — parent={} messageId={}", parentId, messageId);

            sauvegarder(parentId, fcmToken, type, titre, message, sourceId, sourceType,
                        StatutEnvoi.ENVOYE, null);

        } catch (FirebaseMessagingException e) {
            log.error("[FCM] ❌ Erreur envoi — parent={} : {}", parentId, e.getMessage());

            // Désactiver le token si invalide
            if (e.getMessagingErrorCode() == MessagingErrorCode.UNREGISTERED
             || e.getMessagingErrorCode() == MessagingErrorCode.INVALID_ARGUMENT) {
                deviceTokenRepo.findByFcmToken(fcmToken).ifPresent(device -> {
                    device.setActif(false);
                    deviceTokenRepo.save(device);
                    log.info("[FCM] Token désactivé : {}", fcmToken.substring(0, 20) + "...");
                });
            }

            sauvegarder(parentId, fcmToken, type, titre, message, sourceId, sourceType,
                        StatutEnvoi.ECHEC, e.getMessage());
        }
    }

    // ─── Persister la notification ────────────────────────────────────────────

    private void sauvegarder(Long parentId, String fcmToken, TypeNotification type,
                              String titre, String message, Long sourceId, String sourceType,
                              StatutEnvoi statut, String erreur) {
        Notification notif = Notification.builder()
                .parentId(parentId)
                .fcmToken(fcmToken)
                .type(type)
                .titre(titre)
                .message(message)
                .sourceId(sourceId)
                .sourceType(sourceType)
                .statutEnvoi(statut)
                .dateEnvoi(LocalDateTime.now())
                .erreurFcm(erreur)
                .build();
        notifRepo.save(notif);
    }
}
