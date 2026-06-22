package ma.transport.ms3localisation.config;

import org.springframework.amqp.core.Binding;
import org.springframework.amqp.core.BindingBuilder;
import org.springframework.amqp.core.Queue;
import org.springframework.amqp.core.TopicExchange;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class RabbitMQConfig {

    @Bean
    public TopicExchange transportExchange() {
        return new TopicExchange("transport.exchange");
    }

    // Queue pour les positions GPS bus
    @Bean
    public Queue gpsBusUpdatedQueue() {
        return new Queue("gps.bus.updated.queue", true);
    }

    // Queue pour les positions GPS élèves
    @Bean
    public Queue gpsEleveUpdatedQueue() {
        return new Queue("gps.eleve.updated.queue", true);
    }

    @Bean
    public Binding bindingGpsBus(Queue gpsBusUpdatedQueue, TopicExchange transportExchange) {
        return BindingBuilder.bind(gpsBusUpdatedQueue)
                .to(transportExchange).with("gps.bus.updated");
    }

    @Bean
    public Binding bindingGpsEleve(Queue gpsEleveUpdatedQueue, TopicExchange transportExchange) {
        return BindingBuilder.bind(gpsEleveUpdatedQueue)
                .to(transportExchange).with("gps.eleve.updated");
    }
}