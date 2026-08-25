package ma.transport.ms13parametres.service;

import jakarta.annotation.PostConstruct;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import ma.transport.ms13parametres.catalogue.ParametreCatalogue;
import ma.transport.ms13parametres.catalogue.ParametreCatalogue.Def;
import ma.transport.ms13parametres.dto.ParametreResponse;
import ma.transport.ms13parametres.entity.Parametre;
import ma.transport.ms13parametres.entity.Parametre.Groupe;
import ma.transport.ms13parametres.entity.Parametre.TypeParam;
import ma.transport.ms13parametres.repository.ParametreRepository;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.*;

@Slf4j
@Service
@RequiredArgsConstructor
public class ParametreService {

    public static final String EXCHANGE    = "transport.exchange";
    public static final String ROUTING_KEY = "parametres.updated";

    private final ParametreRepository repo;
    private final RabbitTemplate      rabbitTemplate;

    // ─── Amorçage ────────────────────────────────────────────────────────────

    /**
     * Aligne la base sur le catalogue à chaque démarrage.
     *
     * <p><b>Upsert non destructif</b> : les métadonnées (libellé, bornes, défaut, groupe…) sont
     * systématiquement réécrites depuis le code, la {@code valeur} ne l'est jamais. C'est ce qui
     * permet de corriger une aide ou d'élargir une borne par un simple redéploiement, sans jamais
     * écraser un réglage fait en production.
     *
     * <p>Les clés retirées du catalogue sont supprimées : une ligne orpheline en base
     * réapparaîtrait dans l'API sans qu'aucun service ne la lise — un réglage sans effet est pire
     * qu'un réglage absent.
     */
    @PostConstruct
    @Transactional
    public void seed() {
        Set<String> clesCatalogue = new HashSet<>();
        int crees = 0, majs = 0;

        for (int i = 0; i < ParametreCatalogue.DEFS.size(); i++) {
            Def d = ParametreCatalogue.DEFS.get(i);
            clesCatalogue.add(d.cle());

            Optional<Parametre> existant = repo.findById(d.cle());
            Parametre p = existant.orElseGet(() -> Parametre.builder()
                    .cle(d.cle())
                    .valeur(d.defaut())          // valeur initiale = défaut, uniquement à la création
                    .build());

            p.setType(d.type());
            p.setGroupe(d.groupe());
            p.setOrdre(i);
            p.setLibelle(d.libelle());
            p.setDescription(d.description());
            p.setUnite(d.unite());
            p.setValeurDefaut(d.defaut());
            p.setMin(d.min());
            p.setMax(d.max());
            p.setOptions(d.options());
            p.setSensible(d.sensible());
            p.setImpact(d.impact());
            p.setDependDe(d.dependDe());
            p.setDependValeur(d.dependValeur());

            repo.save(p);
            if (existant.isPresent()) majs++; else crees++;
        }

        List<Parametre> orphelins = repo.findAll().stream()
                .filter(p -> !clesCatalogue.contains(p.getCle()))
                .toList();
        if (!orphelins.isEmpty()) {
            orphelins.forEach(p -> log.warn("[MS13] Paramètre orphelin supprimé : {}", p.getCle()));
            repo.deleteAll(orphelins);
        }

        log.info("[MS13] Catalogue synchronisé — {} créés, {} mis à jour, {} orphelins supprimés",
                 crees, majs, orphelins.size());
    }

    // ─── Lecture ─────────────────────────────────────────────────────────────

    /** Vue complète pour l'UI et les fronts : secrets masqués. */
    public List<ParametreResponse> getTous() {
        return repo.findAllByOrderByGroupeAscOrdreAsc().stream()
                .map(ParametreResponse::from)
                .toList();
    }

    /**
     * Valeurs effectives en clair, secrets compris — <b>route interne uniquement</b>.
     * Consommée par les services Python et par MS4 en localhost, jamais exposée par la passerelle.
     */
    public Map<String, String> valeursEffectives() {
        Map<String, String> out = new LinkedHashMap<>();
        repo.findAllByOrderByGroupeAscOrdreAsc().forEach(p -> out.put(p.getCle(), p.getValeur()));
        return out;
    }

    /** Onglets et leur contenu, pour que React n'ait aucun libellé en dur. */
    public Map<String, Object> getSchema() {
        Map<String, List<ParametreResponse>> parGroupe = new LinkedHashMap<>();
        for (Groupe g : Groupe.values()) {
            List<ParametreResponse> items = repo.findByGroupeOrderByOrdreAsc(g).stream()
                    .map(ParametreResponse::from)
                    .toList();
            if (!items.isEmpty()) parGroupe.put(g.name(), items);
        }
        return Map.of(
            "groupes", Arrays.stream(Groupe.values()).map(Enum::name).filter(parGroupe::containsKey).toList(),
            "parametres", parGroupe,
            "total", repo.count()
        );
    }

    // ─── Écriture ────────────────────────────────────────────────────────────

    /**
     * Applique un lot de valeurs. Valide TOUT avant d'écrire QUOI QUE CE SOIT.
     *
     * @return les clés effectivement modifiées (une valeur identique à l'actuelle n'en fait pas partie)
     */
    @Transactional
    public List<String> majLot(Map<String, String> valeurs, String parEmail) {
        // Phase 1 — validation intégrale, aucune écriture
        Map<Parametre, String> aEcrire = new LinkedHashMap<>();
        for (Map.Entry<String, String> e : valeurs.entrySet()) {
            Parametre p = repo.findById(e.getKey())
                    .orElseThrow(() -> new IllegalArgumentException(
                            "Paramètre inconnu : " + e.getKey()));

            String normalisee = valider(p, e.getValue());
            if (normalisee == null) continue;                 // secret laissé vide = inchangé
            if (normalisee.equals(p.getValeur())) continue;   // pas de bruit d'événement
            aEcrire.put(p, normalisee);
        }

        // Phase 2 — écriture
        LocalDateTime maintenant = LocalDateTime.now();
        List<String> modifiees = new ArrayList<>();
        aEcrire.forEach((p, v) -> {
            String ancienne = Boolean.TRUE.equals(p.getSensible()) ? "(secret)" : p.getValeur();
            String nouvelle = Boolean.TRUE.equals(p.getSensible()) ? "(secret)" : v;
            p.setValeur(v);
            p.setDateModif(maintenant);
            p.setModifiePar(parEmail);
            repo.save(p);
            modifiees.add(p.getCle());
            log.info("[MS13] {} : {} → {} (par {})", p.getCle(), ancienne, nouvelle, parEmail);
        });

        if (!modifiees.isEmpty()) publierChangement(modifiees);
        return modifiees;
    }

    /** Remet au défaut du catalogue une clé, un groupe entier, ou tout si les deux sont nuls. */
    @Transactional
    public List<String> reset(String cle, Groupe groupe, String parEmail) {
        List<Parametre> cibles;
        if (cle != null && !cle.isBlank()) {
            cibles = List.of(repo.findById(cle).orElseThrow(
                    () -> new IllegalArgumentException("Paramètre inconnu : " + cle)));
        } else if (groupe != null) {
            cibles = repo.findByGroupeOrderByOrdreAsc(groupe);
        } else {
            cibles = repo.findAllByOrderByGroupeAscOrdreAsc();
        }

        LocalDateTime maintenant = LocalDateTime.now();
        List<String> modifiees = new ArrayList<>();
        for (Parametre p : cibles) {
            // Réinitialiser un secret le viderait : le défaut du catalogue est la chaîne vide,
            // et l'admin perdrait sa clé API sans l'avoir demandé explicitement.
            if (Boolean.TRUE.equals(p.getSensible()) && (cle == null || cle.isBlank())) continue;
            if (Objects.equals(p.getValeur(), p.getValeurDefaut())) continue;
            p.setValeur(p.getValeurDefaut());
            p.setDateModif(maintenant);
            p.setModifiePar(parEmail);
            repo.save(p);
            modifiees.add(p.getCle());
        }
        log.info("[MS13] Réinitialisation ({} clés) par {}", modifiees.size(), parEmail);
        if (!modifiees.isEmpty()) publierChangement(modifiees);
        return modifiees;
    }

    // ─── Validation ──────────────────────────────────────────────────────────

    /**
     * Vérifie et normalise une valeur soumise.
     *
     * @return la valeur à écrire, ou {@code null} si le champ doit être laissé inchangé
     * @throws IllegalArgumentException si la valeur est refusée (→ 400 via le handler global)
     */
    private String valider(Parametre p, String brute) {
        String v = brute == null ? "" : brute.trim();

        if (p.getType() == TypeParam.SECRET) {
            // Motif déjà utilisé par MS7 pour les mots de passe : champ vide = valeur conservée.
            if (v.isEmpty()) return null;

            // Un masque qu'on nous renvoie n'est pas une nouvelle valeur.
            //
            // C'est le piège de ce motif, et il est facile à manquer : le formulaire reçoit
            // « ••••••4f2a » depuis GET /api/parametres et le garde dans son état. L'admin change
            // un tout autre champ de l'onglet, enregistre — et le masque part avec le lot. Sans
            // cette garde, la clé API est remplacée par des puces et l'assistant tombe en panne
            // sans qu'aucune erreur ne soit levée : le service a bien reçu « une valeur ».
            //
            // Vérifié en réel avant correctif : la clé était effectivement détruite (HTTP 200).
            // La garde est ici, côté serveur, et non dans le formulaire, parce qu'elle doit tenir
            // quel que soit le client — application mobile, script, appel curl.
            if (v.startsWith(ParametreResponse.MASQUE)) return null;

            return v;
        }

        if (v.isEmpty() && p.getType() != TypeParam.STRING) {
            throw new IllegalArgumentException(p.getCle() + " : valeur vide");
        }

        return switch (p.getType()) {
            case NUMBER -> {
                double d;
                try {
                    d = Double.parseDouble(v.replace(',', '.'));
                } catch (NumberFormatException ex) {
                    throw new IllegalArgumentException(p.getCle() + " : « " + v + " » n'est pas un nombre");
                }
                if (!Double.isFinite(d)) {
                    throw new IllegalArgumentException(p.getCle() + " : nombre non fini");
                }
                if (p.getMin() != null && d < p.getMin()) {
                    throw new IllegalArgumentException(
                            p.getCle() + " : " + d + " est inférieur au minimum " + p.getMin());
                }
                if (p.getMax() != null && d > p.getMax()) {
                    throw new IllegalArgumentException(
                            p.getCle() + " : " + d + " dépasse le maximum " + p.getMax());
                }
                // Normalise « 120,0 » et « 120.00 » vers « 120 » : la comparaison avec la valeur
                // courante décide de l'émission d'un événement, elle doit être stable.
                yield (d == Math.rint(d) && Math.abs(d) < 1e15)
                        ? String.valueOf((long) d)
                        : String.valueOf(d);
            }
            case BOOLEAN -> {
                if (!v.equalsIgnoreCase("true") && !v.equalsIgnoreCase("false")) {
                    throw new IllegalArgumentException(p.getCle() + " : attendu true ou false");
                }
                yield v.toLowerCase();
            }
            case ENUM -> {
                List<String> permis = Arrays.asList(p.getOptions().split(","));
                if (!permis.contains(v)) {
                    throw new IllegalArgumentException(
                            p.getCle() + " : « " + v + " » hors des valeurs permises (" + p.getOptions() + ")");
                }
                yield v;
            }
            case STRING -> {
                if (v.length() > 500) {
                    throw new IllegalArgumentException(p.getCle() + " : plus de 500 caractères");
                }
                yield v;
            }
            case SECRET -> null;   // traité plus haut
        };
    }

    // ─── Diffusion ───────────────────────────────────────────────────────────

    /**
     * Prévient les consommateurs. Le message porte les clés changées, pas les valeurs :
     * chacun relit la source de vérité, ce qui évite qu'un message perdu ou réordonné laisse
     * un service avec une vision différente des autres. Les secrets ne transitent donc jamais
     * par le bus de messages.
     *
     * <p>Publié en {@code text/plain} : le convertisseur JSON de MS4 rejette un objet
     * {@code application/json} dans un handler {@code String}.
     */
    private void publierChangement(List<String> cles) {
        try {
            rabbitTemplate.convertAndSend(EXCHANGE, ROUTING_KEY, String.join(",", cles));
            log.debug("[MS13] Événement publié : {} ({} clés)", ROUTING_KEY, cles.size());
        } catch (Exception e) {
            // Le filet de rattrapage périodique des consommateurs rattrapera le changement.
            log.warn("[MS13] Publication RabbitMQ échouée : {}", e.getMessage());
        }
    }
}
