package ma.transport.ms4notifications.config;

import ma.transport.mscommon.security.JwtUtils;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.client.RestTemplate;

@Configuration
public class JwtUtilsConfig {

    @Value("${jwt.secret}")
    private String secret;

    @Bean
    public JwtUtils jwtUtils() {
        return new JwtUtils(secret);
    }

    @Bean
    public RestTemplate restTemplate() {
        return new RestTemplate();
    }
}
