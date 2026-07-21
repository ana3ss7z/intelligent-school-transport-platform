package ma.transport.ms4notifications.entity;

import jakarta.persistence.*;
import lombok.*;
import java.time.LocalDateTime;

/**
 * Message — messagerie humain↔humain (chauffeur ↔ administration).
 *
 * Une conversation est identifiée par le chauffeur (conversationChauffeurId). Le côté admin est
 * « l'administration » (rôle ADMIN, n'importe quel admin lit/répond). Séparé des Notification (événements système).
 */
@Entity
@Table(name = "messages", indexes = {
    @Index(name = "idx_msg_conv",  columnList = "conversation_chauffeur_id"),
    @Index(name = "idx_msg_dest",  columnList = "destinataire_role"),
    @Index(name = "idx_msg_date",  columnList = "date_envoi")
})
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Message {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    /** Chauffeur du fil de discussion (clé de conversation). */
    @Column(name = "conversation_chauffeur_id", nullable = false)
    private Long conversationChauffeurId;

    @Column(name = "expediteur_id", nullable = false)
    private Long expediteurId;

    @Column(name = "expediteur_nom")
    private String expediteurNom;

    @Column(name = "expediteur_role", nullable = false, length = 20)
    private String expediteurRole;

    /** Destinataire précis (le chauffeur) ; null si adressé au rôle ADMIN (l'administration). */
    @Column(name = "destinataire_id")
    private Long destinataireId;

    @Column(name = "destinataire_role", nullable = false, length = 20)
    private String destinataireRole;

    @Column(columnDefinition = "TEXT", nullable = false)
    private String contenu;

    /** Diffusion chauffeur → parents du groupe (séparée des fils chauffeur↔admin). */
    @Column(nullable = false)
    @Builder.Default
    private boolean diffusion = false;

    @Column(nullable = false)
    @Builder.Default
    private boolean lu = false;

    @Column(name = "date_envoi", nullable = false)
    @Builder.Default
    private LocalDateTime dateEnvoi = LocalDateTime.now();
}
