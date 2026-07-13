package ma.transport.ms1bus.config;

import org.springframework.amqp.core.TopicExchange;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * MS1 publie des événements de flotte sur l'exchange partagé (déclencheur clustering MS6).
 * Producteur uniquement : on déclare l'exchange, les queues/bindings sont côté consommateurs (MS6).
 */
@Configuration
public class RabbitMQConfig {

    public static final String EXCHANGE = "transport.exchange";

    @Bean
    public TopicExchange transportExchange() {
        return new TopicExchange(EXCHANGE, true, false);
    }
}
