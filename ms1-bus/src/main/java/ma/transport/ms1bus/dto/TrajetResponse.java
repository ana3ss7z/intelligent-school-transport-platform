package ma.transport.ms1bus.dto;

import java.time.LocalDateTime;

import lombok.Builder;
import lombok.Data;
import ma.transport.ms1bus.entity.Trajet.Sens;
import ma.transport.ms1bus.entity.Trajet.StatutTrajet;

@Data
@Builder
public class TrajetResponse {
    private Long id;
    private Long busId;
    private String matricule;
    private Long chauffeurId;
    private Long groupeId;
    private Sens sens;
    private StatutTrajet statut;
    private LocalDateTime heureDebut;
    private LocalDateTime heureFin;
}
