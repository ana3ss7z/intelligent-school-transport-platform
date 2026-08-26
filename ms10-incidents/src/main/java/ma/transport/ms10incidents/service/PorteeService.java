package ma.transport.ms10incidents.service;

import java.util.Collections;
import java.util.Set;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.server.ResponseStatusException;

import lombok.extern.slf4j.Slf4j;
import ma.transport.mscommon.enums.Role;
import ma.transport.mscommon.security.UserPrincipal;

/**
 * Controle de <b>portee</b> : ce compte a-t-il le droit d'agir sur <b>ce bus</b> ?
 *
 * <p>Deux defauts vivaient ici. {@code GET /api/incidents/bus/{id}} etait ouvert au role PARENT
 * avec, en commentaire, « la portee est appliquee en amont par MS9 » : vrai pour le chatbot,
 * faux pour un appel HTTP direct — tout parent lisait les incidents de toute la flotte
 * (defaut P6). Et {@code POST /api/incidents} prend le {@code busId} dans le corps sans le
 * confronter au bus du chauffeur : un signalement sur le bus d'un collegue declenchait une
 * alerte aux parents de <b>ce</b> bus (defaut P5).
 *
 * <p>MS10 ne connait ni les bus ni les eleves : il interroge les routes internes de MS1 et MS2.
 *
 * <p><b>Echec ferme</b> : dependance injoignable ⇒ refus.
 */
@Slf4j
@Service
public class PorteeService {

    private final RestTemplate restTemplate = new RestTemplate();
    private final String ms1Url;
    private final String ms2Url;

    public PorteeService(@Value("${ms1.url:http://localhost:8081}") String ms1Url,
                         @Value("${ms2.url:http://localhost:8082}") String ms2Url) {
        this.ms1Url = ms1Url;
        this.ms2Url = ms2Url;
    }

    /** Bus que ce compte peut consulter. {@code null} = aucune restriction (ADMIN). */
    public Set<Long> busAutorises(UserPrincipal user) {
        if (user == null || user.getRole() == null) {
            return Collections.emptySet();
        }
        if (user.getRole() == Role.ADMIN) {
            return null;
        }
        try {
            String url = user.getRole() == Role.CHAUFFEUR
                    ? ms1Url + "/internal/bus/chauffeur/" + user.getUserId()
                    : ms2Url + "/internal/parents/" + user.getUserId() + "/bus";
            Long[] bus = restTemplate.getForObject(url, Long[].class);
            return bus == null ? Collections.emptySet() : Set.of(bus);
        } catch (Exception e) {
            log.warn("[MS10] Portee indeterminable pour l'utilisateur {} ({}) - acces refuse",
                    user.getUserId(), e.getMessage());
            return Collections.emptySet();
        }
    }

    /** Leve 403 si le bus ne concerne pas ce compte. */
    public void exigerAccesAuBus(UserPrincipal user, Long busId) {
        Set<Long> autorises = busAutorises(user);
        if (autorises == null || (busId != null && autorises.contains(busId))) {
            return;
        }
        throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Ce bus ne vous concerne pas.");
    }
}
