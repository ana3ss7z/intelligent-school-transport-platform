package ma.transport.ms13parametres.config;

import org.springframework.amqp.core.TopicExchange;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * MS13 est producteur seulement : il publie {@code parametres.updated} sur l'échange commun.
 * Ce sont les consommateurs (MS4 et les services Python) qui déclarent leurs propres files —
 * chacun choisit ainsi sa durabilité sans que MS13 ait à connaître qui l'écoute.
 */
@Configuration
public class RabbitMQConfig {

    @Bean
    public TopicExchange transportExchange() {
        return new TopicExchange("transport.exchange");
    }
}
