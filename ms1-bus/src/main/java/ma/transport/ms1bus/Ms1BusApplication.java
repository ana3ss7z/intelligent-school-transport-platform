package ma.transport.ms1bus;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication(
    scanBasePackages = {
        "ma.transport.ms1bus",
        "ma.transport.mscommon"
    }
)
public class Ms1BusApplication {

	public static void main(String[] args) {
		SpringApplication.run(Ms1BusApplication.class, args);
	}

}
