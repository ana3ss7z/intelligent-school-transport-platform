package ma.transport.ms4notifications.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

/** Message libre envoyé par l'admin à un utilisateur (chauffeur). */
@Data
public class MessageRequest {
    @NotNull
    private Long destinataireId;
    @NotBlank
    private String titre;
    @NotBlank
    private String message;
}
