package com.fintech.payments.modern.client;

import io.github.resilience4j.circuitbreaker.annotation.CircuitBreaker;
import io.github.resilience4j.retry.annotation.Retry;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;

import java.math.BigDecimal;
import java.time.Duration;
import java.util.Map;

/**
 * MODERN — Non-blocking acquirer client.
 *
 * Replaces the legacy RestTemplate + Thread.sleep retry loop with WebClient
 * and Resilience4j: exponential-backoff retry for transient failures and a
 * circuit breaker that fails fast when the acquirer is down, instead of
 * burning (maxAttempts × timeout) per request.
 */
@Component
public class AcquirerClient {

    private static final Logger log = LoggerFactory.getLogger(AcquirerClient.class);

    private final WebClient acquirerWebClient;
    private final PanTokeniser panTokeniser;

    public AcquirerClient(@Qualifier("acquirerWebClient") WebClient acquirerWebClient,
                          PanTokeniser panTokeniser) {
        this.acquirerWebClient = acquirerWebClient;
        this.panTokeniser = panTokeniser;
    }

    @CircuitBreaker(name = "acquirer", fallbackMethod = "acquirerDown")
    @Retry(name = "acquirer")
    @SuppressWarnings("unchecked")
    public Map<String, Object> authorise(String cardNumber, BigDecimal amount, String currency) {
        // Tokenised PAN only — the raw card number never leaves this service
        String panToken = panTokeniser.tokenise(cardNumber);

        return acquirerWebClient.post()
                .uri("/authorise")
                .bodyValue(Map.of(
                        "panToken", panToken,
                        "amount", amount,
                        "currency", currency
                ))
                .retrieve()
                .bodyToMono(Map.class)
                .timeout(Duration.ofSeconds(10))
                .block();
    }

    public Map<String, Object> acquirerDown(String cardNumber, BigDecimal amount,
                                            String currency, Throwable t) {
        log.error("Acquirer circuit open ({}): {}", t.getClass().getSimpleName(), t.getMessage());
        throw new AcquirerUnavailableException("Acquirer unavailable", t);
    }
}
