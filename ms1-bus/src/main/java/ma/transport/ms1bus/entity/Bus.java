package ma.transport.ms1bus.entity;

import jakarta.persistence.*;
import lombok.*;
import ma.transport.ms1bus.enums.StatutBus;

@Entity
@Table(name = "bus")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Bus {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, unique = true)
    private String matricule;

    @Column(nullable = false)
    private int capacite;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private StatutBus statut;

    // ID du chauffeur assigné (référence vers MS2 utilisateurs)
    private Long chauffeurId;

    // Dernière position connue
    private Double latitude;
    private Double longitude;
}
