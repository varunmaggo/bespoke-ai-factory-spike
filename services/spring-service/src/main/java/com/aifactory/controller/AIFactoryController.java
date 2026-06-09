// src/main/java/com/aifactory/controller/AIFactoryController.java
package com.aifactory.controller;

import com.aifactory.dto.AIFactoryRequest;
import com.aifactory.dto.AIFactoryResponse;
import com.aifactory.service.AIFactoryService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/v1")
@Validated
@Tag(name = "AI Factory", description = "Agentic AI Factory endpoints")
public class AIFactoryController {

    private static final Logger log = LoggerFactory.getLogger(AIFactoryController.class);
    private final AIFactoryService service;

    public AIFactoryController(AIFactoryService service) {
        this.service = service;
    }

    @PostMapping("/query")
    @Operation(
        summary = "Submit a query to the AI Factory",
        description = "Triggers agentic RAG retrieval, LLM generation, and eval validation"
    )
    public ResponseEntity<AIFactoryResponse> query(
        @Valid @RequestBody AIFactoryRequest request
    ) {
        log.info("Query received: userId={}, queryLength={}",
            request.getUserId(), request.getQuery().length());

        AIFactoryResponse response = service.query(request);

        if (!response.isEvalPassed()) {
            log.warn("Returning low-quality response: score={}", response.getEvalScore());
            return ResponseEntity.ok()
                .header("X-Eval-Score", String.valueOf(response.getEvalScore()))
                .header("X-Eval-Passed", "false")
                .body(response);
        }

        return ResponseEntity.ok()
            .header("X-Eval-Score", String.valueOf(response.getEvalScore()))
            .header("X-Eval-Passed", "true")
            .body(response);
    }

    @GetMapping("/health")
    public ResponseEntity<Map<String, String>> health() {
        return ResponseEntity.ok(Map.of("status", "UP"));
    }
}
