package ma.transport.ms3localisation.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.socket.config.annotation.EnableWebSocket;
import org.springframework.web.socket.config.annotation.WebSocketConfigurer;
import org.springframework.web.socket.config.annotation.WebSocketHandlerRegistry;

import lombok.RequiredArgsConstructor;
import ma.transport.ms3localisation.websocket.GpsWebSocketHandler;

/**
 * Configuration WebSocket
 * =======================
 * Endpoint : /ws/gps
 *
 * Connexion depuis le front :
 *   const ws = new WebSocket("ws://localhost:8083/ws/gps");
 *
 * Via la Gateway (MS8) :
 *   const ws = new WebSocket("ws://localhost:8080/ws/gps");
 *   (la Gateway doit être configurée pour proxifier les WebSockets)
 */
@Configuration
@EnableWebSocket
@RequiredArgsConstructor
public class WebSocketConfig implements WebSocketConfigurer {

    private final GpsWebSocketHandler gpsWebSocketHandler;

    @Override
    public void registerWebSocketHandlers(WebSocketHandlerRegistry registry) {
        registry
            .addHandler(gpsWebSocketHandler, "/ws/gps")
            .setAllowedOrigins("*");  // CORS — à restreindre en production
    }
}