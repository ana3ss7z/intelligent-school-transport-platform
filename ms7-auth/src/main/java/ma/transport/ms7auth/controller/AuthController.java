package ma.transport.ms7auth.controller;

import java.util.List;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import ma.transport.ms7auth.dto.AuthResponse;
import ma.transport.ms7auth.dto.LoginRequest;
import ma.transport.ms7auth.dto.RegisterRequest;
import ma.transport.ms7auth.dto.UserResponse;
import ma.transport.ms7auth.entity.Utilisateur;
import ma.transport.ms7auth.enums.Role;
import ma.transport.ms7auth.repository.UtilisateurRepository;
import ma.transport.ms7auth.security.JwtService;

@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor
// @CrossOrigin(origins = "*")
public class AuthController {

    private final UtilisateurRepository repo;
    private final JwtService jwtService;
    private final PasswordEncoder encoder;

    // ── Inscription ──────────────────────────────────────────────────
    @PostMapping("/register")
    public ResponseEntity<?> register(
            @Valid @RequestBody RegisterRequest req) {

        if (repo.existsByEmail(req.getEmail())) {
            return ResponseEntity.badRequest()
                    .body("Email déjà utilisé.");
        }

        Utilisateur user = Utilisateur.builder()
                .nom(req.getNom())
                .email(req.getEmail())
                .motDePasse(encoder.encode(req.getMotDePasse()))
                .role(req.getRole())
                .telephone(req.getTelephone())
                .build();

        repo.save(user);

        String token = jwtService.generateToken(user);

        return ResponseEntity.status(HttpStatus.CREATED)
                .body(AuthResponse.builder()
                        .token(token)
                        .userId(user.getId())
                        .nom(user.getNom())
                        .email(user.getEmail())
                        .role(user.getRole())
                        .build());
    }

    // ── Connexion ────────────────────────────────────────────────────
    @PostMapping("/login")
    public ResponseEntity<?> login(
            @Valid @RequestBody LoginRequest req) {

        Utilisateur user = repo.findByEmail(req.getEmail())
                .orElse(null);

        if (user == null ||
            !encoder.matches(req.getMotDePasse(), user.getMotDePasse())) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                    .body("Email ou mot de passe incorrect.");
        }

        String token = jwtService.generateToken(user);

        return ResponseEntity.ok(AuthResponse.builder()
                .token(token)
                .userId(user.getId())
                .nom(user.getNom())
                .email(user.getEmail())
                .role(user.getRole())
                .build());
    }

    // ── Liste des utilisateurs (ADMIN) ───────────────────────────────
    // Sécurisé par SecurityConfig (hasRole ADMIN). Ne renvoie JAMAIS le mot de passe.
    @GetMapping("/users")
    public ResponseEntity<List<UserResponse>> getUsers(
            @RequestParam(required = false) Role role) {

        List<UserResponse> users = repo.findAll().stream()
                .filter(u -> role == null || u.getRole() == role)
                .map(u -> UserResponse.builder()
                        .id(u.getId())
                        .nom(u.getNom())
                        .email(u.getEmail())
                        .role(u.getRole())
                        .telephone(u.getTelephone())
                        .build())
                .toList();

        return ResponseEntity.ok(users);
    }

    // ── Vérification token ───────────────────────────────────────────
    @GetMapping("/validate")
    public ResponseEntity<?> validate(
            @RequestHeader("Authorization") String authHeader) {

        if (authHeader == null || !authHeader.startsWith("Bearer ")) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                    .body("Token manquant.");
        }

        String token = authHeader.substring(7);

        if (!jwtService.isTokenValid(token)) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                    .body("Token invalide ou expiré.");
        }

        return ResponseEntity.ok("Token valide — " +
                jwtService.extractEmail(token) +
                " [" + jwtService.extractRole(token) + "]");
    }
}