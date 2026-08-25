package ma.transport.ms4notifications.service;

import ma.transport.ms4notifications.entity.DeviceToken;
import ma.transport.ms4notifications.entity.Notification;
import ma.transport.ms4notifications.entity.Notification.StatutEnvoi;
import ma.transport.ms4notifications.entity.Notification.TypeNotification;
import ma.transport.ms4notifications.repository.DeviceTokenRepository;
import ma.transport.ms4notifications.repository.NotificationRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

/**
 * Historisation : une ligne par événement métier, quel que soit le nombre d'appareils.
 *
 * <p>La persistance était faite dans la boucle d'envoi, donc une ligne par appareil. Le défaut
 * était masqué par l'absence totale de token enregistré (zéro appareil ⇒ exactement une ligne).
 * Ces tests fixent le comportement <b>avant</b> que des clients web et Android n'enregistrent
 * plusieurs appareils pour un même compte, ce qui aurait affiché le message en double dans
 * l'application des familles.
 *
 * <p>{@code firebaseApp} est laissé à {@code null} : le mode dégradé emprunte le même chemin de
 * persistance que l'envoi réel, ce qui permet de couvrir le comptage sans joindre Firebase.
 */
class FcmServiceTest {

    private static final long PARENT = 421L;

    private DeviceTokenRepository devices;
    private NotificationRepository notifs;
    private FcmService service;

    @BeforeEach
    void setUp() {
        devices = mock(DeviceTokenRepository.class);
        notifs  = mock(NotificationRepository.class);
        service = new FcmService(null, devices, notifs);   // firebaseApp null → mode dégradé
    }

    private void avecAppareils(String... tokens) {
        when(devices.findByParentIdAndActifTrue(PARENT)).thenReturn(
                java.util.Arrays.stream(tokens)
                        .map(t -> DeviceToken.builder().parentId(PARENT).fcmToken(t).build())
                        .toList());
    }

    private Notification envoyerEtCapturer() {
        service.envoyerAuParent(PARENT, TypeNotification.ENFANT_A_BORD,
                                "🎒 Enfant à bord", "Salma est bien montée.", 134L, "ELEVE");
        ArgumentCaptor<Notification> capt = ArgumentCaptor.forClass(Notification.class);
        verify(notifs, times(1)).save(capt.capture());   // ← le cœur du test
        return capt.getValue();
    }

    @Test
    @DisplayName("Aucun appareil : une ligne, en échec, avec le motif historique")
    void aucunAppareil() {
        avecAppareils();

        Notification n = envoyerEtCapturer();

        assertThat(n.getStatutEnvoi()).isEqualTo(StatutEnvoi.ECHEC);
        assertThat(n.getErreurFcm()).isEqualTo("Aucun device FCM enregistré");
        assertThat(n.getFcmToken()).isNull();
    }

    @Test
    @DisplayName("Un seul appareil : une ligne, et le token reste tracé")
    void unAppareil() {
        avecAppareils("token-web-5174");

        Notification n = envoyerEtCapturer();

        assertThat(n.getFcmToken()).isEqualTo("token-web-5174");
        assertThat(n.getStatutEnvoi()).isEqualTo(StatutEnvoi.ECHEC);   // Firebase absent ici
    }

    @Test
    @DisplayName("Trois appareils : UNE seule ligne — le défaut que la correction empêche")
    void plusieursAppareilsNeDupliquentPas() {
        avecAppareils("token-web-5173", "token-web-5174", "token-android");

        Notification n = envoyerEtCapturer();   // times(1) échouerait avec l'ancien code

        // Au-delà d'un appareil, la ligne décrit l'événement et non un envoi particulier.
        assertThat(n.getFcmToken()).isNull();
        assertThat(n.getErreurFcm()).contains("3 appareils en échec");
    }

    @Test
    @DisplayName("Le type et la source de l'événement sont préservés")
    void contenuPreserve() {
        avecAppareils("token-web-5174", "token-android");

        Notification n = envoyerEtCapturer();

        assertThat(n.getParentId()).isEqualTo(PARENT);
        assertThat(n.getType()).isEqualTo(TypeNotification.ENFANT_A_BORD);
        assertThat(n.getSourceId()).isEqualTo(134L);
        assertThat(n.getSourceType()).isEqualTo("ELEVE");
        assertThat(n.getTitre()).isEqualTo("🎒 Enfant à bord");
    }

    @Test
    @DisplayName("Un token rejeté n'est pas désactivé tant que Firebase est absent")
    void pasDeDesactivationEnModeDegrade() {
        // Le mode dégradé n'est pas un rejet de FCM : désactiver le token ici priverait
        // définitivement l'appareil de push une fois Firebase rebranché.
        avecAppareils("token-web-5174");

        service.envoyerAuParent(PARENT, TypeNotification.ENFANT_A_BORD, "t", "m", 1L, "ELEVE");

        verify(devices, never()).save(any());
    }
}
