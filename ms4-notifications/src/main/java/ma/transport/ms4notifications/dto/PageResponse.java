package ma.transport.ms4notifications.dto;

import org.springframework.data.domain.Page;

import java.util.List;
import java.util.function.Function;

/**
 * Enveloppe de pagination renvoyée par les listes d'administration.
 *
 * <p>Introduite parce que {@code GET /api/notifications} faisait un {@code findAll()} sans
 * limite : la console d'administration re-téléchargeait <b>la table entière</b> à chaque
 * sondage, alors que sa pagination était purement cosmétique (25 lignes affichées sur 10 157
 * transportées). Le journal grossit de plus de mille lignes par minute pendant une simulation,
 * donc le coût n'était pas stable dans le temps.
 *
 * @param content    la page demandée
 * @param page       index de page, à partir de 0
 * @param size       taille demandée
 * @param total      nombre total d'éléments correspondant au filtre
 * @param totalPages nombre total de pages
 */
public record PageResponse<T>(List<T> content, int page, int size, long total, int totalPages) {

    public static <E, T> PageResponse<T> from(Page<E> p, Function<E, T> mapper) {
        return new PageResponse<>(
                p.getContent().stream().map(mapper).toList(),
                p.getNumber(), p.getSize(), p.getTotalElements(), p.getTotalPages());
    }
}
