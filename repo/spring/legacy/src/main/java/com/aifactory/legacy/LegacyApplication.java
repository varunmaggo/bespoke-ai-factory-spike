package com.aifactory.legacy;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * LEGACY — Spring Boot 2.7.x entry point.
 *
 * Problems to fix during migration:
 *   1. Upgrade to Spring Boot 3.2 (Java 21, virtual threads, Spring AI 1.x)
 *   2. Replace ChatClient with ChatModel
 *   3. Replace RestTemplate with WebClient (reactive, non-blocking)
 *   4. Add Resilience4j circuit breakers and retry
 *   5. Add OpenTelemetry tracing + Micrometer metrics
 *   6. Wire up RAG retrieval before generation
 *   7. Add LLM response evaluation before returning to caller
 */
@SpringBootApplication
public class LegacyApplication {

    public static void main(String[] args) {
        SpringApplication.run(LegacyApplication.class, args);
    }
}
