package ma.transport.ms3localisation.entity;

import java.time.LocalDateTime;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
import jakarta.persistence.Table;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * Entité PositionGPS — historique complet des positions.
 *
 * Chaque mise à jour GPS génère une nouvelle ligne (append-only).
 * La dernière position est aussi mise en cache Redis pour accès temps réel.
 *
 * Deux types de cibles : BUS ou ELEVE
 */
@Entity
@Table(name = "positions_gps",
       indexes = {
           @Index(name = "idx_position_cible",   columnList = "cible_type, cible_id"),
           @Index(name = "idx_position_horodatage", columnList = "horodatage DESC")
       })
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class PositionGPS {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    /** Type de la cible : BUS ou ELEVE */
    @Enumerated(EnumType.STRING)
    @Column(name = "cible_type", nullable = false)
    private TypeCible cibleType;

    /** ID du bus ou de l'élève */
    @Column(name = "cible_id", nullable = false)
    private Long cibleId;

    @Column(nullable = false)
    private Double latitude;

    @Column(nullable = false)
    private Double longitude;

    /** Vitesse en km/h (null si non disponible) */
    private Double vitesse;

    /** Cap en degrés 0-360 (null si non disponible) */
    private Double cap;

    /** Précision GPS en mètres */
    private Double precision;

    @Column(nullable = false)
    @Builder.Default
    private LocalDateTime horodatage = LocalDateTime.now();

    public enum TypeCible {
        BUS, ELEVE
    }
}