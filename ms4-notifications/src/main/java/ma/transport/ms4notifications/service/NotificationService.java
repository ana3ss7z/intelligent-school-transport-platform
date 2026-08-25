package ma.transport.ms4notifications.service;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import ma.transport.ms4notifications.dto.DeviceTokenRequest;
import ma.transport.ms4notifications.dto.NotificationResponse;
import ma.transport.ms4notifications.dto.PageResponse;
import ma.transport.ms4notifications.entity.DeviceToken;
import ma.transport.ms4notifications.entity.Notification.StatutEnvoi;
import ma.transport.ms4notifications.entity.Notification.TypeNotification;
import ma.transport.ms4notifications.repository.DeviceTokenRepository;
import ma.transport.ms4notifications.repository.NotificationRepository;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Map;
import java.util.Set;
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
                .plateforme(normaliserPlateforme(req.getPlateforme()))
                .actif(true)
                .build();

        deviceTokenRepo.save(token);
        log.info("[MS4] Token FCM enregistré — parentId={} plateforme={}", parentId, token.getPlateforme());
    }

    /**
     * Normalise la plateforme déclarée par le client.
     *
     * <p>{@code DeviceToken.plateforme} porte bien un {@code @Builder.Default} à
     * {@code "ANDROID"}, mais {@link #enregistrerToken} appelle le constructeur de façon
     * explicite : passer {@code null} <b>écrase</b> le défaut. Un client web qui omettait le
     * champ s'enregistrait donc avec une plateforme nulle.
     *
     * <p>Le repli est volontairement {@code "INCONNU"} et non {@code "ANDROID"} : maintenant
     * que des clients web, Android et mobile coexistent, deviner la plateforme reviendrait à
     * étiqueter faussement la moitié du parc. Le champ ne sert qu'au diagnostic — autant qu'il
     * dise la vérité.
     */
    private static String normaliserPlateforme(String brut) {
        if (brut == null || brut.isBlank()) return "INCONNU";
        return brut.trim().toUpperCase();
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

    /** Types dont le destinataire est l'administration (parentId null). */
    private static final Set<TypeNotification> TYPES_ADMIN = Set.of(
            TypeNotification.ALERTE_QUALITE,
            TypeNotification.ANOMALIE_DETECTEE);

    /**
     * Champs sur lesquels le tri est autorisé.
     *
     * <p>Liste blanche volontaire : {@code Sort.by} accepte n'importe quelle chaîne et échoue à
     * l'exécution sur une propriété inconnue. Un nom de colonne venu du client produirait donc
     * un 500 — et exposerait la structure de l'entité au passage.
     */
    private static final Set<String> TRIS_AUTORISES = Set.of("id", "type", "statutEnvoi", "dateEnvoi");

    private static final int TAILLE_PAGE_MAX = 500;

    /**
     * Journal d'administration, paginé côté serveur.
     *
     * <p>Remplace un {@code findAll()} non borné. Le plafond {@link #TAILLE_PAGE_MAX} borne aussi
     * l'export CSV, qui demande une grande page en une fois plutôt que de tout charger à chaque
     * sondage.
     */
    public PageResponse<NotificationResponse> getToutesNotifications(
            int page, int size, String tri, String sens, boolean adminSeulement) {

        String champ = TRIS_AUTORISES.contains(tri) ? tri : "id";
        Sort.Direction dir = "asc".equalsIgnoreCase(sens) ? Sort.Direction.ASC : Sort.Direction.DESC;
        Pageable pageable = PageRequest.of(
                Math.max(page, 0),
                Math.min(Math.max(size, 1), TAILLE_PAGE_MAX),
                Sort.by(dir, champ));

        return PageResponse.from(
                adminSeulement ? notifRepo.findByTypeIn(TYPES_ADMIN, pageable) : notifRepo.findAll(pageable),
                NotificationResponse::from);
    }

    // ── Stats (bugfix echecs=0) ───────────────────────────────────────

    public Map<String, Long> getStats() {
        return Map.of(
            "total",   notifRepo.count(),
            "envoyes", notifRepo.countByStatutEnvoi(StatutEnvoi.ENVOYE),
            "echecs",  notifRepo.countByStatutEnvoi(StatutEnvoi.ECHEC),
            "attente", notifRepo.countByStatutEnvoi(StatutEnvoi.EN_ATTENTE),
            // Comptée en base : la console ne voit plus qu'une page, elle ne peut plus
            // dériver ce total en filtrant la liste qu'elle a reçue.
            "alertesAdmin", notifRepo.countByTypeIn(TYPES_ADMIN)
        );
    }

    // ── Envoi (appelé par les consumers RabbitMQ) ─────────────────────

    public void envoyerAuParent(Long parentId, TypeNotification type,
                                 String titre, String message,
                                 Long sourceId, String sourceType) {
        fcmService.envoyerAuParent(parentId, type, titre, message, sourceId, sourceType);
    }
}