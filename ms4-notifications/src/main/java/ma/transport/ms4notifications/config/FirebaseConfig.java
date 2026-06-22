package ma.transport.ms4notifications.config;

import com.google.auth.oauth2.GoogleCredentials;
import com.google.firebase.FirebaseApp;
import com.google.firebase.FirebaseOptions;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.io.Resource;

import java.io.IOException;

/**
 * Configuration Firebase Admin SDK
 * =================================
 * Initialise FirebaseApp au démarrage de MS4.
 * Utilise le fichier service-account.json placé dans resources/.
 *
 * Si le fichier n'existe pas ou est invalide (placeholder),
 * MS4 démarre quand même en mode dégradé (FCM désactivé).
 */
@Slf4j
@Configuration
public class FirebaseConfig {

    @Value("${firebase.service-account-path}")
    private Resource serviceAccountResource;

    @Value("${firebase.project-id}")
    private String projectId;

    @Bean
    public FirebaseApp firebaseApp() {
        // Eviter double initialisation (ex: hot reload)
        if (!FirebaseApp.getApps().isEmpty()) {
            log.info("[Firebase] App déjà initialisée");
            return FirebaseApp.getInstance();
        }

        try {
            GoogleCredentials credentials = GoogleCredentials
                    .fromStream(serviceAccountResource.getInputStream())
                    .createScoped("https://www.googleapis.com/auth/firebase.messaging");

            FirebaseOptions options = FirebaseOptions.builder()
                    .setCredentials(credentials)
                    .setProjectId(projectId)
                    .build();

            FirebaseApp app = FirebaseApp.initializeApp(options);
            log.info("[Firebase] ✅ Initialisé — projet: {}", projectId);
            return app;

        } catch (IOException e) {
            log.warn("[Firebase] ⚠️  Impossible d'initialiser Firebase : {}", e.getMessage());
            log.warn("[Firebase] MS4 démarre en mode dégradé — FCM désactivé");
            log.warn("[Firebase] → Remplacer firebase-service-account.json par le vrai fichier");
            // Retourner null — le service FCM gérera le cas null
            return null;
        }
    }
}
