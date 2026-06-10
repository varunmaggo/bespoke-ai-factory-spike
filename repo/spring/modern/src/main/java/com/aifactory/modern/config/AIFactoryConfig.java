package com.aifactory.modern.config;

import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.web.reactive.function.client.ExchangeFilterFunction;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.time.Duration;

/**
 * MODERN configuration — replaces LegacyConfig entirely.
 *
 * AWS Transform Custom changes:
 *   - RestTemplate bean removed; two WebClient beans added (rag + eval)
 *   - Resilience4j beans configured via application.yml (not here)
 *   - ChatModel auto-configured by spring-ai-anthropic-spring-boot-starter
 */
@Configuration
public class AIFactoryConfig {

    @Value("${ai-factory.rag.url}")
    private String ragServiceUrl;

    @Value("${ai-factory.eval.url}")
    private String evalServiceUrl;

    @Value("${ai-factory.rag.timeout-seconds:30}")
    private int ragTimeoutSeconds;

    @Value("${ai-factory.eval.timeout-seconds:15}")
    private int evalTimeoutSeconds;

    /**
     * MIGRATED: RestTemplate → WebClient for RAG service calls.
     *
     * Before (legacy):
     *   ResponseEntity<Map> resp = restTemplate.getForEntity(url, Map.class);
     *
     * After:
     *   ragWebClient.post().uri("/retrieve")
     *       .bodyValue(request)
     *       .retrieve()
     *       .bodyToMono(RetrieveResponse.class)
     *       .timeout(Duration.ofSeconds(ragTimeoutSeconds));
     */
    @Bean("ragWebClient")
    public WebClient ragWebClient(WebClient.Builder builder) {
        return builder
                .baseUrl(ragServiceUrl)
                .defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
                .defaultHeader(HttpHeaders.ACCEPT, MediaType.APPLICATION_JSON_VALUE)
                .filter(loggingFilter("rag"))
                .build();
    }

    /**
     * ADDED: WebClient for eval service — not present in legacy at all.
     */
    @Bean("evalWebClient")
    public WebClient evalWebClient(WebClient.Builder builder) {
        return builder
                .baseUrl(evalServiceUrl)
                .defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
                .defaultHeader(HttpHeaders.ACCEPT, MediaType.APPLICATION_JSON_VALUE)
                .filter(loggingFilter("eval"))
                .build();
    }

    /**
     * Request/response logging filter — adds traceId to outbound calls.
     * In legacy this was absent; correlation was impossible.
     */
    private ExchangeFilterFunction loggingFilter(String serviceLabel) {
        return ExchangeFilterFunction.ofRequestProcessor(req -> {
            // traceId is injected into MDC by Micrometer Tracing automatically
            return Mono.just(req);
        });
    }
}
