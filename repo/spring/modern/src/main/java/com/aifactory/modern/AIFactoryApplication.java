package com.aifactory.modern;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * MODERN — Spring Boot 3.2.x entry point.
 *
 * What AWS Transform Custom changed from legacy:
 *   - Java 21 + virtual threads (spring.threads.virtual.enabled=true)
 *   - Spring Boot 3.2.x parent (Jakarta EE 10, Spring Framework 6.1)
 *   - spring-ai-anthropic-spring-boot-starter 1.0 replaces spring-ai-openai 0.8.1
 *   - ChatModel replaces ChatClient throughout the codebase
 *   - WebClient replaces RestTemplate for all HTTP calls
 *   - javax.validation.* → jakarta.validation.* in all model classes
 *   - Resilience4j circuit breaker + retry on all LLM and service calls
 *   - Micrometer + OpenTelemetry tracing added
 */
@SpringBootApplication
public class AIFactoryApplication {

    public static void main(String[] args) {
        SpringApplication.run(AIFactoryApplication.class, args);
    }
}
