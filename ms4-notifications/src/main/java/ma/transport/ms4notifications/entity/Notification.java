package ma.transport.ms4notifications.entity;

import jakarta.persistence.*;
import lombok.*;
import java.time.LocalDateTime;

/**
 * Entité Notification — historique complet de toutes les notifications envoyées.
 *
 * Chaque notification est liée à un parent (destinataire) et contient
 * le statut d'envoi FCM pour audit et retry éventuel.
 */
@Entity
@Table(name = "notifications", indexes = {
    @Index(name = "idx_notif_parent",    columnList = "parent_id"),
    @Index(name = "idx_notif_type",      columnList = "type"),
    @Index(name = "idx_notif_date",      columnList = "date_envoi DESC"),
    @Index(name = "idx_notif_statut",    columnList = "statut_envoi")
})
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Notification {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    /** Type d'événement déclencheur */
    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private TypeNotification type;

    /** Statut envoi FCM */
    @Enumerated(EnumType.STRING)
    @Column(name = "statut_envoi", nullable = false)
    @Builder.Default
    private StatutEnvoi statutEnvoi = StatutEnvoi.EN_ATTENTE;

    /** ID du parent destinataire (userId MS7) */
    @Column(name = "parent_id")
    private Long parentId;

    /** FCM token du device parent (enregistré lors du login app mobile) */
    @Column(name = "fcm_token", length = 500)
    private String fcmToken;

    /** Titre de la notification push */
    @Column(nullable = false)
    private String titre;

    /** Corps du message */
    @Column(length = 500, nullable = false)
    private String message;

    /** ID de l'entité source (busId, incidentId...) */
    @Column(name = "source_id")
    private Long sourceId;

    /** Type source : BUS, INCIDENT */
    @Column(name = "source_type", length = 50)
    private String sourceType;

    @Column(name = "date_envoi", nullable = false)
    @Builder.Default
    private LocalDateTime dateEnvoi = LocalDateTime.now();

    /** Message d'erreur FCM si échec */
    @Column(name = "erreur_fcm", length = 500)
    private String erreurFcm;

    // ─── Enums ───────────────────────────────────────────────────────────────

    public enum TypeNotification {
        INCIDENT_SIGNALE,   // Un incident a été signalé sur le bus de l'enfant
        INCIDENT_RESOLU,    // L'incident est résolu, le bus repart
        BUS_ARRIVE_ECOLE,   // Le bus est arrivé à l'école
        BUS_EN_ROUTE,       // Le bus a démarré son circuit
        RETARD,             // Le bus est en retard
        ENFANT_A_BORD,      // L'enfant est bien monté dans le bus (présence confirmée)
        ENFANT_DEPOSE,      // L'enfant a été déposé à son arrêt (dépose du soir)
        ALERTE_QUALITE,     // Alerte admin : qualité de clustering dégradée (MS6)
        ANOMALIE_DETECTEE,  // Alerte admin : anomalie GPS détectée (MS11)
        TRAJET_DEMARRE,     // Alerte admin : un chauffeur a démarré un trajet
        TRAJET_TERMINE,     // Alerte admin : un chauffeur a terminé un trajet
        MESSAGE_ADMIN       // Message libre envoyé par l'admin à un chauffeur
    }

    public enum StatutEnvoi {
        EN_ATTENTE,   // Pas encore envoyé
        ENVOYE,       // FCM a accepté le message
        ECHEC         // FCM a retourné une erreur
    }
}
