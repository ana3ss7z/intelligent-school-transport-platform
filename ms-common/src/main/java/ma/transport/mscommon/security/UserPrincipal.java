package ma.transport.mscommon.security;

import ma.transport.mscommon.enums.Role;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@AllArgsConstructor
@NoArgsConstructor
public class UserPrincipal {
    private String email;
    private Role role;
    private Long userId;
}