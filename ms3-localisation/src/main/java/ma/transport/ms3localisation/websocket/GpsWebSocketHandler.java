package ma.transport.ms3localisation.websocket;

import java.util.concurrent.ConcurrentHashMap;

import org.springframework.stereotype.Component;
import org.springframework.web.socket.CloseStatus;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;
import org.springframework.web.socket.handler.TextWebSocketHandler;

import com.fasterxml.jackson.databind.ObjectMapper;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import ma.transport.ms3localisation.dto.PositionResponse;

/**
 * WebSocket Handler GPS
 * =====================
 * Endpoint : ws://localhost:8083/ws/gps
 *
 * Clients connectés (parents, admin) reçoivent en temps réel :
 * - Les positions des bus
 * - Les positions des élèves
 *
 * Format message sortant (JSON) :
 * {
 *   "id": 123,
 *   "cibleType": "BUS",
 *   "cibleId": 5,
 *   "latitude": 33.8935,
 *   "longitude": -5.5547,
 *   "vitesse": 42.5,
 *   "cap": 180.0,
 *   "horodatage": "2026-06-10T10:30:00"
 * }
 *
 * Format message entrant (filtre optionnel) :
 * {"subscribe": "BUS:5"}   → ne recevoir que le bus 5
 * {"subscribe": "ALL"}     → tout recevoir (défaut)
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class GpsWebSocketHandler extends TextWebSocketHandler {

    private final ObjectMapper objectMapper;

    // Sessions actives : sessionId → WebSocketSession
    private final ConcurrentHashMap<String, WebSocketSession> sessions
            = new ConcurrentHashMap<>();

    // Filtre par session : sessionId → "ALL" | "BUS:5" | "ELEVE:42"
    private final ConcurrentHashMap<String, String> filtres
            = new ConcurrentHashMap<>();

    // ─── Connexion ────────────────────────────────────────────────────────────

    @Override
    public void afterConnectionEstablished(WebSocketSession session) {
        sessions.put(session.getId(), session);
        filtres.put(session.getId(), "ALL"); // par défaut tout recevoir
        log.info("[WS] Client connecté — id={} | total={}",
                session.getId(), sessions.size());
    }

    // ─── Message reçu (filtre d'abonnement) ──────────────────────────────────

    @Override
    protected void handleTextMessage(WebSocketSession session, TextMessage message) {
        try {
            String payload = message.getPayload();
            var node = objectMapper.readTree(payload);

            if (node.has("subscribe")) {
                String filtre = node.get("subscribe").asText("ALL").toUpperCase();
                filtres.put(session.getId(), filtre);
                log.debug("[WS] Client {} s'abonne à : {}", session.getId(), filtre);

                // Confirmer l'abonnement
                session.sendMessage(new TextMessage(
                        "{\"type\":\"subscribed\",\"filtre\":\"" + filtre + "\"}"
                ));
            }
        } catch (Exception e) {
            log.warn("[WS] Message invalide du client {} : {}", session.getId(), e.getMessage());
        }
    }

    // ─── Déconnexion ─────────────────────────────────────────────────────────

    @Override
    public void afterConnectionClosed(WebSocketSession session, CloseStatus status) {
        sessions.remove(session.getId());
        filtres.remove(session.getId());
        log.info("[WS] Client déconnecté — id={} | raison={} | restants={}",
                session.getId(), status.getReason(), sessions.size());
    }

    @Override
    public void handleTransportError(WebSocketSession session, Throwable exception) {
        log.warn("[WS] Erreur transport client {} : {}", session.getId(), exception.getMessage());
        sessions.remove(session.getId());
        filtres.remove(session.getId());
    }

    // ─── Diffusion (appelé par GpsService) ───────────────────────────────────

    public void broadcast(PositionResponse position) {
        if (sessions.isEmpty()) return;

        String cibleKey = position.getCibleType().name() + ":" + position.getCibleId();

        try {
            String json = objectMapper.writeValueAsString(position);
            TextMessage msg = new TextMessage(json);

            sessions.forEach((sessionId, session) -> {
                if (!session.isOpen()) {
                    sessions.remove(sessionId);
                    return;
                }

                String filtre = filtres.getOrDefault(sessionId, "ALL");

                // Envoyer si le client écoute tout ou ce type/id précis
                boolean doitEnvoyer = "ALL".equals(filtre) || filtre.equals(cibleKey);

                if (doitEnvoyer) {
                    try {
                        session.sendMessage(msg);
                    } catch (Exception e) {
                        log.warn("[WS] Envoi échoué vers {} : {}", sessionId, e.getMessage());
                        sessions.remove(sessionId);
                    }
                }
            });

        } catch (Exception e) {
            log.error("[WS] Erreur sérialisation position : {}", e.getMessage());
        }
    }

    // ─── Stats ────────────────────────────────────────────────────────────────

    public int getNbClientsConnectes() {
        return sessions.size();
    }
}