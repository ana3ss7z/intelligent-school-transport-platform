package ma.transport.ms13parametres;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication(scanBasePackages = {
        "ma.transport.ms13parametres",
        "ma.transport.mscommon"
})
public class Ms13ParametresApplication {
    public static void main(String[] args) {
        SpringApplication.run(Ms13ParametresApplication.class, args);
    }
}
