package ma.transport.ms13parametres.config;

import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import ma.transport.ms13parametres.security.JwtAuthFilter;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;

@Configuration
@EnableWebSecurity
@EnableMethodSecurity
@RequiredArgsConstructor
public class SecurityConfig {

    private final JwtAuthFilter jwtAuthFilter;

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
            .csrf(csrf -> csrf.disable())
            .sessionManagement(sess -> sess
                .sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            .exceptionHandling(ex -> ex
                .authenticationEntryPoint((request, response, authException) -> {
                    response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
                    response.setContentType("application/json");
                    String authHeader = request.getHeader("Authorization");
                    String msg = (authHeader == null || !authHeader.startsWith("Bearer "))
                            ? "Token manquant" : "Token invalide";
                    response.getWriter().write("{\"error\": \"" + msg + "\"}");
                })
                .accessDeniedHandler((request, response, accessEx) -> {
                    response.setStatus(HttpServletResponse.SC_FORBIDDEN);
                    response.setContentType("application/json");
                    response.getWriter().write("{\"error\": \"Accès refusé\"}");
                })
            )
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/actuator/health").permitAll()
                // Route interne : les services Python et MS4 n'ont pas de jeton utilisateur à
                // présenter. Sa protection ne vient pas d'un rôle mais du fait qu'elle n'est PAS
                // routée par la passerelle — donc injoignable depuis le web (même motif que les
                // routes internes de MS2 pour MS6). Ne jamais ajouter de prédicat
                // /api/parametres/internal/** dans ms8-gateway/application.yml.
                .requestMatchers(HttpMethod.GET, "/api/parametres/internal").permitAll()
                .anyRequest().authenticated()
            )
            .addFilterBefore(jwtAuthFilter, UsernamePasswordAuthenticationFilter.class);

        return http.build();
    }
}
