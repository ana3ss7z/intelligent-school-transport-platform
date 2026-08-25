package ma.transport.ms4notifications;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

// @EnableScheduling : filet de rafraîchissement des paramètres (ParametresCache), utile si
// RabbitMQ est indisponible au moment où l'administrateur enregistre un changement.
@EnableScheduling
@SpringBootApplication
public class Ms4NotificationsApplication {

	public static void main(String[] args) {
		SpringApplication.run(Ms4NotificationsApplication.class, args);
	}

}
