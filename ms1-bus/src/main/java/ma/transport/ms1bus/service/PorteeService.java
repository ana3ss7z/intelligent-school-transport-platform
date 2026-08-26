package ma.transport.ms1bus.service;

import java.util.Collections;
import java.util.Set;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.server.ResponseStatusException;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import ma.transport.ms1bus.repository.BusRepository;
import ma.transport.mscommon.enums.Role;
import ma.transport.mscommon.security.UserPrincipal;

/**
 * Controle de <b>portee</b> : ce compte a-t-il le droit d'agir sur <b>ce bus</b> ?
 *
 * <p>MS1 ouvrait au role PARENT la lecture du trajet actif et surtout de la <b>polyligne</b>
 * d'un bus. Le commentaire du code disait « deja scope par bus » : scope a UN bus, pas au bus
 * du demandeur. N'importe quel parent lisait donc la tournee de n'importe quel bus — et une
 * polyligne de tournee trace la rue de chaque famille transportee. C'est exactement ce que MS5
 * refuse deliberement de livrer au parent via /mes-enfants.
 *
 * <p>MS1 connait la table des bus (donc le chauffeur), mais pas celle des eleves : la portee
 * d'un parent se demande a MS2 par sa route interne.
 *
 * <p><b>Echec ferme</b> : MS2 injoignable ⇒ refus. Un controle de propriete qui s'ouvre quand
 * sa dependance tombe ne protege rien.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class PorteeService {

    private final BusRepository busRepo;
    private final RestTemplate restTemplate = new RestTemplate();

    @Value("${ms2.url:http://localhost:8082}")
    private String ms2Url;

    /** Bus consultables par ce compte. {@code null} = aucune restriction (ADMIN). */
    public Set<Long> busAutorises(UserPrincipal user) {
        if (user == null || user.getRole() == null) {
            return Collections.emptySet();
        }
        if (user.getRole() == Role.ADMIN) {
            return null;
        }
        if (user.getRole() == Role.CHAUFFEUR) {
            return busRepo.findAll().stream()
                    .filter(b -> user.getUserId().equals(b.getChauffeurId()))
                    .map(b -> b.getId())
                    .collect(java.util.stream.Collectors.toSet());
        }
        try {
            Long[] bus = restTemplate.getForObject(
                    ms2Url + "/internal/parents/" + user.getUserId() + "/bus", Long[].class);
            return bus == null ? Collections.emptySet() : Set.of(bus);
        } catch (Exception e) {
            log.warn("[MS1] Portee indeterminable pour l'utilisateur {} ({}) - acces refuse",
                    user.getUserId(), e.getMessage());
            return Collections.emptySet();
        }
    }

    /** Leve 403 si le compte n'a rien a faire sur ce bus. */
    public void exigerAccesAuBus(UserPrincipal user, Long busId) {
        Set<Long> autorises = busAutorises(user);
        if (autorises == null || autorises.contains(busId)) {
            return;
        }
        throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Ce bus ne vous concerne pas.");
    }

    /** Leve 403 si ce chauffeur ne conduit pas ce bus. L'ADMIN passe. */
    public void exigerBusDuChauffeur(UserPrincipal user, Long busId) {
        if (user != null && user.getRole() == Role.ADMIN) {
            return;
        }
        Long proprietaire = busRepo.findById(busId)
                .map(b -> b.getChauffeurId())
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Bus introuvable."));
        if (user == null || !user.getUserId().equals(proprietaire)) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Ce bus ne vous est pas affecte.");
        }
    }
}
