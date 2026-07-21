package ma.transport.ms4notifications.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

/**
 * Envoi d'un message de messagerie.
 * - Admin : destinataireId = le chauffeur (requis).
 * - Chauffeur : destinataireId ignoré (adressé à l'administration).
 */
@Data
public class MessageRequest {
    private Long destinataireId;
    @NotBlank
    private String contenu;
}
