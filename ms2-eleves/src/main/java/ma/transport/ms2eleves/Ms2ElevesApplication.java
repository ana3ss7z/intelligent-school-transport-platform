package ma.transport.ms2eleves;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication(
    scanBasePackages = {
        "ma.transport.ms2eleves",
        "ma.transport.mscommon"
    }
)
public class Ms2ElevesApplication {

	public static void main(String[] args) {
		SpringApplication.run(Ms2ElevesApplication.class, args);
	}

}
