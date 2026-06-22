package ma.transport.ms4notifications.repository;

import ma.transport.ms4notifications.entity.Notification;
import ma.transport.ms4notifications.entity.Notification.StatutEnvoi;
import ma.transport.ms4notifications.entity.Notification.TypeNotification;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface NotificationRepository extends JpaRepository<Notification, Long> {

    List<Notification> findByParentIdOrderByDateEnvoiDesc(Long parentId);

    List<Notification> findByStatutEnvoiOrderByDateEnvoiDesc(StatutEnvoi statut);

    List<Notification> findByTypeOrderByDateEnvoiDesc(TypeNotification type);

    long countByParentIdAndStatutEnvoi(Long parentId, StatutEnvoi statut);
}