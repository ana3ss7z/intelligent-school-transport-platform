package ma.transport.ms1bus.dto;

import jakarta.validation.constraints.*;
import lombok.Data;
import ma.transport.ms1bus.enums.StatutBus;

@Data
public class BusRequest {

    @NotBlank(message = "Le matricule est obligatoire")
    private String matricule;

    @Min(value = 1, message = "La capacité doit être > 0")
    @Max(value = 100, message = "La capacité max est 100")
    private int capacite;

    private StatutBus statut = StatutBus.ACTIF;

    private Long chauffeurId;
}