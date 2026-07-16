package ma.transport.ms2eleves.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Entity
@Table(name = "eleves")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Eleve {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false)
    private String nom;

    @Column(nullable = false)
    private String prenom;

    @Column(nullable = false)
    private Double latitude;

    @Column(nullable = false)
    private Double longitude;

    private Long parentId;

    /** Réservé pour MS6 (clustering géographique futur) */
    private Long groupeId;

    /** Lien direct vers le bus assigné (MS1) — utilisé par MS4 pour les notifications */
    private Long busId;

    @Column(nullable = false, columnDefinition = "boolean default false")
    @Builder.Default
    private Boolean statutPresence = false;

    /** Rang de passage dans la tournée du bus (persisté par MS5-VRP) — 1..n, null si non planifié */
    private Integer ordrePassage;
}