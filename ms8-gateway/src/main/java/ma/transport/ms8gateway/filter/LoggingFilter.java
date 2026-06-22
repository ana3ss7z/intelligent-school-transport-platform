package ma.transport.ms8gateway.filter;

import lombok.extern.slf4j.Slf4j;
import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.core.Ordered;
import org.springframework.http.server.reactive.ServerHttpRequest;
import org.springframework.http.server.reactive.ServerHttpResponse;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

/**
 * Filtre global de logging — s'applique à TOUTES les requêtes.
 * S'exécute en premier (ORDER = -1) et loggue :
 *  - À l'entrée  : méthode, path, IP, headers importants
 *  - À la sortie : status HTTP + durée en ms
 */
@Slf4j
@Component
public class LoggingFilter implements GlobalFilter, Ordered {

    @Override
    public int getOrder() {
        // -1 = s'exécute avant tous les autres filtres
        return -1;
    }

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        ServerHttpRequest request = exchange.getRequest();

        String method     = request.getMethod().name();
        String path       = request.getURI().getPath();
        String remoteAddr = getClientIp(request);
        long   startTime  = System.currentTimeMillis();

        // Log entrant
        log.info("[Gateway] ➜ {} {} | IP: {} | User-Agent: {}",
                method,
                path,
                remoteAddr,
                getHeader(request, "User-Agent", "inconnu")
        );

        return chain.filter(exchange)
                .then(Mono.fromRunnable(() -> {
                    ServerHttpResponse response = exchange.getResponse();
                    long duration = System.currentTimeMillis() - startTime;

                    int statusCode = response.getStatusCode() != null
                            ? response.getStatusCode().value()
                            : 0;

                    // Log sortant avec durée
                    if (statusCode >= 400) {
                        log.warn("[Gateway] ✗ {} {} → {} | {}ms | IP: {}",
                                method, path, statusCode, duration, remoteAddr);
                    } else {
                        log.info("[Gateway] ✓ {} {} → {} | {}ms",
                                method, path, statusCode, duration);
                    }
                }));
    }

    // ─── Helpers ────────────────────────────────────────────────

    private String getClientIp(ServerHttpRequest request) {
        String xForwardedFor = request.getHeaders().getFirst("X-Forwarded-For");
        if (xForwardedFor != null && !xForwardedFor.isBlank()) {
            return xForwardedFor.split(",")[0].trim();
        }
        if (request.getRemoteAddress() != null) {
            return request.getRemoteAddress().getAddress().getHostAddress();
        }
        return "unknown";
    }

    private String getHeader(ServerHttpRequest request, String headerName, String defaultVal) {
        String val = request.getHeaders().getFirst(headerName);
        if (val == null || val.isBlank()) return defaultVal;
        // Tronquer si trop long (ex: User-Agent verbeux)
        return val.length() > 80 ? val.substring(0, 80) + "…" : val;
    }
}
