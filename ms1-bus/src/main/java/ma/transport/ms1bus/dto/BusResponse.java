package ma.transport.ms1bus.dto;

import lombok.*;
import ma.transport.ms1bus.enums.StatutBus;

@Data
@Builder
@AllArgsConstructor
@NoArgsConstructor
public class BusResponse {
    private Long id;
    private String matricule;
    private int capacite;
    private StatutBus statut;
    private Long chauffeurId;
    private Double latitude;
    private Double longitude;
    private int capaciteRestante; // calculé dynamiquement
}