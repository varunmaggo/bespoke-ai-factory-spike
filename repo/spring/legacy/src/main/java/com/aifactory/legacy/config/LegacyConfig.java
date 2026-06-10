package com.aifactory.legacy.config;

import org.springframework.boot.web.client.RestTemplateBuilder;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.client.RestTemplate;

import java.time.Duration;

/**
 * LEGACY configuration.
 *
 * Migration targets:
 *   1. Replace RestTemplate bean with WebClient.Builder (reactive, non-blocking)
 *   2. Remove this class — Spring AI 1.x auto-configures ChatModel via starter
 *   3. Add Resilience4j CircuitBreakerConfig beans
 *   4. Add OpenTelemetry SDK configuration
 */
@Configuration
public class LegacyConfig {

    /**
     * MIGRATE TO: WebClient.Builder with reactor-netty
     *
     * Before (this):
     *   RestTemplate restTemplate = restTemplateBuilder.build();
     *
     * After:
     *   WebClient webClient = WebClient.builder()
     *       .baseUrl(ragServiceUrl)
     *       .defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
     *       .build();
     */
    @Bean
    public RestTemplate restTemplate(RestTemplateBuilder builder) {
        return builder
                .connectTimeout(Duration.ofSeconds(5))
                .readTimeout(Duration.ofSeconds(30))
                .build();
    }
}
