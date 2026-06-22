package ma.transport.ms10incidents;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication(scanBasePackages = {
        "ma.transport.ms10incidents",
        "ma.transport.mscommon"
})
public class Ms10IncidentsApplication {
    public static void main(String[] args) {
        SpringApplication.run(Ms10IncidentsApplication.class, args);
    }
}