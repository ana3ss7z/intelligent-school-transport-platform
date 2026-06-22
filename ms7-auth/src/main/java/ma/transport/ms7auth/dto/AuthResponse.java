package ma.transport.ms7auth.dto;

import lombok.*;
import ma.transport.ms7auth.enums.Role;

@Data
@Builder
@AllArgsConstructor
@NoArgsConstructor
public class AuthResponse {
    private String token;
    private String type = "Bearer";
    private Long userId;
    private String nom;
    private String email;
    private Role role;
}