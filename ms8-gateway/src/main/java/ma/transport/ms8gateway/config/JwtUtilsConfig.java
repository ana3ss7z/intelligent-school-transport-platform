package ma.transport.ms8gateway.config;

import ma.transport.mscommon.security.JwtUtils;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * Instancie JwtUtils (Java pur, pas @Component) comme @Bean Spring.
 * Même pattern que MS1 et MS2.
 */
@Configuration
public class JwtUtilsConfig {

    @Value("${jwt.secret}")
    private String jwtSecret;

    @Bean
    public JwtUtils jwtUtils() {
        return new JwtUtils(jwtSecret);
    }
}
