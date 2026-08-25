package ma.transport.ms4notifications.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.annotation.PostConstruct;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.util.Collections;
import java.util.Map;

/**
 * Cache local des paramètres métier servis par MS13.
 * ==================================================
 *
 * <p>Équivalent Java du module {@code params.py} des services Python. Trois chemins de mise à
 * jour, du plus rapide au plus robuste : l'événement {@code parametres.updated}, un
 * rafraîchissement périodique en filet, et le démarrage.
 *
 * <p><b>Ce cache corrige un défaut de fond, pas seulement un confort.</b> Les coordonnées de
 * l'école étaient trois constantes compilées dans {@code NotificationListener}
 * ({@code 33.8850 / -5.5480}), alors que MS5, MS12, MS9 et les deux applications Flutter
 * utilisaient {@code 33.893 / -5.5455} — environ 900 m plus au nord. MS4 déclenchait donc
 * « le bus est arrivé à l'école » sur un point qui n'était pas l'école desservie par les
 * tournées. Rien ne pouvait le révéler : les deux valeurs vivaient dans deux fichiers de deux
 * langages différents, et aucune n'était fausse en elle-même.
 *
 * <p>MS4 appelle MS13 <b>en direct</b>, sans passer par la passerelle : il n'a pas de jeton
 * utilisateur à présenter. C'est le même motif que {@link ParentLookupService}, qui appelle
 * MS2 en direct pour la même raison.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ParametresCache {

    private final ObjectMapper objectMapper;
    private final RestTemplate restTemplate = new RestTemplate();

    @Value("${ms13.url:http://localhost:8092}")
    private String ms13Url;

    /** Dernier instantané connu. Volatile : écrit par le listener AMQP, lu par les autres. */
    private volatile Map<String, String> valeurs = Collections.emptyMap();

    @PostConstruct
    public void init() {
        rafraichir();
    }

    /** Filet : rattrape un courtier absent ou un message perdu. */
    @Scheduled(fixedDelay = 60_000L, initialDelay = 60_000L)
    public void rafraichirPeriodiquement() {
        rafraichir();
    }

    /**
     * Réception de l'événement. Le message ne porte que les clés changées : on relit toujours
     * MS13, si bien qu'un message perdu, dupliqué ou réordonné ne peut pas laisser MS4 avec une
     * vision différente des autres services.
     */
    @RabbitListener(queues = "ms4.parametres.queue")
    public void onParametresUpdated(String clesModifiees) {
        log.info("[MS4] 📨 parametres.updated reçu ({})", clesModifiees);
        rafraichir();
    }

    private void rafraichir() {
        try {
            String json = restTemplate.getForObject(ms13Url + "/api/parametres/internal", String.class);
            if (json == null) return;
            Map<String, String> nouvelles =
                    objectMapper.readValue(json, new TypeReference<Map<String, String>>() {});
            boolean premier = valeurs.isEmpty();
            valeurs = nouvelles;
            if (premier) {
                log.info("[MS4] Paramètres chargés depuis MS13 — école {},{} rayon {} m",
                         ecoleLat(), ecoleLng(), rayonArriveeM());
            }
        } catch (Exception e) {
            // Mode dégradé assumé : MS4 continue avec les valeurs par défaut ci-dessous.
            // Un incident sur MS13 ne doit pas interrompre les notifications aux familles.
            log.warn("[MS4] MS13 injoignable ({}) — valeurs par défaut conservées", e.getMessage());
        }
    }

    // ─── Accès typés ─────────────────────────────────────────────────────────

    public double ecoleLat()      { return nombre("ecole.lat", 33.893); }
    public double ecoleLng()      { return nombre("ecole.lng", -5.5455); }
    public double rayonArriveeM() { return nombre("ecole.rayon_arrivee_m", 150.0); }

    public boolean notifArriveeEcole()  { return booleen("ms4.notif_arrivee_ecole", true); }
    public boolean notifEnfantABord()   { return booleen("ms4.notif_enfant_a_bord", true); }
    public boolean notifEta()           { return booleen("ms4.notif_eta", true); }
    public boolean notifAdminQualite()  { return booleen("ms4.notif_admin_qualite", true); }
    public boolean notifAdminAnomalie() { return booleen("ms4.notif_admin_anomalie", true); }

    private double nombre(String cle, double defaut) {
        String v = valeurs.get(cle);
        if (v == null || v.isBlank()) return defaut;
        try {
            return Double.parseDouble(v);
        } catch (NumberFormatException e) {
            log.warn("[MS4] {} = « {} » illisible — défaut {} appliqué", cle, v, defaut);
            return defaut;
        }
    }

    private boolean booleen(String cle, boolean defaut) {
        String v = valeurs.get(cle);
        if (v == null || v.isBlank()) return defaut;
        return Boolean.parseBoolean(v);
    }
}
