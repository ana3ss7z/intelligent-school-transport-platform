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

    /*
     * Les files `incident.signale.queue, incident.resolu.queue` ont ete SUPPRIMEES le 27/08.
     *
     * Ce service les DECLARAIT — durables, liees a ses propres cles de routage — sans jamais
     * les consommer : il n'a aucun @RabbitListener. Les vrais destinataires de ces evenements
     * (MS4, MS6, MS11, MS12) declarent chacun leur propre file. Chaque message publie
     * atterrissait donc AUSSI dans une file que personne ne lit : 29 000 messages accumules,
     * et une pile qui ne redescend jamais.
     *
     * L'echange reste declare ci-dessus : c'est lui que les publieurs utilisent. Declarer une
     * file n'a de sens que pour qui la consomme.
     */
}
