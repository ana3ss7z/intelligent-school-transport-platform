package ma.transport.ms2eleves.dto;

import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

@Data
public class EleveRequest {

    @NotBlank
    private String nom;

    @NotBlank
    private String prenom;

    @NotNull
    @DecimalMin("-90.0") @DecimalMax("90.0")
    private Double latitude;

    @NotNull
    @DecimalMin("-180.0") @DecimalMax("180.0")
    private Double longitude;

    private Long parentId;

    /** Assignation directe d'un bus (ex: résultat clustering MS6) */
    private Long busId;

    /** Groupe géographique (résultat K-Means MS6) */
    private Long groupeId;

    /** Rang de passage dans la tournée (résultat VRP MS5) */
    private Integer ordrePassage;
}