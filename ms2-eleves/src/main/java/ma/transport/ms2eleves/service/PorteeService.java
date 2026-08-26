package ma.transport.ms2eleves.service;

import java.util.Collections;
import java.util.Set;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.server.ResponseStatusException;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import ma.transport.ms2eleves.repository.EleveRepository;
import ma.transport.mscommon.enums.Role;
import ma.transport.mscommon.security.UserPrincipal;

/**
 * Controle de <b>portee</b> : ce compte a-t-il le droit d'agir sur <b>cet eleve</b> ?
 *
 * <p>Deux defauts de la recette du 26/08 vivaient ici. Le pointage de presence
 * ({@code PATCH /api/eleves/{id}/presence}) n'injectait meme pas le principal : <b>n'importe
 * quel chauffeur pouvait pointer n'importe quel eleve</b>, ce qui declenche aussitot une
 * notification poussee au parent d'une <b>autre</b> famille (« votre enfant est bien monte »).
 * Et {@code GET /api/eleves/bus/{id}} servait la liste nominative des eleves de n'importe quel
 * bus a n'importe quel chauffeur.
 *
 * <p>MS2 connait l'affectation eleve → bus, mais pas la table des bus : l'appartenance d'un bus
 * a un chauffeur se demande a MS1 par sa route interne.
 *
 * <p><b>Echec ferme</b> : MS1 injoignable ⇒ refus.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class PorteeService {

    private final EleveRepository repo;
    private final RestTemplate restTemplate = new RestTemplate();

    @Value("${ms1.url:http://localhost:8081}")
    private String ms1Url;

    /** Bus conduits par ce compte. {@code null} = aucune restriction (ADMIN). */
    public Set<Long> busAutorises(UserPrincipal user) {
        if (user == null || user.getRole() == null) {
            return Collections.emptySet();
        }
        if (user.getRole() == Role.ADMIN) {
            return null;
        }
        if (user.getRole() != Role.CHAUFFEUR) {
            return Collections.emptySet();
        }
        try {
            Long[] bus = restTemplate.getForObject(
                    ms1Url + "/internal/bus/chauffeur/" + user.getUserId(), Long[].class);
            return bus == null ? Collections.emptySet() : Set.of(bus);
        } catch (Exception e) {
            log.warn("[MS2] Portee indeterminable pour l'utilisateur {} ({}) - acces refuse",
                    user.getUserId(), e.getMessage());
            return Collections.emptySet();
        }
    }

    /** Leve 403 si le compte ne conduit pas ce bus. */
    public void exigerAccesAuBus(UserPrincipal user, Long busId) {
        Set<Long> autorises = busAutorises(user);
        if (autorises == null || (busId != null && autorises.contains(busId))) {
            return;
        }
        throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Ce bus ne vous est pas affecte.");
    }

    /** Leve 403 si cet eleve n'est pas dans le bus du compte. */
    public void exigerAccesAEleve(UserPrincipal user, Long eleveId) {
        Set<Long> autorises = busAutorises(user);
        if (autorises == null) {
            return;
        }
        Long busEleve = repo.findById(eleveId)
                .map(e -> e.getBusId())
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Eleve introuvable."));
        if (busEleve == null || !autorises.contains(busEleve)) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN,
                    "Cet eleve n'est pas dans votre bus.");
        }
    }
}
