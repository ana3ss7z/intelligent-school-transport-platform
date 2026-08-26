package ma.transport.ms4notifications.service;

import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

/**
 * BusLookupService — trouve le chauffeur affecté à un bus.
 *
 * Appelle MS1 (BusService) DIRECTEMENT (port 8081), sans passer par la Gateway :
 * MS4 n'a pas de token JWT utilisateur. La route GET /api/bus/{id}/chauffeur est
 * exemptée de JWT côté MS1 (SecurityConfig.permitAll) — interne au réseau.
 */
@Slf4j
@Service
public class BusLookupService {

    private final RestTemplate restTemplate;
    private final String ms1Url;

    public BusLookupService(
            RestTemplate restTemplate,
            @Value("${ms1.url:http://localhost:8081}") String ms1Url) {
        this.restTemplate = restTemplate;
        this.ms1Url = ms1Url;
    }

    /**
     * Ce compte conduit-il au moins un bus de la flotte ?
     *
     * <p>Sert à valider le destinataire d'un message de l'administration : la messagerie relie
     * l'administration aux chauffeurs, et un identifiant de parent ou un identifiant inexistant
     * ne doit pas y ouvrir de fil (défaut P15). Utilise {@code GET /api/bus/actifs}, déjà
     * exemptée de jeton côté MS1.
     *
     * <p><b>Échec fermé</b> : MS1 injoignable ⇒ on refuse plutôt que d'accepter à l'aveugle.
     */
    @SuppressWarnings("unchecked")
    public boolean estUnChauffeur(Long userId) {
        if (userId == null) {
            return false;
        }
        try {
            java.util.List<java.util.Map<String, Object>> bus =
                    restTemplate.getForObject(ms1Url + "/api/bus/actifs", java.util.List.class);
            if (bus == null) {
                return false;
            }
            return bus.stream().anyMatch(b -> {
                Object c = b.get("chauffeurId");
                return c instanceof Number && ((Number) c).longValue() == userId;
            });
        } catch (Exception e) {
            log.warn("[MS4] Impossible de valider le destinataire {} : {}", userId, e.getMessage());
            return false;
        }
    }

    /** Retourne le chauffeurId d'un bus, ou null si inaccessible/non affecté (dégradation gracieuse). */
    public Long getChauffeurParBus(Long busId) {
        try {
            Long chauffeurId = restTemplate.getForObject(
                    ms1Url + "/api/bus/" + busId + "/chauffeur", Long.class);
            log.debug("[MS4] chauffeur {} trouvé pour bus {}", chauffeurId, busId);
            return chauffeurId;
        } catch (Exception e) {
            log.warn("[MS4] Impossible de récupérer le chauffeur du bus {} : {}", busId, e.getMessage());
            return null;
        }
    }
}
