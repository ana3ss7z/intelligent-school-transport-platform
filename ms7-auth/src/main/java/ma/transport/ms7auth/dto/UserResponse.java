package ma.transport.ms7auth.dto;

import lombok.Builder;
import lombok.Data;
import ma.transport.ms7auth.enums.Role;

/** Vue publique d'un utilisateur — SANS mot de passe (jamais exposé). */
@Data
@Builder
public class UserResponse {
    private Long id;
    private String nom;
    private String email;
    private Role role;
    private String telephone;
}
