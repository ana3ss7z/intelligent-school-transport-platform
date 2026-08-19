package ma.transport.ms1bus.dto;

import java.util.List;

import lombok.Builder;
import lombok.Data;
import ma.transport.ms1bus.entity.Trajet.Sens;

/**
 * Tournée figée d'un trajet en cours : polyligne + totaux OSRM.
 *
 * <p>Volontairement séparé de {@link TrajetResponse} : la géométrie pèse plusieurs dizaines de Ko
 * et {@code /bus/{id}/actif} est sondé toutes les 15 s par chaque front. Ici l'appelant ne recharge
 * qu'au changement de trajet.</p>
 *
 * <p>Sert aux fronts (chauffeur ET parent) à calculer la distance <b>restante le long de la
 * tournée</b> plutôt qu'à vol d'oiseau : pendant le ramassage le bus s'éloigne de l'école, donc un
 * ETA point-à-point augmente au lieu de décroître.</p>
 */
@Data
@Builder
public class TrajetRouteResponse {
    private Long trajetId;
    private Long busId;
    private Long groupeId;
    private Sens sens;
    /** Polyligne [[lat,lng],…] de la tournée planifiée (vide si le trajet a démarré sans tournée). */
    private List<List<Double>> geometrie;
    private Double distancePlanM;
    private Double dureePlanMin;
}
