package ma.transport.ms3localisation.service;

import java.time.Duration;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import com.fasterxml.jackson.databind.ObjectMapper;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import ma.transport.ms3localisation.dto.PositionRequest;
import ma.transport.ms3localisation.dto.PositionResponse;
import ma.transport.ms3localisation.entity.PositionGPS;
import ma.transport.ms3localisation.entity.PositionGPS.TypeCible;
import ma.transport.ms3localisation.repository.PositionGPSRepository;
import ma.transport.ms3localisation.websocket.GpsWebSocketHandler;

@Slf4j
@Service
@RequiredArgsConstructor
public class GpsService {

    private final PositionGPSRepository repo;
    private final StringRedisTemplate    redis;
    private final RabbitTemplate         rabbitTemplate;
    private final GpsWebSocketHandler    wsHandler;
    private final ObjectMapper           objectMapper;

    // Clé Redis : "gps:BUS:5" ou "gps:ELEVE:42"
    private static final String REDIS_KEY_PREFIX = "gps:";
    private static final Duration REDIS_TTL      = Duration.ofHours(2);

    // ─── Publier une position (appelé par le chauffeur / device GPS) ──────────

    public PositionResponse publierPosition(PositionRequest req) {
        // 1. Persister en base (historique)
        PositionGPS position = PositionGPS.builder()
                .cibleType(req.getCibleType())
                .cibleId(req.getCibleId())
                .latitude(req.getLatitude())
                .longitude(req.getLongitude())
                .vitesse(req.getVitesse())
                .cap(req.getCap())
                .precision(req.getPrecision())
                .horodatage(LocalDateTime.now())
                .build();

        PositionGPS saved = repo.save(position);
        PositionResponse response = PositionResponse.from(saved);

        // 2. Mettre en cache Redis (TTL 2h)
        cachePosition(response);

        // 3. Diffuser via WebSocket à tous les abonnés
        wsHandler.broadcast(response);

        // 4. Publier événement RabbitMQ → MS5 (planification) peut réagir
        publierEvenement(response);

        log.debug("[GPS] Position publiée — {} {} → ({}, {})",
                req.getCibleType(), req.getCibleId(),
                req.getLatitude(), req.getLongitude());

        return response;
    }

    // ─── Dernière position connue (Redis first, DB fallback) ─────────────────

    public Optional<PositionResponse> getDernierePosition(TypeCible type, Long id) {
        // Essayer Redis d'abord (temps réel)
        String key = redisKey(type, id);
        String cached = redis.opsForValue().get(key);

        if (cached != null) {
            try {
                return Optional.of(objectMapper.readValue(cached, PositionResponse.class));
            } catch (Exception e) {
                log.warn("[GPS] Cache Redis corrompu pour {} {} — fallback DB", type, id);
            }
        }

        // Fallback base de données
        return repo.findTopByCibleTypeAndCibleIdOrderByHorodatageDesc(type, id)
                .map(PositionResponse::from);
    }

    // ─── Historique des positions ─────────────────────────────────────────────

    public List<PositionResponse> getHistorique(TypeCible type, Long id) {
        return repo.findByCibleTypeAndCibleIdOrderByHorodatageDesc(type, id)
                .stream()
                .map(PositionResponse::from)
                .toList();
    }

    // ─── Toutes les dernières positions des bus (vue carte) ───────────────────

    public List<PositionResponse> getDernieresPositionsBus() {
        return repo.findDernieresPositionsBus()
                .stream()
                .map(PositionResponse::from)
                .toList();
    }

    // ─── Stats WebSocket ─────────────────────────────────────────────────────

    public int getNbClientsWebSocket() {
        return wsHandler.getNbClientsConnectes();
    }

    // ─── Helpers privés ──────────────────────────────────────────────────────

    private void cachePosition(PositionResponse pos) {
        try {
            String key   = redisKey(pos.getCibleType(), pos.getCibleId());
            String value = objectMapper.writeValueAsString(pos);
            redis.opsForValue().set(key, value, REDIS_TTL);
        } catch (Exception e) {
            log.warn("[GPS] Impossible de cacher la position Redis : {}", e.getMessage());
        }
    }

    private void publierEvenement(PositionResponse pos) {
        try {
            String json = objectMapper.writeValueAsString(pos);
            String routingKey = pos.getCibleType() == TypeCible.BUS
                    ? "gps.bus.updated"
                    : "gps.eleve.updated";
            rabbitTemplate.convertAndSend("transport.exchange", routingKey, json);
        } catch (Exception e) {
            log.warn("[GPS] Impossible de publier l'événement RabbitMQ : {}", e.getMessage());
        }
    }

    private String redisKey(TypeCible type, Long id) {
        return REDIS_KEY_PREFIX + type.name() + ":" + id;
    }
}