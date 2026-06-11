package com.fintech.payments.legacy.client;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

import java.util.HashMap;
import java.util.Map;

/**
 * LEGACY — Blocking HTTP client to the card acquirer.
 *
 * PROBLEM: RestTemplate — in maintenance mode since Spring 5; blocking I/O.
 * PROBLEM: hand-rolled retry loop with Thread.sleep — ties up a servlet
 *          thread for the full backoff duration; no jitter; retries on
 *          non-retryable 4xx errors too.
 * PROBLEM: no circuit breaker — when the acquirer is down every request
 *          burns (maxAttempts × timeout) before failing.
 *
 * MIGRATE TO: WebClient + @Retry/@CircuitBreaker (Resilience4j) — see
 * modern/src/main/java/com/fintech/payments/modern/client/AcquirerClient.java
 */
@Component
public class AcquirerClient {

    private static final Logger log = LoggerFactory.getLogger(AcquirerClient.class);

    private final RestTemplate restTemplate = new RestTemplate();

    @Value("${acquirer.url:http://localhost:9999/acquirer}")
    private String acquirerUrl;

    @Value("${acquirer.max-attempts:3}")
    private int maxAttempts;

    @SuppressWarnings("unchecked")
    public Map<String, Object> authorise(String cardNumber, double amount, String currency) {
        Map<String, Object> body = new HashMap<>();
        // PROBLEM: full PAN sent and logged downstream — PCI DSS violation;
        // modern service tokenises the PAN before any outbound call.
        body.put("pan", cardNumber);
        body.put("amount", amount);
        body.put("currency", currency);

        int attempt = 0;
        while (true) {
            attempt++;
            try {
                return restTemplate.postForObject(acquirerUrl + "/authorise", body, Map.class);
            } catch (Exception e) {
                log.warn("Acquirer call failed attempt={}/{}: {}", attempt, maxAttempts, e.getMessage());
                if (attempt >= maxAttempts) {
                    throw new IllegalStateException("Acquirer unavailable after " + attempt + " attempts", e);
                }
                try {
                    // PROBLEM: blocking sleep on the request thread, fixed backoff, no jitter
                    Thread.sleep(1000L * attempt);
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                    throw new IllegalStateException("Interrupted during acquirer retry", ie);
                }
            }
        }
    }
}
