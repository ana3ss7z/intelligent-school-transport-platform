package ma.transport.ms8gateway.exception;

/**
 * Exception levée quand le JWT est absent ou invalide dans la Gateway.
 */
public class GatewayAuthException extends RuntimeException {

    private final int statusCode;

    public GatewayAuthException(String message, int statusCode) {
        super(message);
        this.statusCode = statusCode;
    }

    public int getStatusCode() {
        return statusCode;
    }
}