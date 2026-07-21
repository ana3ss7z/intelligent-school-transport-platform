package ma.transport.ms4notifications.controller;

import java.util.List;
import java.util.Map;

import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import ma.transport.ms4notifications.dto.ConversationResponse;
import ma.transport.ms4notifications.dto.MessageRequest;
import ma.transport.ms4notifications.dto.MessageResponse;
import ma.transport.ms4notifications.service.MessageService;
import ma.transport.mscommon.security.UserPrincipal;

@RestController
@RequestMapping("/api/messages")
@RequiredArgsConstructor
public class MessageController {

    private final MessageService service;

    @PostMapping
    @PreAuthorize("hasAnyRole('ADMIN','CHAUFFEUR')")
    public ResponseEntity<MessageResponse> envoyer(
            @AuthenticationPrincipal UserPrincipal user,
            @Valid @RequestBody MessageRequest req) {
        return ResponseEntity.ok(service.envoyer(user, req));
    }

    @GetMapping("/ma-conversation")
    @PreAuthorize("hasRole('CHAUFFEUR')")
    public ResponseEntity<List<MessageResponse>> maConversation(@AuthenticationPrincipal UserPrincipal user) {
        return ResponseEntity.ok(service.maConversation(user.getUserId()));
    }

    /** Diffusion d'un chauffeur à tous les parents de son bus. */
    @PostMapping("/diffusion")
    @PreAuthorize("hasRole('CHAUFFEUR')")
    public ResponseEntity<Map<String, Integer>> diffuser(
            @AuthenticationPrincipal UserPrincipal user,
            @RequestParam Long busId,
            @Valid @RequestBody MessageRequest req) {
        int n = service.diffuser(user, busId, req.getContenu());
        return ResponseEntity.ok(Map.of("parents", n));
    }

    /** Boîte de réception du parent (diffusions reçues). */
    @GetMapping("/parent")
    @PreAuthorize("hasRole('PARENT')")
    public ResponseEntity<List<MessageResponse>> inboxParent(@AuthenticationPrincipal UserPrincipal user) {
        return ResponseEntity.ok(service.inboxParent(user.getUserId()));
    }

    @GetMapping("/conversations")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<List<ConversationResponse>> conversations() {
        return ResponseEntity.ok(service.conversationsAdmin());
    }

    @GetMapping("/conversation/{chauffeurId}")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<List<MessageResponse>> conversation(@PathVariable Long chauffeurId) {
        return ResponseEntity.ok(service.conversation(chauffeurId));
    }

    @GetMapping("/non-lus")
    @PreAuthorize("hasAnyRole('ADMIN','CHAUFFEUR','PARENT')")
    public ResponseEntity<Map<String, Long>> nonLus(@AuthenticationPrincipal UserPrincipal user) {
        return ResponseEntity.ok(Map.of("count", service.nonLus(user)));
    }
}
