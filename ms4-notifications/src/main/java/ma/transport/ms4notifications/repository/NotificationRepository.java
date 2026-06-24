package ma.transport.ms4notifications.repository;

import java.util.List;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import ma.transport.ms4notifications.entity.Notification;

@Repository
public interface NotificationRepository extends JpaRepository<Notification, Long> {

    List<Notification> findByParentIdOrderByDateEnvoiDesc(Long parentId);

    void deleteByParentId(Long parentId);

    /** Bugfix : count global par statut, sans filtrer sur parentId */
    long countByStatutEnvoi(Notification.StatutEnvoi statut);
}