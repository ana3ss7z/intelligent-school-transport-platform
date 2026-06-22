package ma.transport.ms4notifications.repository;

import ma.transport.ms4notifications.entity.DeviceToken;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface DeviceTokenRepository extends JpaRepository<DeviceToken, Long> {

    List<DeviceToken> findByParentIdAndActifTrue(Long parentId);

    Optional<DeviceToken> findByFcmToken(String fcmToken);

    boolean existsByFcmToken(String fcmToken);
}