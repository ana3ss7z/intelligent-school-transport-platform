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

import java.time.LocalDateTime;
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

    /**
     * Enregistre — ou réactive — le token FCM d'un appareil.
     *
     * <p><b>L'opération doit être idempotente</b>, et ne l'était pas. La version précédente
     * désactivait la ligne existante <i>sans la supprimer</i>, puis en insérait une nouvelle
     * portant le même token ; or {@code fcm_token} porte une <b>contrainte UNIQUE</b>
     * ({@code idx_device_token}). Toute seconde inscription du même token violait donc la
     * contrainte.
     *
     * <p>Ce n'est pas un cas limite : un token FCM est <b>stable pour une installation</b>
     * (ou un profil de navigateur). La deuxième connexion depuis le même appareil échouait,
     * et le parent restait sans push sans que rien ne l'indique côté client.
     *
     * <p>Le token appartient à l'<b>appareil</b>, pas au compte : quand un autre utilisateur
     * se connecte depuis le même navigateur, la ligne est <b>réaffectée</b>. C'est le cas
     * courant dans ce projet, où la console web sert les rôles parent et chauffeur sur une
     * seule origine — donc un seul service worker, donc un seul token.
     */
    @Transactional
    public void enregistrerToken(Long parentId, DeviceTokenRequest req) {
        String plateforme = normaliserPlateforme(req.getPlateforme());

        DeviceToken token = deviceTokenRepo.findByFcmToken(req.getFcmToken())
                .map(existant -> {
                    existant.setParentId(parentId);
                    existant.setPlateforme(plateforme);
                    existant.setActif(true);
                    existant.setDateEnregistrement(LocalDateTime.now());
                    return existant;
                })
                .orElseGet(() -> DeviceToken.builder()
                        .parentId(parentId)
                        .fcmToken(req.getFcmToken())
                        .plateforme(plateforme)
                        .actif(true)
                        .build());

        deviceTokenRepo.save(token);
        log.info("[MS4] Token FCM enregistré — parentId={} plateforme={}", parentId, plateforme);
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
    /**
     * Desactive un jeton d'appareil — <b>uniquement s'il appartient au demandeur</b>.
     *
     * <p>Un jeton identifie un appareil, mais il est porte par un compte : le desactiver coupe
     * les notifications de ce compte. La version precedente le desactivait sur sa seule valeur,
     * sans verifier le proprietaire (defaut P13 de la recette du 26/08).
     */
    public void supprimerToken(String fcmToken, Long demandeurId) {
        deviceTokenRepo.findByFcmToken(fcmToken).ifPresent(device -> {
            if (demandeurId != null && !demandeurId.equals(device.getParentId())) {
                log.warn("[MS4] Desactivation refusee : le jeton appartient a {}, demandee par {}",
                        device.getParentId(), demandeurId);
                throw new org.springframework.web.server.ResponseStatusException(
                        org.springframework.http.HttpStatus.FORBIDDEN,
                        "Ce jeton d'appareil ne vous appartient pas.");
            }
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