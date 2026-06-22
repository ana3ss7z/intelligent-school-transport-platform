package ma.transport.ms8gateway.filter;

import java.nio.charset.StandardCharsets;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.cloud.gateway.filter.GatewayFilter;
import org.springframework.cloud.gateway.filter.factory.AbstractGatewayFilterFactory;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.server.reactive.ServerHttpRequest;
import org.springframework.http.server.reactive.ServerHttpResponse;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;

import lombok.extern.slf4j.Slf4j;
import ma.transport.mscommon.security.JwtUtils;
import reactor.core.publisher.Mono;

/**
 * Filtre Gateway JWT — valide le token Bearer sur chaque route protégée.
 *
 * Fonctionnement :
 *  1. Extrait le header Authorization: Bearer <token>
 *  2. Valide le token via JwtUtils (ms-common)
 *  3. Injecte X-User-Email, X-User-Role, X-User-Id dans les headers
 *     → Les microservices peuvent lire ces headers sans re-valider
 *  4. Rejette avec 401 si token absent/invalide
 *
 * Utilisé dans application.yml avec : - JwtAuthFilter
 */
@Slf4j
@Component
public class JwtAuthFilter extends AbstractGatewayFilterFactory<JwtAuthFilter.Config> {

    private final JwtUtils jwtUtils;

    @Autowired
    public JwtAuthFilter(JwtUtils jwtUtils) {
        super(Config.class);
        this.jwtUtils = jwtUtils;
    }

    @Override
    public GatewayFilter apply(Config config) {
        return (exchange, chain) -> {
            ServerHttpRequest request = exchange.getRequest();
            String path = request.getURI().getPath();
            String method = request.getMethod().name();

            log.debug("[Gateway] {} {}", method, path);

            // 0. Laisser passer les preflight CORS (OPTIONS) sans vérifier le JWT
            //    Le navigateur n'envoie jamais de token sur un preflight —
            //    le bloquer ici casse CORS et provoque "Failed to fetch" côté client.
            if (org.springframework.http.HttpMethod.OPTIONS.equals(request.getMethod())) {
                return chain.filter(exchange);
            }

            // 1. Récupérer le header Authorization
            String authHeader = request.getHeaders().getFirst(HttpHeaders.AUTHORIZATION);

            if (authHeader == null || !authHeader.startsWith("Bearer ")) {
                log.warn("[Gateway] Token manquant — {} {}", method, path);
                return rejectUnauthorized(exchange, "Token d'authentification manquant");
            }

            String token = authHeader.substring(7); // Enlève "Bearer "

            // 2. Valider le token
            try {
                if (!jwtUtils.isTokenValid(token)) {
                    log.warn("[Gateway] Token invalide — {} {}", method, path);
                    return rejectUnauthorized(exchange, "Token invalide ou expiré");
                }

                // 3. Extraire les claims
                String email  = jwtUtils.extractEmail(token);
                String role   = jwtUtils.extractRole(token).name();
                Long   userId = jwtUtils.extractUserId(token);

                log.debug("[Gateway] Token valide — user={} role={} → {} {}",
                        email, role, method, path);

                // 4. Propager les infos via headers internes
                //    Les MS pourront lire X-User-Email etc. directement
                ServerHttpRequest mutatedRequest = request.mutate()
                        .header("X-User-Email",  email)
                        .header("X-User-Role",   role)
                        .header("X-User-Id",     String.valueOf(userId))
                        .build();

                return chain.filter(exchange.mutate().request(mutatedRequest).build());

            } catch (Exception e) {
                log.warn("[Gateway] Erreur validation token : {} — {} {}",
                        e.getMessage(), method, path);
                return rejectUnauthorized(exchange, "Token invalide : " + e.getMessage());
            }
        };
    }

    /**
     * Renvoie une réponse 401 JSON propre.
     */
    private Mono<Void> rejectUnauthorized(ServerWebExchange exchange, String message) {
        ServerHttpResponse response = exchange.getResponse();
        response.setStatusCode(HttpStatus.UNAUTHORIZED);
        response.getHeaders().setContentType(MediaType.APPLICATION_JSON);

        String body = """
                {
                  "status": 401,
                  "error": "Unauthorized",
                  "message": "%s",
                  "path": "%s"
                }
                """.formatted(message, exchange.getRequest().getURI().getPath());

        byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
        var buffer = response.bufferFactory().wrap(bytes);
        return response.writeWith(Mono.just(buffer));
    }

    /**
     * Classe de configuration du filtre (vide ici, extensible si besoin).
     */
    public static class Config {
        // Pas de config spécifique pour l'instant
        // Pourrait contenir : roles autorisés, whitelist paths, etc.
    }
}