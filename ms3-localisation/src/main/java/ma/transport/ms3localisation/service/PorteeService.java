package ma.transport.ms3localisation.service;

import java.util.Collections;
import java.util.List;
import java.util.Set;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.server.ResponseStatusException;

import lombok.extern.slf4j.Slf4j;
import ma.transport.ms3localisation.dto.PositionResponse;
import ma.transport.mscommon.enums.Role;
import ma.transport.mscommon.security.UserPrincipal;

/**
 * Contrôle de <b>portée</b> : ce compte a-t-il le droit d'agir sur <b>ce bus</b> ?
 *
 * <p>Le rôle ne suffit pas. Ouvrir une lecture au rôle PARENT autorise n'importe quel parent à
 * lire n'importe quel bus, y compris celui d'une autre famille. C'est la classe de défauts que
 * la recette du 26/08 a trouvée en quantité (P1 à P15) : l'autorisation était vérifiée, la
 * propriété jamais.
 *
 * <p>MS3 ne connaît ni la table des élèves ni celle des bus. Il interroge donc les routes
 * internes de MS1 et MS2 — celles qui ne sont pas routées par la passerelle et n'exigent pas de
 * jeton utilisateur, que MS3 n'a pas.
 *
 * <p><b>Échec fermé.</b> Si MS1 ou MS2 est injoignable, on refuse. Un contrôle de propriété qui
 * s'ouvre quand sa dépendance tombe ne protège rien : c'est précisément pendant un incident que
 * l'on veut qu'il tienne.
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

    /** Bus que ce compte a le droit de consulter. Vide = aucun (jamais « tous »). */
    public Set<Long> busAutorises(UserPrincipal user) {
        if (user == null || user.getRole() == null) {
            return Collections.emptySet();
        }
        if (user.getRole() == Role.ADMIN) {
            return null;  // null = pas de restriction, distinct d'un ensemble vide
        }
        try {
            if (user.getRole() == Role.CHAUFFEUR) {
                Long[] bus = restTemplate.getForObject(
                        ms1Url + "/internal/bus/chauffeur/" + user.getUserId(), Long[].class);
                return bus == null ? Collections.emptySet() : Set.of(bus);
            }
            Long[] bus = restTemplate.getForObject(
                    ms2Url + "/internal/parents/" + user.getUserId() + "/bus", Long[].class);
            return bus == null ? Collections.emptySet() : Set.of(bus);
        } catch (Exception e) {
            log.warn("[MS3] Portée indéterminable pour l'utilisateur {} ({}) — accès refusé",
                    user.getUserId(), e.getMessage());
            return Collections.emptySet();
        }
    }

    /** Lève 403 si le compte n'a rien à faire sur ce bus. */
    public void exigerAccesAuBus(UserPrincipal user, Long busId) {
        Set<Long> autorises = busAutorises(user);
        if (autorises == null || autorises.contains(busId)) {
            return;
        }
        throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Ce bus ne vous concerne pas.");
    }

    /**
     * Restreint une liste de positions aux bus autorisés.
     * L'administration reçoit la liste entière ; les autres, leur périmètre.
     */
    public List<PositionResponse> filtrerAuxBusAutorises(UserPrincipal user,
                                                         List<PositionResponse> positions) {
        Set<Long> autorises = busAutorises(user);
        if (autorises == null) {
            return positions;
        }
        return positions.stream()
                .filter(p -> p.getCibleId() != null && autorises.contains(p.getCibleId()))
                .toList();
    }
}
