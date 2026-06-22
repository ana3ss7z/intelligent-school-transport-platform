package ma.transport.ms3localisation.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import ma.transport.mscommon.security.JwtUtils;

@Configuration
public class JwtUtilsConfig {

    @Value("${jwt.secret}")
    private String secret;

    @Bean
    public JwtUtils jwtUtils() {
        return new JwtUtils(secret);
    }
}