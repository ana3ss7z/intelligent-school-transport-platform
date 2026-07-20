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
