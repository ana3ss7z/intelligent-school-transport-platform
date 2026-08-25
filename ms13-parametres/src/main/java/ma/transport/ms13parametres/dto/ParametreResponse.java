package ma.transport.ms13parametres.dto;

import lombok.Builder;
import lombok.Data;
import ma.transport.ms13parametres.entity.Parametre;

import java.time.LocalDateTime;

/**
 * Vue d'un paramètre destinée à l'extérieur du service.
 *
 * <p><b>Un secret ne sort jamais en clair par ici.</b> {@link #from} remplace la valeur par un
 * masque ; seul {@code GET /api/parametres/internal}, non routé par la passerelle, renvoie la
 * valeur réelle aux services qui en ont besoin.
 */
@Data
@Builder
public class ParametreResponse {

    private String  cle;
    private String  valeur;
    private String  type;
    private String  groupe;
    private Integer ordre;
    private String  libelle;
    private String  description;
    private String  unite;
    private String  valeurDefaut;
    private Double  min;
    private Double  max;
    private String  options;
    private Boolean sensible;
    private String  impact;

    /**
     * Condition d'activation : ce réglage n'a de sens que si le paramètre {@code dependDe}
     * vaut {@code dependValeur}. Null si le réglage est toujours actif.
     *
     * <p>L'interface verrouille alors le champ en expliquant pourquoi. Le serveur, lui,
     * accepte toujours l'écriture — voir {@code ParametreCatalogue.depend}.
     */
    private String  dependDe;
    private String  dependValeur;

    /** Vrai si la valeur courante diffère du défaut du catalogue (pastille « modifié » dans l'UI). */
    private Boolean modifie;

    /** Pour un secret : une valeur est-elle enregistrée ? (le masque ne permet pas de le déduire) */
    private Boolean defini;

    private LocalDateTime dateModif;
    private String        modifiePar;

    public static ParametreResponse from(Parametre p) {
        boolean sensible = Boolean.TRUE.equals(p.getSensible());
        boolean defini   = p.getValeur() != null && !p.getValeur().isBlank();
        return ParametreResponse.builder()
                .cle(p.getCle())
                .valeur(sensible ? masquer(p.getValeur()) : p.getValeur())
                .type(p.getType().name())
                .groupe(p.getGroupe().name())
                .ordre(p.getOrdre())
                .libelle(p.getLibelle())
                .description(p.getDescription())
                .unite(p.getUnite())
                .valeurDefaut(sensible ? "" : p.getValeurDefaut())
                .min(p.getMin())
                .max(p.getMax())
                .options(p.getOptions())
                .sensible(sensible)
                .impact(p.getImpact().name())
                .dependDe(p.getDependDe())
                .dependValeur(p.getDependValeur())
                .modifie(p.estModifie())
                .defini(defini)
                .dateModif(p.getDateModif())
                .modifiePar(p.getModifiePar())
                .build();
    }

    /**
     * Caractère de masquage (U+2022 PUCE). Aucun secret légitime ne commence par ce caractère :
     * c'est ce qui permet au service de reconnaître un masque qu'on lui renvoie et de refuser de
     * l'écrire — voir {@code ParametreService.valider}.
     */
    public static final String MASQUE = "•";

    /**
     * Masque une valeur sensible en conservant ses 4 derniers caractères — assez pour qu'un admin
     * reconnaisse la clé qu'il a collée, pas assez pour la réutiliser.
     */
    private static String masquer(String v) {
        if (v == null || v.isBlank()) return "";
        if (v.length() <= 4) return MASQUE.repeat(4);
        return MASQUE.repeat(6) + v.substring(v.length() - 4);
    }
}
