package ma.transport.ms10incidents.entity;

import jakarta.persistence.*;
import lombok.*;
import java.time.LocalDateTime;

/**
 * Entité Incident
 * ===============
 * Représente un incident survenu sur un bus ou un trajet.
 *
 * Flow statuts :
 *   SIGNALE → CONFIRME → EN_TRAITEMENT → RESOLU
 *
 * Transitions RabbitMQ :
 *   SIGNALE  → publie incident.signale
 *   RESOLU   → publie incident.resolu  (→ MS4 notifie les parents)
 */
@Entity
@Table(name = "incidents", indexes = {
    @Index(name = "idx_incident_bus",    columnList = "bus_id"),
    @Index(name = "idx_incident_statut", columnList = "statut"),
    @Index(name = "idx_incident_date",   columnList = "date_signalement DESC")
})
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Incident {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    /** Type d'incident */
    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private TypeIncident type;

    /** Statut courant */
    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    @Builder.Default
    private StatutIncident statut = StatutIncident.SIGNALE;

    /** Bus concerné */
    @Column(name = "bus_id", nullable = false)
    private Long busId;

    /** Chauffeur qui a signalé (userId MS7) */
    @Column(name = "signale_par")
    private Long signalePar;

    /** Description libre */
    @Column(length = 1000)
    private String description;

    /** Latitude de l'incident (optionnel) */
    private Double latitude;

    /** Longitude de l'incident (optionnel) */
    private Double longitude;

    @Column(name = "date_signalement", nullable = false)
    @Builder.Default
    private LocalDateTime dateSignalement = LocalDateTime.now();

    @Column(name = "date_resolution")
    private LocalDateTime dateResolution;

    /** Notes de résolution */
    @Column(name = "notes_resolution", length = 500)
    private String notesResolution;

    // ─── Enums ───────────────────────────────────────────────────────────────

    public enum TypeIncident {
        ACCIDENT,
        PANNE,
        RETARD,
        ABSENCE_CHAUFFEUR,
        ROUTE_BLOQUEE,
        AUTRE
    }

    public enum StatutIncident {
        SIGNALE,       // Incident signalé, en attente de confirmation
        CONFIRME,      // Confirmé par l'admin
        EN_TRAITEMENT, // Action en cours (remplacement, dépannage...)
        RESOLU         // Clôturé → déclenche notification parents via RabbitMQ
    }
}
