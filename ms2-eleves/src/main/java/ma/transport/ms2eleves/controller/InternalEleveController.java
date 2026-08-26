package ma.transport.ms2eleves.controller;

import java.util.List;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import lombok.RequiredArgsConstructor;
import ma.transport.ms2eleves.dto.EleveResponse;
import ma.transport.ms2eleves.service.EleveService;

/**
 * Routes internes de MS2 — réservées aux services qui n'ont pas de jeton utilisateur.
 *
 * <p>Pourquoi un contrôleur séparé, et pas une route sous {@code /api/eleves}
 * ------------------------------------------------------------------------
 * MS5, MS6 et MS12 lisent l'effectif complet des élèves pour travailler (tournées,
 * clustering, contexte ETA). Aucun ne dispose d'un JWT : ils appellent MS2 directement.
 * La route {@code GET /api/eleves} avait donc été passée {@code permitAll} — ce qui servait
 * <b>301 élèves avec nom, prénom et coordonnées GPS de leur domicile à qui le demandait</b>,
 * y compris à travers la passerelle. C'est le défaut critique n° 2 de la recette du 26/08,
 * détecté depuis toujours par l'assertion Newman n° 13, jamais rejouée.
 *
 * <p>La protection retenue est celle de MS13 : <b>ne pas être routé par la passerelle</b>.
 * Elle impose un chemin <b>hors</b> de {@code /api/eleves/**}, car ce prédicat
 * ({@code ms8-gateway/application.yml}) avale tout ce qui vit sous {@code /api/eleves} —
 * une route {@code /api/eleves/internal} serait restée joignable depuis le web.
 *
 * <p><b>Ne jamais ajouter de prédicat {@code /internal/**} dans
 * {@code ms8-gateway/src/main/resources/application.yml}.</b> La régression se vérifie en une
 * commande : {@code GET http://localhost:8080/internal/eleves} doit répondre <b>404</b>.
 */
@RestController
@RequestMapping("/internal")
@RequiredArgsConstructor
public class InternalEleveController {

    private final EleveService service;

    /**
     * Effectif complet, pour MS5 (tournées), MS6 (clustering) et MS12 (contexte ETA).
     * Même charge utile que l'ancien {@code GET /api/eleves}, afin que la bascule des clients
     * Python se limite à changer l'URL.
     */
    @GetMapping("/eleves")
    public ResponseEntity<List<EleveResponse>> listerTousInterne() {
        return ResponseEntity.ok(service.listerTous());
    }

    /**
     * Bus fréquentés par les enfants d'un parent — support du contrôle de propriété.
     *
     * <p>MS1 (trajet et polyligne d'un bus), MS3 (positions) et MS10 (incidents d'un bus)
     * ouvrent ces lectures au rôle PARENT. Le rôle ne suffit pas : il faut vérifier que le bus
     * demandé est bien celui d'un de ses enfants, sinon n'importe quel parent lit la tournée —
     * donc la rue de chaque famille — de n'importe quel bus.
     *
     * <p>Ne renvoie que des identifiants de bus : aucun nom, aucune coordonnée.
     */
    @GetMapping("/parents/{parentId}/bus")
    public ResponseEntity<List<Long>> busDuParent(@PathVariable Long parentId) {
        return ResponseEntity.ok(service.getBusIdsParParent(parentId));
    }
}
