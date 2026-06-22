package ma.transport.ms8gateway;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication(scanBasePackages = {
        "ma.transport.ms8gateway",
        "ma.transport.mscommon"
})
public class Ms8GatewayApplication {

    public static void main(String[] args) {
        SpringApplication.run(Ms8GatewayApplication.class, args);
    }
}
