package ma.transport.ms4notifications.repository;

import java.util.List;

import org.springframework.data.jpa.repository.JpaRepository;

import ma.transport.ms4notifications.entity.Message;

public interface MessageRepository extends JpaRepository<Message, Long> {

    // ── Fils chauffeur ↔ admin (hors diffusions) ──
    List<Message> findByConversationChauffeurIdAndDiffusionFalseOrderByDateEnvoiAsc(Long conversationChauffeurId);

    long countByDestinataireRoleAndLuFalse(String destinataireRole);

    long countByConversationChauffeurIdAndDestinataireRoleAndLuFalse(Long conversationChauffeurId, String destinataireRole);

    List<Message> findByConversationChauffeurIdAndDestinataireRoleAndLuFalse(Long conversationChauffeurId, String destinataireRole);

    List<Message> findByDiffusionFalseOrderByDateEnvoiDesc();

    // ── Boîte parent (diffusions reçues) ──
    List<Message> findByDestinataireIdOrderByDateEnvoiDesc(Long destinataireId);

    long countByDestinataireIdAndLuFalse(Long destinataireId);

    List<Message> findByDestinataireIdAndLuFalse(Long destinataireId);
}
