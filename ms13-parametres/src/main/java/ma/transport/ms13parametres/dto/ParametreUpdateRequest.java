package ma.transport.ms13parametres.dto;

import jakarta.validation.constraints.NotEmpty;
import lombok.Data;

import java.util.Map;

/**
 * Écriture par lot : {@code {"valeurs": {"ms11.seuil_deviation_m": "120", …}}}.
 *
 * <p>Le lot est volontairement atomique — l'admin enregistre un onglet entier. Si une seule
 * valeur est refusée, aucune n'est écrite : à moitié appliqué, un réglage de seuils est pire
 * qu'un réglage refusé.
 */
@Data
public class ParametreUpdateRequest {

    @NotEmpty(message = "aucune valeur fournie")
    private Map<String, String> valeurs;
}
