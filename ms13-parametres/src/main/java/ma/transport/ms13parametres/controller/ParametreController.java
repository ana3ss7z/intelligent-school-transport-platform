package ma.transport.ms13parametres.controller;

import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import ma.transport.ms13parametres.dto.ParametreResponse;
import ma.transport.ms13parametres.dto.ParametreUpdateRequest;
import ma.transport.ms13parametres.entity.Parametre.Groupe;
import ma.transport.ms13parametres.service.ParametreService;
import ma.transport.mscommon.security.UserPrincipal;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/parametres")
@RequiredArgsConstructor
public class ParametreController {

    private final ParametreService service;

    /**
     * GET /api/parametres — valeurs effectives, secrets masqués.
     *
     * <p>Ouvert à tous les rôles authentifiés : les applications parent et chauffeur en ont besoin
     * pour leurs intervalles de rafraîchissement et les coordonnées de l'école. Rien de sensible
     * n'en sort — {@code ParametreResponse.from} masque les valeurs marquées sensibles.
     */
    @GetMapping
    public ResponseEntity<List<ParametreResponse>> getTous() {
        return ResponseEntity.ok(service.getTous());
    }

    /** GET /api/parametres/schema — catalogue groupé par onglet, pour construire le formulaire. */
    @GetMapping("/schema")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<Map<String, Object>> getSchema() {
        return ResponseEntity.ok(service.getSchema());
    }

    /** PUT /api/parametres — écriture par lot. Tout est validé avant que rien ne soit écrit. */
    @PutMapping
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<Map<String, Object>> majLot(
            @Valid @RequestBody ParametreUpdateRequest req,
            @AuthenticationPrincipal UserPrincipal principal) {

        List<String> modifiees = service.majLot(req.getValeurs(), principal.getEmail());
        return ResponseEntity.ok(Map.of(
            "modifiees", modifiees,
            "n", modifiees.size(),
            "parametres", service.getTous()
        ));
    }

    /**
     * POST /api/parametres/reset — retour aux défauts du catalogue.
     * Sans argument, réinitialise tout <i>sauf les secrets</i> (voir {@code ParametreService.reset}).
     */
    @PostMapping("/reset")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<Map<String, Object>> reset(
            @RequestParam(required = false) String cle,
            @RequestParam(required = false) Groupe groupe,
            @AuthenticationPrincipal UserPrincipal principal) {

        List<String> modifiees = service.reset(cle, groupe, principal.getEmail());
        return ResponseEntity.ok(Map.of(
            "modifiees", modifiees,
            "n", modifiees.size(),
            "parametres", service.getTous()
        ));
    }

    /**
     * GET /api/parametres/internal — valeurs EN CLAIR, secrets compris.
     *
     * <p><b>Cette route ne doit jamais être routée par la passerelle.</b> Elle n'est joignable
     * qu'en {@code localhost:8092}, par les services qui ont besoin des clés API (MS9) ou qui
     * n'ont pas de jeton utilisateur à présenter (les services Python, MS4). C'est exactement le
     * motif déjà retenu ailleurs dans le projet : MS4 appelle MS2 en direct, et MS2 ouvre des
     * routes internes en {@code permitAll} pour MS6.
     *
     * <p>Le test qui compte, à chaque vérification : {@code GET localhost:8080/api/parametres/internal}
     * doit répondre 404.
     */
    @GetMapping("/internal")
    public ResponseEntity<Map<String, String>> internal() {
        return ResponseEntity.ok(service.valeursEffectives());
    }
}
