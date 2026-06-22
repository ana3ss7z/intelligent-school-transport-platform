package ma.transport.ms3localisation.dto;

import java.time.LocalDateTime;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import ma.transport.ms3localisation.entity.PositionGPS;
import ma.transport.ms3localisation.entity.PositionGPS.TypeCible;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class PositionResponse {

    private Long id;
    private TypeCible cibleType;
    private Long cibleId;
    private Double latitude;
    private Double longitude;
    private Double vitesse;
    private Double cap;
    private Double precision;
    private LocalDateTime horodatage;

    public static PositionResponse from(PositionGPS p) {
        return PositionResponse.builder()
                .id(p.getId())
                .cibleType(p.getCibleType())
                .cibleId(p.getCibleId())
                .latitude(p.getLatitude())
                .longitude(p.getLongitude())
                .vitesse(p.getVitesse())
                .cap(p.getCap())
                .precision(p.getPrecision())
                .horodatage(p.getHorodatage())
                .build();
    }
}