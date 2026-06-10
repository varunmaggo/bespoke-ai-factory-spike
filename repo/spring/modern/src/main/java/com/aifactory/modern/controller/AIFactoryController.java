package com.aifactory.modern.controller;

import com.aifactory.modern.model.QueryRequest;
import com.aifactory.modern.model.QueryResponse;
import com.aifactory.modern.service.AIFactoryService;
import jakarta.validation.Valid;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.Map;

/**
 * MODERN REST controller — Spring Boot 3.2.x.
 *
 * AWS Transform Custom changes from LegacyQueryController:
 *   - import javax.validation.Valid → import jakarta.validation.Valid
 *   - @ExceptionHandler moved to @ControllerAdvice (GlobalExceptionHandler)
 *   - /health → delegates to Spring Actuator /actuator/health
 *   - Response includes evalScore, evalPassed, hops, transformMetadata
 */
@RestController
@RequestMapping("/api/v1")
public class AIFactoryController {

    private static final Logger log = LoggerFactory.getLogger(AIFactoryController.class);

    private final AIFactoryService queryService;

    public AIFactoryController(AIFactoryService queryService) {
        this.queryService = queryService;
    }

    /**
     * POST /api/v1/query
     *
     * Example request (same as legacy):
     *   curl -X POST http://localhost:8080/api/v1/query \
     *        -H 'Content-Type: application/json' \
     *        -d '{"query":"What is our refund policy?","userId":"u123","department":"sales"}'
     *
     * Example response (richer than legacy):
     *   {
     *     "requestId": "550e8400-...",
     *     "answer": "Our refund policy allows returns within 30 days...",
     *     "sources": [
     *       {"id": "doc-001", "score": 0.92, "excerpt": "Returns are accepted..."}
     *     ],
     *     "evalScore": 0.87,
     *     "evalPassed": true,
     *     "hops": 1,
     *     "transformMetadata": {"definition": "enterprise-context-normaliser", "items_transformed": 3},
     *     "timestamp": "2024-01-15T10:30:00Z"
     *   }
     *
     * MIGRATED: @Valid uses jakarta.validation (not javax.validation)
     */
    @PostMapping("/query")
    public ResponseEntity<QueryResponse> query(@Valid @RequestBody QueryRequest request) {
        log.info("Received query userId={} department={}", request.getUserId(), request.getDepartment());
        QueryResponse response = queryService.query(request);
        return ResponseEntity.ok(response);
    }

    /**
     * GET /api/v1/health — lightweight liveness check.
     * Full health (RAG, eval, OpenSearch) is via Spring Actuator: GET /actuator/health
     */
    @GetMapping("/health")
    public ResponseEntity<Map<String, String>> health() {
        return ResponseEntity.ok(Map.of(
                "status", "UP",
                "service", "ai-factory-modern",
                "fullHealth", "/actuator/health"
        ));
    }

    /**
     * MIGRATED: @ExceptionHandler kept here for validation; all other exceptions
     * handled by GlobalExceptionHandler (@ControllerAdvice).
     *
     * MIGRATED: javax.validation → jakarta.validation in MethodArgumentNotValidException binding.
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
