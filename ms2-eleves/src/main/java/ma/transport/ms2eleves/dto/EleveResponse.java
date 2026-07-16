package ma.transport.ms2eleves.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@AllArgsConstructor
@NoArgsConstructor
public class EleveResponse {
    private Long id;
    private String nom;
    private String prenom;
    private Double latitude;
    private Double longitude;
    private Long parentId;
    private Long groupeId;
    private Long busId;
    private Boolean statutPresence;
    private Integer ordrePassage;
}