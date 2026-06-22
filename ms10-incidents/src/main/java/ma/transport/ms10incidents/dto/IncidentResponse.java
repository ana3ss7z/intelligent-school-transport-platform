package ma.transport.ms10incidents.dto;

import lombok.*;
import ma.transport.ms10incidents.entity.Incident;
import ma.transport.ms10incidents.entity.Incident.StatutIncident;
import ma.transport.ms10incidents.entity.Incident.TypeIncident;

import java.time.LocalDateTime;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class IncidentResponse {

    private Long           id;
    private TypeIncident   type;
    private StatutIncident statut;
    private Long           busId;
    private Long           signalePar;
    private String         description;
    private Double         latitude;
    private Double         longitude;
    private LocalDateTime  dateSignalement;
    private LocalDateTime  dateResolution;
    private String         notesResolution;

    public static IncidentResponse from(Incident i) {
        return IncidentResponse.builder()
                .id(i.getId())
                .type(i.getType())
                .statut(i.getStatut())
                .busId(i.getBusId())
                .signalePar(i.getSignalePar())
                .description(i.getDescription())
                .latitude(i.getLatitude())
                .longitude(i.getLongitude())
                .dateSignalement(i.getDateSignalement())
                .dateResolution(i.getDateResolution())
                .notesResolution(i.getNotesResolution())
                .build();
    }
}
