package ma.transport.ms10incidents.config;

import org.springframework.amqp.core.*;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class RabbitMQConfig {

    @Bean
    public TopicExchange transportExchange() {
        return new TopicExchange("transport.exchange");
    }

    @Bean
    public Queue incidentSignaleQueue() {
        return new Queue("incident.signale.queue", true);
    }

    @Bean
    public Queue incidentResoluQueue() {
        return new Queue("incident.resolu.queue", true);
    }

    @Bean
    public Binding bindingSignale(Queue incidentSignaleQueue,
                                  TopicExchange transportExchange) {
        return BindingBuilder.bind(incidentSignaleQueue)
                .to(transportExchange).with("incident.signale");
    }

    @Bean
    public Binding bindingResolu(Queue incidentResoluQueue,
                                 TopicExchange transportExchange) {
        return BindingBuilder.bind(incidentResoluQueue)
                .to(transportExchange).with("incident.resolu");
    }
}
