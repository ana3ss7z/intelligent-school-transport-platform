package ma.transport.ms4notifications.dto;

import java.time.LocalDateTime;

import lombok.Builder;
import lombok.Data;

/** Résumé d'un fil de discussion pour la liste admin. */
@Data
@Builder
public class ConversationResponse {
    private Long chauffeurId;
    private String chauffeurNom;      // dernier nom connu de l'expéditeur chauffeur (si dispo)
    private String dernierMessage;
    private LocalDateTime dateDernier;
    private long nonLus;              // non-lus côté admin
}
