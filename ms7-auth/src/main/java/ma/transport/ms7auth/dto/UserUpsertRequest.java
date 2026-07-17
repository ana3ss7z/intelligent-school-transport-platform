package ma.transport.ms7auth.dto;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Data;
import ma.transport.ms7auth.enums.Role;

/** Création / édition d'un utilisateur par l'ADMIN.
 *  motDePasse : requis à la création ; à l'édition, vide/absent = inchangé. */
@Data
public class UserUpsertRequest {
    @NotBlank
    private String nom;

    @Email @NotBlank
    private String email;

    @NotNull
    private Role role;

    private String telephone;

    private String motDePasse; // optionnel (édition)
}
