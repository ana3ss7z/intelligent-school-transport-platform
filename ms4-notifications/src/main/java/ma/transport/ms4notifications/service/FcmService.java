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
     * Envoie une notification push à tous les appareils d'un destinataire, et l'historise
     * <b>une seule fois</b>.
     *
     * <p>La persistance était auparavant faite <i>dans</i> la boucle d'envoi : une ligne par
     * appareil. Tant qu'aucun client n'enregistrait de token, le défaut restait invisible —
     * zéro appareil produit exactement une ligne. Dès qu'un même parent est connecté sur
     * plusieurs origines (console web, application parent, téléphone), le <b>même événement
     * métier</b> aurait produit autant de lignes que d'appareils, et
     * {@code GET /mes-notifications} aurait affiché le message en double dans l'application
     * de la famille.
     *
     * <p>Une ligne décrit donc désormais l'événement, pas la tentative :
     * {@link StatutEnvoi#ENVOYE} dès qu'<b>au moins un</b> appareil a reçu. La contrepartie
     * assumée est la perte du diagnostic par appareil — un échec partiel n'apparaît qu'au
     * journal. Le suivi fin exigerait une table de livraison séparée.
     */
    public void envoyerAuParent(Long parentId, TypeNotification type,
                                 String titre, String message,
                                 Long sourceId, String sourceType) {

        List<DeviceToken> tokens = deviceTokenRepo.findByParentIdAndActifTrue(parentId);

        if (tokens.isEmpty()) {
            log.debug("[FCM] Aucun device enregistré pour parent {}", parentId);
            // Persister quand même pour l'historique : l'absence de push ne doit pas faire
            // disparaître la notification de l'application, qui la lit sans filtrer le statut.
            sauvegarder(parentId, null, type, titre, message, sourceId, sourceType,
                        StatutEnvoi.ECHEC, "Aucun device FCM enregistré");
            return;
        }

        int envoyes = 0;
        String premiereErreur = null;
        for (DeviceToken device : tokens) {
            String erreur = envoyerAuToken(device.getFcmToken(), parentId, type,
                                           titre, message, sourceId, sourceType);
            if (erreur == null) envoyes++;
            else if (premiereErreur == null) premiereErreur = erreur;
        }

        if (envoyes > 0 && envoyes < tokens.size()) {
            log.warn("[FCM] Envoi partiel — parent={} : {}/{} appareils, 1ʳᵉ erreur : {}",
                     parentId, envoyes, tokens.size(), premiereErreur);
        }

        // Le token n'est tracé que s'il est sans ambiguïté ; au-delà d'un appareil, la ligne
        // décrit l'événement et non un envoi particulier.
        String tokenTrace = tokens.size() == 1 ? tokens.get(0).getFcmToken() : null;
        String erreur = envoyes > 0 ? null
                : tokens.size() == 1 ? premiereErreur
                : String.format("%d appareils en échec — 1ʳᵉ erreur : %s", tokens.size(), premiereErreur);

        sauvegarder(parentId, tokenTrace, type, titre, message, sourceId, sourceType,
                    envoyes > 0 ? StatutEnvoi.ENVOYE : StatutEnvoi.ECHEC, erreur);
    }

    /**
     * Envoie la notification à un appareil précis.
     *
     * <p>N'historise plus rien : la persistance appartient à {@link #envoyerAuParent}, qui écrit
     * une ligne unique pour l'événement. La <b>désactivation d'un token rejeté reste ici</b>,
     * par appareil — c'est bien une propriété de l'appareil, et cette logique fonctionne déjà
     * (les deux faux tokens e2e du parent 31 ont été désactivés ainsi).
     *
     * @return {@code null} si l'envoi a réussi, sinon le motif de l'échec.
     */
    private String envoyerAuToken(String fcmToken, Long parentId,
                                  TypeNotification type, String titre,
                                  String message, Long sourceId, String sourceType) {

        // Firebase non configuré (placeholder JSON) → mode dégradé
        if (firebaseApp == null) {
            log.warn("[FCM] Firebase non configuré — notification simulée pour parent {}", parentId);
            log.warn("[FCM] Titre: {} | Message: {}", titre, message);
            return "Firebase non configuré — remplacer firebase-service-account.json";
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
            return null;

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

            return e.getMessage();
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
