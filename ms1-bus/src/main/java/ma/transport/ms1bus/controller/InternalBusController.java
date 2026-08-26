package ma.transport.ms1bus.controller;

import java.util.List;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import lombok.RequiredArgsConstructor;
import ma.transport.ms1bus.repository.BusRepository;

/**
 * Routes internes de MS1 — pour les services qui n'ont pas de jeton utilisateur.
 *
 * <p>MS3 (positions) et MS10 (incidents) doivent savoir quels bus appartiennent a un chauffeur
 * pour verifier qu'une lecture ou une ecriture le concerne. Ni l'un ni l'autre ne connait la
 * table des bus, et aucun ne dispose d'un jeton : ils passent par ici.
 *
 * <p>Meme motif que MS2 et MS13 : la protection n'est pas un role, c'est le fait que le chemin
 * ne soit <b>pas route par la passerelle</b>. Le prefixe /internal est volontairement hors de
 * /api/bus/**, que la passerelle route en entier.
 *
 * <p><b>Ne jamais ajouter de predicat /internal/** dans ms8-gateway/application.yml.</b>
 * Verification : GET http://localhost:8080/internal/bus/chauffeur/1 doit repondre 404.
 */
@RestController
@RequestMapping("/internal")
@RequiredArgsConstructor
public class InternalBusController {

    private final BusRepository repo;

    /** Identifiants des bus affectes a un chauffeur. Aucune autre donnee. */
    @GetMapping("/bus/chauffeur/{chauffeurId}")
    public ResponseEntity<List<Long>> busDuChauffeur(@PathVariable Long chauffeurId) {
        return ResponseEntity.ok(repo.findAll().stream()
                .filter(b -> chauffeurId.equals(b.getChauffeurId()))
                .map(b -> b.getId())
                .toList());
    }
}
