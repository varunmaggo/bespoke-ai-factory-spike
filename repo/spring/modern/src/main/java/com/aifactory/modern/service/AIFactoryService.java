package com.aifactory.modern.service;

import com.aifactory.modern.model.QueryRequest;
import com.aifactory.modern.model.QueryResponse;
import com.aifactory.modern.model.QueryResponse.SourceDocument;
import io.github.resilience4j.circuitbreaker.annotation.CircuitBreaker;
import io.github.resilience4j.retry.annotation.Retry;
import io.micrometer.observation.annotation.Observed;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.ai.anthropic.AnthropicChatModel;
import org.springframework.ai.chat.messages.SystemMessage;
import org.springframework.ai.chat.messages.UserMessage;
import org.springframework.ai.chat.model.ChatResponse;
import org.springframework.ai.chat.prompt.Prompt;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;

import java.time.Duration;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * MODERN — AIFactoryService.
 *
 * What AWS Transform Custom migrated from LegacyQueryService:
 *
 *   1. ChatClient → AnthropicChatModel (Spring AI 1.x ChatModel API)
 *   2. chatClient.call(Prompt) → chatModel.call(Prompt)
 *   3. getResult().getOutput().getContent() → getResult().getOutput().getText()
 *   4. RestTemplate + SolrSearchClient → ragWebClient (vector + graph hybrid search)
 *   5. No retry/circuit breaker → @CircuitBreaker + @Retry on LLM call
 *   6. No OTel → @Observed on public method (auto-creates spans)
 *   7. No eval → evalWebClient call gates response before returning to caller
 *   8. Thread-blocking → Duration.ofSeconds timeouts on all WebClient calls
 */
@Service
public class AIFactoryService {

    private static final Logger log = LoggerFactory.getLogger(AIFactoryService.class);

    // MIGRATED: ChatClient → ChatModel (Spring AI 1.x)
    private final AnthropicChatModel chatModel;

    private final WebClient ragWebClient;
    private final WebClient evalWebClient;

    @Value("${ai-factory.eval-gate.min-score:0.75}")
    private double evalMinScore;

    @Value("${ai-factory.eval-gate.enabled:true}")
    private boolean evalGateEnabled;

    private static final String SYSTEM_PROMPT_TEMPLATE = """
            You are an enterprise AI assistant. Answer the user's question using ONLY
            the context below. If the context does not contain enough information, say
            "I don't have enough information to answer that." Do not hallucinate.

            Context:
            {context}
            """;

    public AIFactoryService(
            AnthropicChatModel chatModel,
            @Qualifier("ragWebClient") WebClient ragWebClient,
            @Qualifier("evalWebClient") WebClient evalWebClient) {
        this.chatModel     = chatModel;
        this.ragWebClient  = ragWebClient;
        this.evalWebClient = evalWebClient;
    }

    /**
     * ADDED: @Observed — Micrometer auto-creates an OTel span for this method.
     * The span includes traceId propagated from the incoming HTTP request.
     * In legacy there was no tracing at all.
     */
    @Observed(name = "ai.factory.query", contextualName = "query")
    public QueryResponse query(QueryRequest request) {
        String requestId = UUID.randomUUID().toString();
        log.info("Processing query requestId={} userId={}", requestId, request.getUserId());

        // Step 1: RAG retrieval — hybrid vector + graph search via RAG service
        // MIGRATED from: SolrSearchClient.keywordSearch() + fetchDocumentContent()
        var ragResult = callRagService(request, requestId);

        List<SourceDocument> sources      = ragResult.sources();
        String contextBlock               = ragResult.contextText();
        Map<String, Object> transformMeta = ragResult.transformMetadata();
        int hops                          = ragResult.hops();

        // Step 2: Build grounded prompt — context comes from RAG, not hard-coded text
        String systemText = SYSTEM_PROMPT_TEMPLATE.replace("{context}", contextBlock);

        // MIGRATED: new Prompt(List.of(systemMessage, userMessage))
        // Old pattern was SystemPromptTemplate(systemText).createMessage(Map.of())
        var prompt = new Prompt(List.of(
                new SystemMessage(systemText),
                new UserMessage(request.getQuery())
        ));

        // Step 3: Call LLM with circuit breaker + retry
        // MIGRATED: chatClient.call() → chatModel.call()
        String answer = callLlmWithResilience(prompt, requestId);

        // Step 4: Evaluate response — absent in legacy
        double evalScore = evalGateEnabled
                ? callEvalService(request.getQuery(), answer, contextBlock, requestId)
                : 1.0;
        boolean evalPassed = evalScore >= evalMinScore;

        if (!evalPassed) {
            log.warn("Eval gate failed requestId={} score={}", requestId, evalScore);
            answer = "I was unable to generate a sufficiently reliable answer. "
                   + "Please rephrase your question or contact support.";
        }

        log.info("Query complete requestId={} hops={} evalScore={} evalPassed={}",
                requestId, hops, evalScore, evalPassed);

        return new QueryResponse(requestId, answer, sources, evalScore, evalPassed, hops, transformMeta);
    }

    // ── LLM call — circuit breaker + retry ──────────────────────────────────

    /**
     * ADDED: @CircuitBreaker + @Retry — absent in legacy.
     * If the LLM call fails 50% of the time over a 10-call window, the circuit
     * opens and fallbackAnswer() is returned immediately without waiting.
     *
     * MIGRATED: chatModel.call() and getResult().getOutput().getText()
     * Old: chatClient.call() and getResult().getOutput().getContent()
     */
    @CircuitBreaker(name = "ai-service", fallbackMethod = "fallbackAnswer")
    @Retry(name = "ai-service")
    public String callLlmWithResilience(Prompt prompt, String requestId) {
        log.debug("Calling LLM requestId={}", requestId);
        // MIGRATED: chatModel.call() — Spring AI 1.x
        ChatResponse response = chatModel.call(prompt);
        // MIGRATED: .getText() instead of .getContent()
        return response.getResult().getOutput().getText();
    }

    @SuppressWarnings("unused")
    public String fallbackAnswer(Prompt prompt, String requestId, Throwable t) {
        log.error("LLM circuit breaker open or all retries exhausted requestId={}: {}", requestId, t.getMessage());
        return "The AI service is temporarily unavailable. Please try again in a few moments.";
    }

    // ── RAG service call ─────────────────────────────────────────────────────

    @CircuitBreaker(name = "rag-service", fallbackMethod = "fallbackRagResult")
    @Retry(name = "rag-service")
    RagResult callRagService(QueryRequest request, String requestId) {
        log.debug("Calling RAG service requestId={}", requestId);

        var ragRequest = Map.of(
                "query", request.getQuery(),
                "filters", Map.of("department", request.getDepartment() != null ? request.getDepartment() : ""),
                "top_k", 10
        );

        @SuppressWarnings("unchecked")
        Map<String, Object> body = ragWebClient.post()
                .uri("/query")
                .bodyValue(ragRequest)
                .retrieve()
                .bodyToMono(Map.class)
                .timeout(Duration.ofSeconds(30))
                .block();

        if (body == null) return fallbackRagResult(request, requestId, new RuntimeException("null body"));

        String answer        = (String) body.getOrDefault("answer", "");
        int hops             = ((Number) body.getOrDefault("hops", 1)).intValue();
        @SuppressWarnings("unchecked")
        var rawSources       = (List<Map<String, Object>>) body.getOrDefault("sources", Collections.emptyList());
        @SuppressWarnings("unchecked")
        var transformMeta    = (Map<String, Object>) body.getOrDefault("transform_metadata", Collections.emptyMap());

        List<SourceDocument> sources = rawSources.stream()
                .map(s -> new SourceDocument(
                        (String) s.getOrDefault("document_id", ""),
                        ((Number) s.getOrDefault("score", 0.0)).doubleValue(),
                        truncate((String) s.getOrDefault("content", ""), 200)
                ))
                .toList();

        String contextText = rawSources.stream()
                .map(s -> (String) s.getOrDefault("content", ""))
                .filter(c -> !c.isBlank())
                .limit(8)
                .reduce("", (a, b) -> a + "\n\n---\n\n" + b);

        return new RagResult(sources, contextText, transformMeta, hops);
    }

    @SuppressWarnings("unused")
    RagResult fallbackRagResult(QueryRequest request, String requestId, Throwable t) {
        log.warn("RAG service unavailable requestId={}: {}", requestId, t.getMessage());
        return new RagResult(Collections.emptyList(), "No context available.", Collections.emptyMap(), 0);
    }

    // ── Eval service call ────────────────────────────────────────────────────

    double callEvalService(String query, String answer, String context, String requestId) {
        try {
            var evalRequest = Map.of(
                    "query", query,
                    "answer", answer,
                    "context", context
            );

            @SuppressWarnings("unchecked")
            Map<String, Object> body = evalWebClient.post()
                    .uri("/evaluate")
                    .bodyValue(evalRequest)
                    .retrieve()
                    .bodyToMono(Map.class)
                    .timeout(Duration.ofSeconds(15))
                    .block();

            if (body == null) return 0.5;
            return ((Number) body.getOrDefault("weighted_score", 0.5)).doubleValue();

        } catch (WebClientResponseException | IllegalStateException e) {
            log.warn("Eval service call failed requestId={}: {} — defaulting to 0.5", requestId, e.getMessage());
            return 0.5;  // don't block the request if eval is down; log and continue
        }
    }

    // ── Helpers ──────────────────────────────────────────────────────────────

    private String truncate(String text, int maxChars) {
        return text.length() <= maxChars ? text : text.substring(0, maxChars) + "…";
    }

    record RagResult(
            List<SourceDocument> sources,
            String contextText,
            Map<String, Object> transformMetadata,
            int hops) {}
}
