package ma.transport.ms4notifications.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

@Data
public class DeviceTokenRequest {

    @NotBlank(message = "Le token FCM est obligatoire")
    private String fcmToken;

    private String plateforme; // ANDROID, IOS, WEB
}
