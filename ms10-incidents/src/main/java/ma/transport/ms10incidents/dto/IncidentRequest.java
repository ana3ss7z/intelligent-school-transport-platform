package ma.transport.ms10incidents.dto;

import jakarta.validation.constraints.*;
import lombok.Data;
import ma.transport.ms10incidents.entity.Incident.TypeIncident;

@Data
public class IncidentRequest {

    @NotNull(message = "Le type d'incident est obligatoire")
    private TypeIncident type;

    @NotNull(message = "L'ID du bus est obligatoire")
    @Positive
    private Long busId;

    @NotBlank(message = "La description est obligatoire")
    @Size(max = 1000)
    private String description;

    @DecimalMin(value = "-90.0",  message = "Latitude invalide")
    @DecimalMax(value = "90.0",   message = "Latitude invalide")
    private Double latitude;

    @DecimalMin(value = "-180.0", message = "Longitude invalide")
    @DecimalMax(value = "180.0",  message = "Longitude invalide")
    private Double longitude;
}
