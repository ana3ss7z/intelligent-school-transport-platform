package ma.transport.ms8gateway.config;

import org.springframework.cloud.gateway.filter.ratelimit.KeyResolver;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import reactor.core.publisher.Mono;

/**
 * Résolution de clé pour le rate limiting.
 * Stratégie : par adresse IP du client.
 * Si derrière un reverse proxy, utilise X-Forwarded-For.
 */
@Configuration
public class RateLimiterConfig {

    @Bean
    public KeyResolver ipKeyResolver() {
        return exchange -> {
            // Récupère l'IP réelle si derrière un proxy
            String xForwardedFor = exchange.getRequest()
                    .getHeaders()
                    .getFirst("X-Forwarded-For");

            if (xForwardedFor != null && !xForwardedFor.isBlank()) {
                // Prend la première IP de la chaîne (client original)
                String clientIp = xForwardedFor.split(",")[0].trim();
                return Mono.just(clientIp);
            }

            // Sinon IP directe
            return Mono.justOrEmpty(
                    exchange.getRequest().getRemoteAddress()
            ).map(addr -> addr.getAddress().getHostAddress())
             .defaultIfEmpty("unknown");
        };
    }
}
