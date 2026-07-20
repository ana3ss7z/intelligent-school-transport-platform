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

    // ETA temps réel (G1) : MS12 publie eta.bus.arriving quand le bus arrive ~10 min avant l'école
    @Bean
    public Queue ms4EtaArrivingQueue() {
        return new Queue("ms4.eta.arriving.queue", true);
    }

    // Présence (G5) : MS2 publie eleve.presence.updated quand l'enfant monte dans le bus
    @Bean
    public Queue ms4ElevePresenceQueue() {
        return new Queue("ms4.eleve.presence.queue", true);
    }

    // Canal admin (D1) : alertes qualité clustering (MS6) et anomalies GPS (MS11)
    @Bean
    public Queue ms4QualityQueue() {
        return new Queue("ms4.quality.queue", true);
    }

    @Bean
    public Queue ms4AnomalieQueue() {
        return new Queue("ms4.anomalie.queue", true);
    }

    // Canal admin : trajets démarrés/terminés par les chauffeurs (MS1)
    @Bean
    public Queue ms4TrajetQueue() {
        return new Queue("ms4.trajet.queue", true);
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

    @Bean
    public Binding bindingEtaArriving(Queue ms4EtaArrivingQueue,
                                      TopicExchange transportExchange) {
        return BindingBuilder.bind(ms4EtaArrivingQueue)
                .to(transportExchange).with("eta.bus.arriving");
    }

    @Bean
    public Binding bindingElevePresence(Queue ms4ElevePresenceQueue,
                                        TopicExchange transportExchange) {
        return BindingBuilder.bind(ms4ElevePresenceQueue)
                .to(transportExchange).with("eleve.presence.updated");
    }

    @Bean
    public Binding bindingTrajetDemarre(Queue ms4TrajetQueue, TopicExchange transportExchange) {
        return BindingBuilder.bind(ms4TrajetQueue).to(transportExchange).with("trajet.demarre");
    }

    @Bean
    public Binding bindingTrajetTermine(Queue ms4TrajetQueue, TopicExchange transportExchange) {
        return BindingBuilder.bind(ms4TrajetQueue).to(transportExchange).with("trajet.termine");
    }

    @Bean
    public Binding bindingQuality(Queue ms4QualityQueue, TopicExchange transportExchange) {
        return BindingBuilder.bind(ms4QualityQueue).to(transportExchange).with("clustering.quality.low");
    }

    @Bean
    public Binding bindingAnomalie(Queue ms4AnomalieQueue, TopicExchange transportExchange) {
        return BindingBuilder.bind(ms4AnomalieQueue).to(transportExchange).with("anomalie.detectee");
    }

    // ─── JSON message converter ───────────────────────────────────────────────

    @Bean
    public Jackson2JsonMessageConverter messageConverter() {
        return new Jackson2JsonMessageConverter();
    }
}
