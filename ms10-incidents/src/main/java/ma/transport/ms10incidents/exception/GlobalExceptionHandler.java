package ma.transport.ms10incidents.exception;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(RuntimeException.class)
    public ResponseEntity<String> handleRuntime(RuntimeException ex) {
        String msg = ex.getMessage() != null ? ex.getMessage() : "";
        if (msg.contains("non trouvé") || msg.contains("not found")) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND).body(msg);
        }
        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(msg);
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<String> handleValidation(MethodArgumentNotValidException ex) {
        String msg = ex.getBindingResult().getFieldErrors().stream()
                .map(e -> e.getField() + ": " + e.getDefaultMessage())
                .reduce("", (a, b) -> a + "; " + b);
        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(msg);
    }

    @ExceptionHandler(AccessDeniedException.class)
    public ResponseEntity<String> handleAccessDenied(AccessDeniedException ex) {
        return ResponseEntity.status(HttpStatus.FORBIDDEN)
                .body("{\"error\": \"Accès refusé\"}");
    }

    /**
     * Statut HTTP explicite → respecté tel quel.
     *
     * <p>{@code ResponseStatusException} hérite de {@code RuntimeException} : sans ce
     * gestionnaire <b>plus spécifique</b>, elle tombait dans celui du dessus et tout statut
     * choisi par le code — 403 d'un contrôle de propriété, 404 d'une ressource absente —
     * ressortait en <b>400</b>. Le refus fonctionnait, mais le client ne pouvait pas le
     * distinguer d'une requête mal formée. Constaté le 26/08 en vérifiant les correctifs de
     * portée : tous répondaient 400 au lieu de 403.
     */
    @ExceptionHandler(org.springframework.web.server.ResponseStatusException.class)
    public ResponseEntity<String> handleResponseStatus(
            org.springframework.web.server.ResponseStatusException ex) {
        String motif = ex.getReason() != null ? ex.getReason() : ex.getStatusCode().toString();
        return ResponseEntity.status(ex.getStatusCode())
                .body("{\"error\": \"" + motif.replace("\"", "'") + "\"}");
    }
}
