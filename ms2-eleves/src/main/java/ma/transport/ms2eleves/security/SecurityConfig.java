package ma.transport.ms2eleves.security;

import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.web.AuthenticationEntryPoint;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;

@Configuration
@EnableWebSecurity
@EnableMethodSecurity
@RequiredArgsConstructor
public class SecurityConfig {

    private final JwtAuthFilter jwtAuthFilter;

    @Bean
    public AuthenticationEntryPoint authenticationEntryPoint() {
        return (request, response, authException) -> {
            String msg = request.getAttribute("jwt_error") != null
                    ? "Token invalide"
                    : "Token manquant";
            response.setStatus(401);
            response.setContentType("application/json;charset=UTF-8");
            response.getWriter().write("{\"error\":\"" + msg + "\"}");
        };
    }

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
            .csrf(csrf -> csrf.disable())
            .sessionManagement(sm -> sm.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            .exceptionHandling(ex -> ex
                .authenticationEntryPoint(authenticationEntryPoint())
                .accessDeniedHandler((request, response, accessDeniedException) -> {
                    // Sans ce gestionnaire, un refus d'AUTORISATION ressortait en 401, que le
                    // client HTTP du front interprete comme une session expiree : un chauffeur
                    // qui touchait une route d'administration etait DECONNECTE de la console au
                    // lieu de voir un refus (defaut C2 de la recette du 26/08).
                    response.setStatus(HttpServletResponse.SC_FORBIDDEN); // 403
                    response.setContentType("application/json;charset=UTF-8");
                    response.getWriter().write("{\"error\": \"Acces refuse\"}");
                })
            )
            .authorizeHttpRequests(auth -> auth
                // ── Routes internes (pas de JWT) ──────────────────────────
                // MS4 → MS2 : récupérer les parentIds d'un bus pour les notifs FCM
                .requestMatchers(HttpMethod.GET,  "/api/eleves/bus/*/parents").permitAll()
                // MS6 → MS2 : assigner un groupe après clustering
                .requestMatchers(HttpMethod.PATCH, "/api/eleves/*/groupe").permitAll()
                // MS6 → MS2 : lister les élèves sans groupe (point de départ)
                .requestMatchers(HttpMethod.GET,  "/api/eleves/sans-groupe").permitAll()
                .requestMatchers(HttpMethod.PUT, "/api/eleves/groupes/bulk").permitAll()
                // MS6 → MS2 : propager busId après liaison groupe↔bus
                .requestMatchers(HttpMethod.PUT, "/api/eleves/bus/bulk").permitAll()
                // MS5 → MS2 : persister l'ordre de passage des tournées
                .requestMatchers(HttpMethod.PUT, "/api/eleves/ordre/bulk").permitAll()

                // MS5 · MS6 · MS12 → MS2 : effectif complet, pour les services sans jeton
                // utilisateur. Le chemin est volontairement HORS de /api/eleves/** : le
                // prédicat de la passerelle est Path=/api/eleves/**, donc une route interne
                // placée sous ce préfixe resterait joignable depuis le web. Voir
                // InternalEleveController pour le raisonnement complet.
                // ⚠️ Ne jamais router /internal/** dans ms8-gateway/application.yml.
                .requestMatchers(HttpMethod.GET, "/internal/eleves").permitAll()
                // MS1 · MS3 · MS10 → MS2 : bus des enfants d'un parent, pour vérifier
                // qu'une lecture par bus concerne bien une famille du bus.
                .requestMatchers(HttpMethod.GET, "/internal/parents/*/bus").permitAll()

                // ── Toutes les autres routes nécessitent un JWT ───────────
                .anyRequest().authenticated()
            )
            .addFilterBefore(jwtAuthFilter, UsernamePasswordAuthenticationFilter.class);

        return http.build();
    }
}