package ma.transport.ms1bus.entity;

import java.time.LocalDateTime;

import jakarta.persistence.*;
import lombok.*;

/** Trajet démarré par un chauffeur sur son bus (matin/soir). */
@Entity
@Table(name = "trajets")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Trajet {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false)
    private Long busId;

    @Column(nullable = false)
    private Long chauffeurId;

    /** Groupe/clustering du bus au démarrage (référence pour la surveillance de déviation MS11). */
    private Long groupeId;

    /** Géométrie de la tournée planifiée (JSON [[lat,lng],…], OSRM) — figée au démarrage, surveillée par MS11. */
    @Column(columnDefinition = "TEXT")
    private String geometrie;

    /**
     * Totaux OSRM de la tournée planifiée (MS5), figés au démarrage avec la géométrie.
     * Servent à dériver la vitesse moyenne réelle du circuit → ETA « distance restante
     * le long de la tournée » côté chauffeur ET parent (sinon le parent devrait deviner
     * une vitesse). Nullables : un trajet démarré sans tournée reste valide.
     */
    private Double distancePlanM;
    private Double dureePlanMin;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private Sens sens;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private StatutTrajet statut;

    private LocalDateTime heureDebut;
    private LocalDateTime heureFin;

    public enum Sens { MATIN, SOIR }
    public enum StatutTrajet { EN_COURS, TERMINE }
}
