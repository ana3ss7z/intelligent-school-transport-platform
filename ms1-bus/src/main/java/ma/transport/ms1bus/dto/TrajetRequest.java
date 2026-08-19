package ma.transport.ms1bus.dto;

import java.util.List;

import jakarta.validation.constraints.NotNull;
import lombok.Data;
import ma.transport.ms1bus.entity.Trajet.Sens;

@Data
public class TrajetRequest {
    @NotNull
    private Long busId;
    @NotNull
    private Sens sens;

    /** Groupe/clustering du bus (optionnel) — figé sur le trajet pour la surveillance MS11. */
    private Long groupeId;

    /** Géométrie de la tournée planifiée [[lat,lng],…] (optionnel) — envoyée par le front chauffeur. */
    private List<List<Double>> geometrie;

    /** Totaux OSRM de cette tournée (MS5) — vitesse moyenne du circuit pour l'ETA restant. */
    private Double distancePlanM;
    private Double dureePlanMin;
}
