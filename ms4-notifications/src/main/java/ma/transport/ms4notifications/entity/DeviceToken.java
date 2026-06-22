package ma.transport.ms4notifications.entity;

import jakarta.persistence.*;
import lombok.*;
import java.time.LocalDateTime;

/**
 * DeviceToken — stocke les tokens FCM des appareils des parents.
 *
 * Quand un parent installe l'app mobile et se connecte,
 * l'app envoie son FCM token à MS4 via POST /api/notifications/device-token.
 * MS4 l'enregistre ici pour pouvoir envoyer des push notifications.
 */
@Entity
@Table(name = "device_tokens", indexes = {
    @Index(name = "idx_device_parent", columnList = "parent_id"),
    @Index(name = "idx_device_token",  columnList = "fcm_token", unique = true)
})
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class DeviceToken {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "parent_id", nullable = false)
    private Long parentId;

    @Column(name = "fcm_token", nullable = false, length = 500, unique = true)
    private String fcmToken;

    /** Android, iOS, Web */
    @Column(length = 20)
    @Builder.Default
    private String plateforme = "ANDROID";

    @Column(name = "date_enregistrement")
    @Builder.Default
    private LocalDateTime dateEnregistrement = LocalDateTime.now();

    @Column(name = "actif")
    @Builder.Default
    private Boolean actif = true;
}
