package ma.transport.ms4notifications.service;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import ma.transport.ms4notifications.dto.ConversationResponse;
import ma.transport.ms4notifications.dto.MessageRequest;
import ma.transport.ms4notifications.dto.MessageResponse;
import ma.transport.ms4notifications.entity.Message;
import ma.transport.ms4notifications.repository.MessageRepository;
import ma.transport.mscommon.security.UserPrincipal;

@Slf4j
@Service
@RequiredArgsConstructor
public class MessageService {

    private static final String ROLE_ADMIN = "ADMIN";
    private static final String ROLE_CHAUFFEUR = "CHAUFFEUR";
    private static final String ROLE_PARENT = "PARENT";

    private final MessageRepository repo;
    private final ParentLookupService parentLookup;
    private final BusLookupService busLookup;

    /** Envoie un message. Chauffeur → administration ; Admin → un chauffeur précis. */
    @Transactional
    public MessageResponse envoyer(UserPrincipal exp, MessageRequest req) {
        String role = exp.getRole().name();
        Long convId;
        Long destId;
        String destRole;

        if (ROLE_CHAUFFEUR.equals(role)) {
            convId = exp.getUserId();          // son propre fil
            destId = null;                     // adressé à l'administration
            destRole = ROLE_ADMIN;
        } else if (ROLE_ADMIN.equals(role)) {
            if (req.getDestinataireId() == null) {
                throw new IllegalArgumentException("destinataireId (chauffeur) requis pour un message admin.");
            }
            convId = req.getDestinataireId();  // le fil du chauffeur visé
            destId = req.getDestinataireId();
            destRole = ROLE_CHAUFFEUR;
        } else {
            throw new IllegalArgumentException("Rôle non autorisé à la messagerie : " + role);
        }

        Message m = repo.save(Message.builder()
                .conversationChauffeurId(convId)
                .expediteurId(exp.getUserId())
                .expediteurNom(exp.getEmail())     // fallback ; le front affiche le vrai nom
                .expediteurRole(role)
                .destinataireId(destId)
                .destinataireRole(destRole)
                .contenu(req.getContenu())
                .lu(false)
                .dateEnvoi(LocalDateTime.now())
                .build());
        log.info("[MS4] Message {} : {} → fil chauffeur {}", m.getId(), role, convId);
        return MessageResponse.from(m);
    }

    /** Fil du chauffeur connecté (+ marque lus les messages qui lui sont destinés). */
    @Transactional
    public List<MessageResponse> maConversation(Long chauffeurId) {
        marquerLus(chauffeurId, ROLE_CHAUFFEUR);
        return fil(chauffeurId);
    }

    /** Fil d'un chauffeur vu par l'admin (+ marque lus les messages destinés à l'admin). */
    @Transactional
    public List<MessageResponse> conversation(Long chauffeurId) {
        marquerLus(chauffeurId, ROLE_ADMIN);
        return fil(chauffeurId);
    }

    /** Liste des fils pour l'admin (dernier message + non-lus admin), les plus récents d'abord. */
    public List<ConversationResponse> conversationsAdmin() {
        Map<Long, ConversationResponse> parFil = new LinkedHashMap<>();
        for (Message m : repo.findByDiffusionFalseOrderByDateEnvoiDesc()) {
            Long cid = m.getConversationChauffeurId();
            ConversationResponse c = parFil.get(cid);
            if (c == null) {
                // 1er rencontré = le plus récent (liste triée desc)
                parFil.put(cid, ConversationResponse.builder()
                        .chauffeurId(cid)
                        .chauffeurNom(ROLE_CHAUFFEUR.equals(m.getExpediteurRole()) ? m.getExpediteurNom() : null)
                        .dernierMessage(m.getContenu())
                        .dateDernier(m.getDateEnvoi())
                        .nonLus(0)
                        .build());
            } else if (c.getChauffeurNom() == null && ROLE_CHAUFFEUR.equals(m.getExpediteurRole())) {
                c.setChauffeurNom(m.getExpediteurNom());
            }
        }
        // non-lus admin par fil
        for (ConversationResponse c : parFil.values()) {
            c.setNonLus(repo.countByConversationChauffeurIdAndDestinataireRoleAndLuFalse(c.getChauffeurId(), ROLE_ADMIN));
        }
        return new ArrayList<>(parFil.values());
    }

    /** Diffusion d'un chauffeur à tous les parents de son bus/groupe. Retourne le nb de parents touchés. */
    @Transactional
    public int diffuser(UserPrincipal chauffeur, Long busId, String contenu) {
        Long proprietaire = busLookup.getChauffeurParBus(busId);
        if (proprietaire == null || !proprietaire.equals(chauffeur.getUserId())) {
            throw new IllegalStateException("Ce bus ne vous est pas affecté.");
        }
        List<Long> parents = parentLookup.getParentsParBus(busId);
        LocalDateTime now = LocalDateTime.now();
        List<Message> lot = parents.stream().map(parentId -> Message.builder()
                .conversationChauffeurId(chauffeur.getUserId())
                .expediteurId(chauffeur.getUserId())
                .expediteurNom(chauffeur.getEmail())
                .expediteurRole(ROLE_CHAUFFEUR)
                .destinataireId(parentId)
                .destinataireRole(ROLE_PARENT)
                .contenu(contenu)
                .diffusion(true)
                .lu(false)
                .dateEnvoi(now)
                .build()).toList();
        repo.saveAll(lot);
        log.info("[MS4] Diffusion chauffeur {} → {} parents (bus {})", chauffeur.getUserId(), lot.size(), busId);
        return lot.size();
    }

    /** Boîte de réception du parent (diffusions reçues) + marque lus. */
    @Transactional
    public List<MessageResponse> inboxParent(Long parentId) {
        List<Message> aLire = repo.findByDestinataireIdAndLuFalse(parentId);
        if (!aLire.isEmpty()) {
            aLire.forEach(m -> m.setLu(true));
            repo.saveAll(aLire);
        }
        return repo.findByDestinataireIdOrderByDateEnvoiDesc(parentId)
                .stream().map(MessageResponse::from).toList();
    }

    /** Nombre de messages non-lus pour le badge. */
    public long nonLus(UserPrincipal p) {
        String role = p.getRole().name();
        if (ROLE_ADMIN.equals(role)) {
            return repo.countByDestinataireRoleAndLuFalse(ROLE_ADMIN);
        }
        if (ROLE_PARENT.equals(role)) {
            return repo.countByDestinataireIdAndLuFalse(p.getUserId());
        }
        return repo.countByConversationChauffeurIdAndDestinataireRoleAndLuFalse(p.getUserId(), ROLE_CHAUFFEUR);
    }

    // ── Helpers ──────────────────────────────────────────────────────
    private List<MessageResponse> fil(Long chauffeurId) {
        return repo.findByConversationChauffeurIdAndDiffusionFalseOrderByDateEnvoiAsc(chauffeurId)
                .stream().map(MessageResponse::from).toList();
    }

    private void marquerLus(Long chauffeurId, String destRole) {
        List<Message> aLire = repo.findByConversationChauffeurIdAndDestinataireRoleAndLuFalse(chauffeurId, destRole);
        if (!aLire.isEmpty()) {
            aLire.forEach(m -> m.setLu(true));
            repo.saveAll(aLire);
        }
    }
}
