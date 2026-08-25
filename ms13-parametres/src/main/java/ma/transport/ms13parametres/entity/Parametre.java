package ma.transport.ms13parametres.entity;

import jakarta.persistence.*;
import lombok.*;

import java.time.LocalDateTime;

/**
 * Entité Parametre — une ligne = un réglage pilotable depuis la console d'administration.
 * ======================================================================================
 *
 * Source de vérité unique du système. Avant MS13, chaque réglage vivait dans un `.env` ou
 * une constante compilée : les coordonnées de l'école étaient écrites à six endroits, et
 * MS4 en avait une version divergente de ~900 m que personne ne pouvait voir.
 *
 * <p><b>Les métadonnées ne sont PAS des données.</b> `libelle`, `min`, `max`, `options`,
 * `valeurDefaut`… sont recopiées à chaque démarrage depuis {@code ParametreCatalogue}
 * (code versionné). Seule {@link #valeur} appartient à la base. Conséquences :
 * <ul>
 *   <li>ajouter un paramètre = ajouter une ligne au catalogue, rien à migrer ;</li>
 *   <li>corriger un libellé ou une borne = redéployer, pas d'UPDATE manuel ;</li>
 *   <li>`POST /reset` sait toujours à quoi revenir.</li>
 * </ul>
 */
@Entity
@Table(name = "parametres", indexes = {
    @Index(name = "idx_parametre_groupe", columnList = "groupe")
})
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Parametre {

    /** Clé stable, préfixée par le service consommateur : {@code ms11.seuil_deviation_m}, {@code ecole.lat}. */
    @Id
    @Column(length = 80)
    private String cle;

    /**
     * Valeur courante, TOUJOURS stockée en texte et interprétée selon {@link #type}.
     * Une colonne unique évite cinq colonnes dont quatre seraient nulles à chaque ligne.
     */
    @Column(nullable = false, length = 500)
    private String valeur;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 20)
    private TypeParam type;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 30)
    private Groupe groupe;

    /** Ordre d'affichage à l'intérieur d'un groupe (position dans le catalogue). */
    @Column(nullable = false)
    private Integer ordre;

    @Column(nullable = false, length = 120)
    private String libelle;

    /** Aide affichée sous le champ — c'est là qu'on cite les mesures des benchmarks. */
    @Column(length = 600)
    private String description;

    /** Unité affichée à droite du champ (« m », « km/h », « min »…), ou null. */
    @Column(length = 20)
    private String unite;

    @Column(name = "valeur_defaut", nullable = false, length = 500)
    private String valeurDefaut;

    /** Bornes de validation, pour {@link TypeParam#NUMBER} uniquement. */
    @Column(name = "valeur_min")
    private Double min;

    @Column(name = "valeur_max")
    private Double max;

    /** Valeurs autorisées, séparées par des virgules, pour {@link TypeParam#ENUM}. */
    @Column(length = 300)
    private String options;

    /** {@code true} ⇒ jamais renvoyé en clair hors du réseau local (clés API). */
    @Column(nullable = false)
    private Boolean sensible;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 20)
    private Impact impact;

    /**
     * Clé d'un autre paramètre dont ce réglage dépend, ou null s'il est toujours actif.
     *
     * <p>Avec {@link #dependValeur}, exprime « ce champ n'a de sens que si {@code dependDe}
     * vaut {@code dependValeur} ». L'interface s'en sert pour verrouiller le champ et afficher
     * la raison — un administrateur ne doit pas pouvoir renseigner soigneusement une météo
     * imposée que le système n'ira jamais lire parce que le mode est resté sur {@code auto}.
     *
     * <p>Purement indicatif côté serveur : l'écriture reste autorisée, afin qu'on puisse
     * préparer les valeurs avant de basculer le mode, ou l'inverse.
     *
     * <p>Colonnes nullables : {@code ddl-auto=update} les ajoute seul, sans migration.
     */
    @Column(name = "depend_de", length = 80)
    private String dependDe;

    @Column(name = "depend_valeur", length = 80)
    private String dependValeur;

    @Column(name = "date_modif")
    private LocalDateTime dateModif;

    /** Email extrait du JWT de l'admin qui a écrit la valeur. */
    @Column(name = "modifie_par", length = 120)
    private String modifiePar;

    /** Type de la valeur — pilote la validation serveur ET le widget affiché par React. */
    public enum TypeParam {
        NUMBER, BOOLEAN, STRING, ENUM, SECRET
    }

    /** Onglet de la page /settings. */
    public enum Groupe {
        ECOLE, REGROUPEMENT, TOURNEES, ETA, CONTEXTE_PRED,
        ANOMALIES, NOTIFICATIONS, ASSISTANT, INTERFACE
    }

    /**
     * Quand le changement prend effet — affiché à l'admin pour qu'il ne croie pas
     * qu'un réglage de clustering redistribue les élèves à la seconde où il l'enregistre.
     */
    public enum Impact {
        /** Pris en compte au prochain appel — aucun redémarrage. */
        IMMEDIAT,
        /** Ne s'applique qu'au prochain calcul de regroupement / tournée. */
        PROCHAIN_CALCUL,
        /** Ne s'applique qu'au prochain trajet démarré (route figée au démarrage). */
        PROCHAIN_TRAJET,
        /** Exige un redémarrage du service concerné. */
        REDEMARRAGE
    }

    /** {@code true} si la valeur courante diffère du défaut du catalogue. */
    public boolean estModifie() {
        return valeur != null && !valeur.equals(valeurDefaut);
    }
}
