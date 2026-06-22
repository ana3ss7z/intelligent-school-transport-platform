package ma.transport.ms10incidents.dto;

import jakarta.validation.constraints.*;
import lombok.*;
import ma.transport.ms10incidents.entity.Incident;
import ma.transport.ms10incidents.entity.Incident.StatutIncident;
import ma.transport.ms10incidents.entity.Incident.TypeIncident;

import java.time.LocalDateTime;

@Data
public class StatutRequest {

    @NotNull(message = "Le statut est obligatoire")
    private StatutIncident statut;

    @Size(max = 500)
    private String notesResolution;
}
