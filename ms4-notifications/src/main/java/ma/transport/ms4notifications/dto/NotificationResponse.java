package ma.transport.ms4notifications.dto;

import lombok.*;
import ma.transport.ms4notifications.entity.Notification;
import ma.transport.ms4notifications.entity.Notification.StatutEnvoi;
import ma.transport.ms4notifications.entity.Notification.TypeNotification;

import java.time.LocalDateTime;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class NotificationResponse {

    private Long              id;
    private TypeNotification  type;
    private StatutEnvoi       statutEnvoi;
    private Long              parentId;
    private String            titre;
    private String            message;
    private Long              sourceId;
    private String            sourceType;
    private LocalDateTime     dateEnvoi;
    private String            erreurFcm;

    public static NotificationResponse from(Notification n) {
        return NotificationResponse.builder()
                .id(n.getId())
                .type(n.getType())
                .statutEnvoi(n.getStatutEnvoi())
                .parentId(n.getParentId())
                .titre(n.getTitre())
                .message(n.getMessage())
                .sourceId(n.getSourceId())
                .sourceType(n.getSourceType())
                .dateEnvoi(n.getDateEnvoi())
                .erreurFcm(n.getErreurFcm())
                .build();
    }
}
