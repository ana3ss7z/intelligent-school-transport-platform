package ma.transport.ms4notifications.service;

import ma.transport.ms4notifications.dto.DeviceTokenRequest;
import ma.transport.ms4notifications.entity.DeviceToken;
import ma.transport.ms4notifications.repository.DeviceTokenRepository;
import ma.transport.ms4notifications.repository.NotificationRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.*;

/**
 * Enregistrement d'un token FCM — l'opération doit être idempotente.
 *
 * <p>{@code fcm_token} porte une contrainte UNIQUE ({@code idx_device_token}). La version
 * précédente désactivait la ligne existante <i>sans la supprimer</i> puis en insérait une
 * nouvelle avec le même token : la seconde inscription violait la contrainte. Comme un token
 * FCM est stable pour une installation, cela signifiait qu'une <b>deuxième connexion depuis le
 * même appareil échouait</b>.
 *
 * <p>Le cas est structurel ici : la console web sert les rôles parent et chauffeur sur une
 * seule origine ({@code localhost:5173}), donc un seul service worker et un seul token —
 * changer de rôle réutilise forcément le même.
 */
class DeviceTokenTest {

    private static final String TOKEN = "token-navigateur-5173";

    private DeviceTokenRepository devices;
    private NotificationService service;

    @BeforeEach
    void setUp() {
        devices = mock(DeviceTokenRepository.class);
        service = new NotificationService(mock(NotificationRepository.class), devices, mock(FcmService.class));
    }

    private DeviceTokenRequest requete(String plateforme) {
        DeviceTokenRequest r = new DeviceTokenRequest();
        r.setFcmToken(TOKEN);
        r.setPlateforme(plateforme);
        return r;
    }

    private DeviceToken enregistrer(long parentId, String plateforme) {
        service.enregistrerToken(parentId, requete(plateforme));
        ArgumentCaptor<DeviceToken> capt = ArgumentCaptor.forClass(DeviceToken.class);
        verify(devices, atLeastOnce()).save(capt.capture());
        return capt.getValue();
    }

    @Test
    @DisplayName("Premier enregistrement : une nouvelle ligne active")
    void premierEnregistrement() {
        when(devices.findByFcmToken(TOKEN)).thenReturn(Optional.empty());

        DeviceToken t = enregistrer(421L, "WEB");

        assertThat(t.getParentId()).isEqualTo(421L);
        assertThat(t.getFcmToken()).isEqualTo(TOKEN);
        assertThat(t.getActif()).isTrue();
        assertThat(t.getPlateforme()).isEqualTo("WEB");
    }

    @Test
    @DisplayName("Reconnexion du même parent : la ligne est réutilisée, pas dupliquée")
    void reconnexionNeDupliquePas() {
        DeviceToken existant = DeviceToken.builder()
                .id(7L).parentId(421L).fcmToken(TOKEN).plateforme("WEB").actif(true).build();
        when(devices.findByFcmToken(TOKEN)).thenReturn(Optional.of(existant));

        DeviceToken t = enregistrer(421L, "WEB");

        // Même entité : aucune insertion concurrente, donc aucune violation d'unicité.
        assertThat(t).isSameAs(existant);
        assertThat(t.getId()).isEqualTo(7L);
        verify(devices, times(1)).save(any());
    }

    @Test
    @DisplayName("Changement de rôle sur le même navigateur : le token est réaffecté")
    void changementDUtilisateurReaffecteLeToken() {
        // Un chauffeur se connecte là où un parent s'était connecté : même origine,
        // même service worker, donc même token.
        DeviceToken existant = DeviceToken.builder()
                .id(7L).parentId(421L).fcmToken(TOKEN).plateforme("WEB").actif(false).build();
        when(devices.findByFcmToken(TOKEN)).thenReturn(Optional.of(existant));

        DeviceToken t = enregistrer(32L, "WEB");

        assertThat(t.getParentId()).isEqualTo(32L);   // le token suit l'appareil, pas le compte
        assertThat(t.getActif()).isTrue();            // réactivé après un logout précédent
    }

    @Test
    @DisplayName("Plateforme omise : « INCONNU », jamais « ANDROID » par défaut")
    void plateformeOmiseNEstPasDevinee() {
        when(devices.findByFcmToken(TOKEN)).thenReturn(Optional.empty());

        // @Builder.Default vaut "ANDROID", mais l'appel explicite du constructeur avec null
        // l'écrasait : un client web qui omet le champ s'enregistrait avec une plateforme nulle.
        assertThat(enregistrer(421L, null).getPlateforme()).isEqualTo("INCONNU");
    }

    @Test
    @DisplayName("Plateforme normalisée en majuscules")
    void plateformeNormalisee() {
        when(devices.findByFcmToken(TOKEN)).thenReturn(Optional.empty());

        assertThat(enregistrer(421L, " web ").getPlateforme()).isEqualTo("WEB");
    }
}
