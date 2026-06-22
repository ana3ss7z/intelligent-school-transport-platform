package ma.transport.ms3localisation.dto;

import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import lombok.Data;
import ma.transport.ms3localisation.entity.PositionGPS.TypeCible;

// ─── Request : publier une position ──────────────────────────────────────────
@Data
public class PositionRequest {

    @NotNull(message = "Le type de cible est obligatoire")
    private TypeCible cibleType;

    @NotNull(message = "L'ID de la cible est obligatoire")
    @Positive
    private Long cibleId;

    @NotNull
    @DecimalMin(value = "-90.0",  message = "Latitude invalide")
    @DecimalMax(value = "90.0",   message = "Latitude invalide")
    private Double latitude;

    @NotNull
    @DecimalMin(value = "-180.0", message = "Longitude invalide")
    @DecimalMax(value = "180.0",  message = "Longitude invalide")
    private Double longitude;

    @DecimalMin("0.0") @DecimalMax("300.0")
    private Double vitesse;

    @DecimalMin("0.0") @DecimalMax("360.0")
    private Double cap;

    @DecimalMin("0.0")
    private Double precision;
}