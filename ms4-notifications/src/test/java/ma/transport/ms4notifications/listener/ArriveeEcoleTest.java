package ma.transport.ms4notifications.listener;

import com.fasterxml.jackson.databind.ObjectMapper;
import ma.transport.ms4notifications.entity.Notification.TypeNotification;
import ma.transport.ms4notifications.service.BusLookupService;
import ma.transport.ms4notifications.service.FcmService;
import ma.transport.ms4notifications.service.ParametresCache;
import ma.transport.ms4notifications.service.ParentLookupService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

/**
 * Verrou d'arrivée à l'école — une annonce par arrivée réelle.
 *
 * <p>Ces tests encadrent la correction du défaut mesuré sur l'export de production du 24/08 :
 * {@code onGpsBusUpdated} notifiait à chaque ping GPS passé dans le rayon, soit
 * <b>150 notifications identiques par parent espacées de 1,2 s</b> (pic à 1110 pour un bus en
 * une minute), parce qu'un bus stationné à l'école continue d'émettre sa position.
 */
class ArriveeEcoleTest {

    private static final double ECOLE_LAT = 33.893, ECOLE_LNG = -5.5455;
    private static final long BUS = 14L;

    private FcmService fcm;
    private ParentLookupService parents;
    private ParametresCache parametres;
    private NotificationListener listener;

    @BeforeEach
    void setUp() {
        fcm        = mock(FcmService.class);
        parents    = mock(ParentLookupService.class);
        parametres = mock(ParametresCache.class);

        when(parametres.notifArriveeEcole()).thenReturn(true);
        when(parametres.ecoleLat()).thenReturn(ECOLE_LAT);
        when(parametres.ecoleLng()).thenReturn(ECOLE_LNG);
        when(parametres.rayonArriveeM()).thenReturn(150.0);
        when(parametres.arriveeEcoleCooldownMin()).thenReturn(30L);
        when(parents.getParentsParBus(BUS)).thenReturn(List.of(421L, 523L));

        listener = new NotificationListener(fcm, parents, mock(BusLookupService.class),
                                            new ObjectMapper(), parametres);
    }

    /** Envoie un ping GPS situé à {@code metres} au nord de l'école. */
    private void ping(double metres) {
        double lat = ECOLE_LAT + metres / 111_320.0;
        listener.onGpsBusUpdated(
                "{\"cibleId\":" + BUS + ",\"latitude\":" + lat + ",\"longitude\":" + ECOLE_LNG + "}");
    }

    private long annonces() {
        return mockingDetails(fcm).getInvocations().stream()
                .filter(i -> i.getMethod().getName().equals("envoyerAuParent"))
                .filter(i -> i.getArgument(1) == TypeNotification.BUS_ARRIVE_ECOLE)
                .count();
    }

    @Test
    @DisplayName("Le bus stationné dans le rayon n'est annoncé qu'une fois — le cas mesuré en production")
    void stationnementNeGenerePasDeRafale() {
        ping(2000);                                   // en tournée, hors zone
        for (int i = 0; i < 150; i++) ping(40);       // arrivée puis stationnement

        assertThat(annonces()).isEqualTo(2);          // 1 annonce × 2 parents
    }

    @Test
    @DisplayName("Le verrou se réarme quand le bus repart, pour annoncer le retour du soir")
    void nouvelleArriveeApresUnVraiDepart() {
        when(parametres.arriveeEcoleCooldownMin()).thenReturn(0L);   // isoler le verrou du filet

        ping(2000);
        for (int i = 0; i < 20; i++) ping(40);        // arrivée du matin
        for (int i = 0; i < 20; i++) ping(3000);      // tournée du soir
        for (int i = 0; i < 20; i++) ping(40);        // retour du soir

        assertThat(annonces()).isEqualTo(4);          // 2 arrivées × 2 parents
    }

    @Test
    @DisplayName("Le bruit GPS autour du rayon ne réarme pas le verrou")
    void bruitGpsNeReArmePas() {
        when(parametres.arriveeEcoleCooldownMin()).thenReturn(0L);

        ping(2000);
        ping(140);                                    // entrée : annonce
        for (int i = 0; i < 50; i++) ping(i % 2 == 0 ? 160 : 140);   // oscillation ±20 m

        assertThat(annonces()).isEqualTo(2);          // toujours une seule arrivée
    }

    @Test
    @DisplayName("Le délai minimal couvre les allers-retours au-delà de la marge d'hystérésis")
    void cooldownCouvreLesAllersRetours() {
        ping(2000);
        ping(40);                                     // arrivée : annoncée
        ping(2000);                                   // sortie franche : verrou levé
        ping(40);                                     // retour immédiat : filet des 30 min

        assertThat(annonces()).isEqualTo(2);          // la seconde est supprimée
    }

    @Test
    @DisplayName("Le départ de la tournée ne s'annonce pas comme une arrivée")
    void demarrageDeTrajetNAnnoncePasUneArrivee() {
        // La tournée part de l'école : sans armement, le premier ping du trajet serait lu
        // comme une entrée dans le rayon. Le cas se produit à chaque redémarrage de MS4.
        listener.onTrajet("{\"statut\":\"EN_COURS\",\"sens\":\"MATIN\",\"busId\":" + BUS
                        + ",\"matricule\":\"1001-A-50\",\"chauffeurId\":32}");
        for (int i = 0; i < 10; i++) ping(30);        // encore sur le parking de l'école

        assertThat(annonces()).isZero();
    }

    @Test
    @DisplayName("L'interrupteur MS13 coupe l'annonce sans consommer le verrou")
    void interrupteurRespecte() {
        when(parametres.notifArriveeEcole()).thenReturn(false);
        for (int i = 0; i < 10; i++) ping(40);

        verify(fcm, never()).envoyerAuParent(any(), any(), any(), any(), any(), any());
    }
}
