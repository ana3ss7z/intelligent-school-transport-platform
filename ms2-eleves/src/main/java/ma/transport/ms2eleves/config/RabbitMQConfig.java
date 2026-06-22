package ma.transport.ms2eleves.config;

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

    @Bean
    public Queue eleveCreatedQueue() {
        return new Queue("eleve.created.queue", true);
    }

    @Bean
    public Queue eleveGpsUpdatedQueue() {
        return new Queue("eleve.gps.updated.queue", true);
    }

    @Bean
    public Queue eleveDeletedQueue() {
        return new Queue("eleve.deleted.queue", true);
    }

    @Bean
    public Binding bindingCreated(Queue eleveCreatedQueue,
                                   TopicExchange transportExchange) {
        return BindingBuilder.bind(eleveCreatedQueue)
                .to(transportExchange).with("eleve.created");
    }

    @Bean
    public Binding bindingGpsUpdated(Queue eleveGpsUpdatedQueue,
                                      TopicExchange transportExchange) {
        return BindingBuilder.bind(eleveGpsUpdatedQueue)
                .to(transportExchange).with("eleve.gps.updated");
    }

    @Bean
    public Binding bindingDeleted(Queue eleveDeletedQueue,
                                   TopicExchange transportExchange) {
        return BindingBuilder.bind(eleveDeletedQueue)
                .to(transportExchange).with("eleve.deleted");
    }
}
