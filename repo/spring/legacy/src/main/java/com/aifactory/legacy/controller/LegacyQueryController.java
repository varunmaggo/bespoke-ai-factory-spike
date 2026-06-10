package com.aifactory.legacy.controller;

import com.aifactory.legacy.model.QueryRequest;
import com.aifactory.legacy.model.QueryResponse;
import com.aifactory.legacy.service.LegacyQueryService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.*;

import javax.validation.Valid;
import java.util.HashMap;
import java.util.Map;

/**
 * LEGACY REST controller — Spring Boot 2.7.x patterns.
 *
 * Problems:
 *   1. @Valid uses javax.validation — migrate to jakarta.validation in Spring Boot 3
 *   2. No rate limiting — a single client can exhaust LLM quota
 *   3. No authentication / authorisation — any caller can hit this endpoint
 *   4. @ExceptionHandler in the controller — migrate to @ControllerAdvice
 *   5. No OTel spans — can't trace slow requests through downstream calls
 *   6. Synchronous — every request ties up a thread until the LLM responds
 *
 * Migration: replace with AIFactoryController (Spring Boot 3.2, @Observed, Jakarta,
 * reactive @RestController returning Mono<ResponseEntity<...>>).
 */
@RestController
@RequestMapping("/api/v1")
public class LegacyQueryController {

    private static final Logger log = LoggerFactory.getLogger(LegacyQueryController.class);

    private final LegacyQueryService queryService;

    public LegacyQueryController(LegacyQueryService queryService) {
        this.queryService = queryService;
    }

    /**
     * POST /api/v1/query
     *
     * Example request:
     *   curl -X POST http://localhost:8080/api/v1/query \
     *        -H 'Content-Type: application/json' \
     *        -d '{"query":"What is our refund policy?","userId":"u123","department":"sales"}'
     *
     * Example response:
     *   {
     *     "answer": "Our refund policy allows returns within 30 days...",
     *     "sourceDocuments": ["doc-001", "doc-047"],
     *     "timestamp": "2024-01-15T10:30:00",
     *     "requestId": "550e8400-e29b-41d4-a716-446655440000"
     *   }
     *
     * Note: response does NOT include evalScore, evalPassed, hops, or transformMetadata.
     * Modern AIFactoryController adds all of these.
     *
     * MIGRATE TO:
     *   @PostMapping("/query")
     *   public Mono<ResponseEntity<QueryResponse>> query(
     *       @RequestBody @Valid QueryRequest request,
     *       @RequestHeader("X-User-Id") String userId) { ... }
     */
    @PostMapping("/query")
    public ResponseEntity<QueryResponse> query(@Valid @RequestBody QueryRequest request) {
        log.info("Received query from userId={} department={}", request.getUserId(), request.getDepartment());

        // PROBLEM: blocking — ties up a thread for full LLM latency
        QueryResponse response = queryService.query(request);

        return ResponseEntity.ok(response);
    }

    /**
     * GET /api/v1/health
     *
     * MIGRATE TO: Spring Boot Actuator /actuator/health with custom indicators
     * for RAG service, eval service, and OpenSearch connectivity.
     */
    @GetMapping("/health")
    public ResponseEntity<Map<String, String>> health() {
        return ResponseEntity.ok(Map.of(
                "status", "UP",
                "service", "legacy-ai-factory",
                "note", "No downstream health checks — use actuator in modern service"
        ));
    }

    /**
     * PROBLEM: @ExceptionHandler scoped to this controller only.
     * MIGRATE TO: @ControllerAdvice class (global, reusable).
     */
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<Map<String, String>> handleValidationErrors(MethodArgumentNotValidException ex) {
        Map<String, String> errors = new HashMap<>();
        ex.getBindingResult().getAllErrors().forEach(error -> {
            String field   = ((FieldError) error).getField();
            String message = error.getDefaultMessage();
            errors.put(field, message);
        });
        log.warn("Validation failed: {}", errors);
        return ResponseEntity.badRequest().body(errors);
    }
}
