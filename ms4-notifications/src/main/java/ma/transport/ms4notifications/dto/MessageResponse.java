package ma.transport.ms4notifications.dto;

import java.time.LocalDateTime;

import lombok.Builder;
import lombok.Data;
import ma.transport.ms4notifications.entity.Message;

@Data
@Builder
public class MessageResponse {
    private Long id;
    private Long conversationChauffeurId;
    private Long expediteurId;
    private String expediteurNom;
    private String expediteurRole;
    private Long destinataireId;
    private String destinataireRole;
    private String contenu;
    private boolean lu;
    private LocalDateTime dateEnvoi;

    public static MessageResponse from(Message m) {
        return MessageResponse.builder()
                .id(m.getId())
                .conversationChauffeurId(m.getConversationChauffeurId())
                .expediteurId(m.getExpediteurId())
                .expediteurNom(m.getExpediteurNom())
                .expediteurRole(m.getExpediteurRole())
                .destinataireId(m.getDestinataireId())
                .destinataireRole(m.getDestinataireRole())
                .contenu(m.getContenu())
                .lu(m.isLu())
                .dateEnvoi(m.getDateEnvoi())
                .build();
    }
}
