package ma.transport.ms4notifications.config;

import org.springframework.amqp.core.*;
import org.springframework.amqp.rabbit.config.SimpleRabbitListenerContainerFactory;
import org.springframework.amqp.rabbit.connection.ConnectionFactory;
import org.springframework.amqp.support.converter.Jackson2JsonMessageConverter;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class RabbitMQConfig {

    @Bean
    public TopicExchange transportExchange() {
        return new TopicExchange("transport.exchange");
    }

    // ─── Queues écoutées par MS4 ──────────────────────────────────────────────

    @Bean
    public Queue ms4IncidentSignaleQueue() {
        return new Queue("ms4.incident.signale.queue", true);
    }

    @Bean
    public Queue ms4IncidentResoluQueue() {
        return new Queue("ms4.incident.resolu.queue", true);
    }

    @Bean
    public Queue ms4GpsBusQueue() {
        return new Queue("ms4.gps.bus.updated.queue", true);
    }

    // ─── Bindings ─────────────────────────────────────────────────────────────

    @Bean
    public Binding bindingIncidentSignale(Queue ms4IncidentSignaleQueue,
                                          TopicExchange transportExchange) {
        return BindingBuilder.bind(ms4IncidentSignaleQueue)
                .to(transportExchange).with("incident.signale");
    }

    @Bean
    public Binding bindingIncidentResolu(Queue ms4IncidentResoluQueue,
                                         TopicExchange transportExchange) {
        return BindingBuilder.bind(ms4IncidentResoluQueue)
                .to(transportExchange).with("incident.resolu");
    }

    @Bean
    public Binding bindingGpsBus(Queue ms4GpsBusQueue,
                                 TopicExchange transportExchange) {
        return BindingBuilder.bind(ms4GpsBusQueue)
                .to(transportExchange).with("gps.bus.updated");
    }

    // ─── JSON message converter ───────────────────────────────────────────────

    @Bean
    public Jackson2JsonMessageConverter messageConverter() {
        return new Jackson2JsonMessageConverter();
    }
}
