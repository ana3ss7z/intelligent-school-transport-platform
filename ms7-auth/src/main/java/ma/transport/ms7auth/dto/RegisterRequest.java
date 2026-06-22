package ma.transport.ms7auth.dto;

import jakarta.validation.constraints.*;
import lombok.Data;
import ma.transport.ms7auth.enums.Role;

@Data
public class RegisterRequest {
    @NotBlank
    private String nom;

    @Email @NotBlank
    private String email;

    @NotBlank @Size(min = 6)
    private String motDePasse;

    @NotNull
    private Role role;

    private String telephone;
}