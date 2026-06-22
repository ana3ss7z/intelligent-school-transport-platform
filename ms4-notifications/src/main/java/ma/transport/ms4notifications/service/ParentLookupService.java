package ma.transport.ms4notifications.service;

import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpMethod;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.util.Collections;
import java.util.List;

/**
 * ParentLookupService — trouve les parents des élèves d'un bus.
 *
 * Appelle MS2 (EleveService) DIRECTEMENT (port 8082), sans passer par
 * la Gateway (MS8). Communication service-à-service interne : MS4 n'a
 * pas de token JWT utilisateur, donc passer par la Gateway provoquerait
 * un 401 (toutes les routes /api/eleves/** y exigent un Bearer token).
 *
 * La route GET /api/eleves/bus/{busId}/parents est exemptée de JWT
 * côté MS2 (SecurityConfig.permitAll) — elle est interne au réseau et
 * jamais exposée directement à un client externe.
 *
 * IMPORTANT — typage : on utilise ParameterizedTypeReference<List<Long>>
 * au lieu de List.class. Sans ça, Jackson désérialise les petits nombres
 * JSON en Integer plutôt que Long, ce qui casse un cast direct (Long) plus
 * loin dans le code avec une ClassCastException.
 */
@Slf4j
@Service
public class ParentLookupService {

    private final RestTemplate restTemplate;
    private final String ms2Url;

    public ParentLookupService(
            RestTemplate restTemplate,
            @Value("${ms2.url:http://localhost:8082}") String ms2Url) {
        this.restTemplate = restTemplate;
        this.ms2Url       = ms2Url;
    }

    /**
     * Retourne la liste des parentId pour un bus donné.
     * Si MS2 est inaccessible, retourne une liste vide (graceful degradation).
     */
    public List<Long> getParentsParBus(Long busId) {
        try {
            String url = ms2Url + "/api/eleves/bus/" + busId + "/parents";

            ResponseEntity<List<Long>> response = restTemplate.exchange(
                    url,
                    HttpMethod.GET,
                    null,
                    new ParameterizedTypeReference<List<Long>>() {}
            );

            List<Long> parents = response.getBody();
            log.debug("[MS4] {} parents trouvés pour bus {}",
                      parents != null ? parents.size() : 0, busId);
            return parents != null ? parents : Collections.emptyList();

        } catch (Exception e) {
            log.warn("[MS4] Impossible de récupérer les parents du bus {} : {}", busId, e.getMessage());
            return Collections.emptyList();
        }
    }
}