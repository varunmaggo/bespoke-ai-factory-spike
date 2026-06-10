package com.aifactory.legacy.service;

import com.aifactory.legacy.client.SolrSearchClient;
import com.aifactory.legacy.model.QueryRequest;
import com.aifactory.legacy.model.QueryResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.ai.chat.ChatClient;
import org.springframework.ai.chat.ChatResponse;
import org.springframework.ai.chat.prompt.Prompt;
import org.springframework.ai.chat.prompt.SystemPromptTemplate;
import org.springframework.ai.chat.messages.UserMessage;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.stream.Collectors;

/**
 * LEGACY — Synchronous AI query service using Spring AI 0.8.x patterns.
 *
 * Problems this class demonstrates (all fixed in the modern service):
 *
 *   1. ChatClient (old API) — replaced by ChatModel in Spring AI 1.x
 *   2. chatClient.call(Prompt) returns ChatResponse with deprecated shape
 *   3. No RAG retrieval — asks the LLM directly, no grounding in company docs
 *   4. Solr keyword search only — no vector similarity, no graph enrichment
 *   5. Two-trip document fetch — search returns IDs, must fetch content separately
 *   6. No circuit breaker — if OpenAI is down, all requests fail immediately
 *   7. No retry — a transient 429 rate-limit kills the request
 *   8. No OTel tracing — can't correlate a slow request through the call chain
 *   9. No eval — response goes straight to caller; hallucinations are invisible
 *  10. Thread-blocking throughout — does not scale under load
 *
 * AWS Transform Custom migration (transformation_definition.md: java-spring-to-spring-ai):
 *   - ChatClient → ChatModel
 *   - chatClient.call(new Prompt(...)) → chatModel.call(new Prompt(...))
 *   - getResult().getOutput().getContent() → getResult().getOutput().getText()
 *   - Add @CircuitBreaker(name = "ai-service", fallbackMethod = "fallbackAnswer")
 *   - Add @Retry(name = "ai-service")
 *   - Add OTel @WithSpan on public methods
 *   - Wire in ragWebClient.post("/retrieve") before prompt construction
 *   - Wire in evalWebClient.post("/evaluate") after generation
 */
@Service
public class LegacyQueryService {

    private static final Logger log = LoggerFactory.getLogger(LegacyQueryService.class);

    // MIGRATE TO: ChatModel (Spring AI 1.x)
    private final ChatClient chatClient;

    private final SolrSearchClient solrSearchClient;

    @Value("${spring.ai.openai.model:gpt-3.5-turbo}")
    private String model;

    // System prompt — in modern service this incorporates RAG context chunks
    private static final String SYSTEM_PROMPT = """
            You are an enterprise AI assistant. Answer the user's question clearly and concisely.
            If you don't know the answer, say so rather than guessing.
            """;

    public LegacyQueryService(ChatClient chatClient, SolrSearchClient solrSearchClient) {
        this.chatClient      = chatClient;
        this.solrSearchClient = solrSearchClient;
    }

    /**
     * MIGRATE TO: Use ChatModel + WebClient RAG retrieval + eval gate.
     *
     * Before (this method):
     *   1. Keyword search → document IDs only
     *   2. Fetch each doc content via a second HTTP call
     *   3. Build a simple concatenated context string
     *   4. Call ChatClient.call() — blocking, old API
     *   5. Return answer with no eval, no hop count, no transform metadata
     *
     * After (modern AIFactoryService):
     *   1. ragWebClient.post("/retrieve") → chunks with scores + graph enrichment
     *   2. atx custom def exec — normalise / redact the chunks
     *   3. Build grounded prompt from transformed chunks
     *   4. chatModel.call() — Spring AI 1.x, jakarta.*, non-blocking via @Async
     *   5. evalWebClient.post("/evaluate") — gate on evalPassed before returning
     */
    public QueryResponse query(QueryRequest request) {
        String requestId = UUID.randomUUID().toString();
        log.info("Processing query requestId={} userId={}", requestId, request.getUserId());

        // Step 1: keyword search — IDs only, no relevance scores
        // PROBLEM: pure keyword match — synonym-blind, no semantic understanding
        List<String> documentIds = solrSearchClient.keywordSearch(
                request.getQuery(),
                request.getDepartment()
        );
        log.debug("Solr returned {} document IDs for requestId={}", documentIds.size(), requestId);

        // Step 2: fetch content for each ID — N additional HTTP calls
        // PROBLEM: O(N) synchronous round trips; each blocks the thread
        List<String> contexts = documentIds.stream()
                .map(solrSearchClient::fetchDocumentContent)
                .filter(content -> !content.isBlank())
                .limit(5)  // crude truncation — no score-based ranking
                .collect(Collectors.toList());

        // Step 3: concatenate context — no deduplication, no score ranking
        String contextBlock = contexts.isEmpty()
                ? "No relevant documents found."
                : String.join("\n\n---\n\n", contexts);

        // Step 4: build prompt — old Spring AI 0.8.x API
        // MIGRATE TO: new Prompt(List.of(new SystemMessage(...), new UserMessage(...)))
        String systemText = SYSTEM_PROMPT + "\n\nContext from company knowledge base:\n" + contextBlock;

        SystemPromptTemplate systemPromptTemplate = new SystemPromptTemplate(systemText);
        var systemMessage = systemPromptTemplate.createMessage(Map.of());
        var userMessage   = new UserMessage(request.getQuery());

        // PROBLEM: ChatClient.call() — deprecated in Spring AI 1.x, replaced by ChatModel
        // PROBLEM: blocking call — ties up a thread for the full LLM latency (typically 2-10s)
        // PROBLEM: no circuit breaker — if OpenAI is down this throws directly to caller
        ChatResponse chatResponse;
        try {
            chatResponse = chatClient.call(new Prompt(List.of(systemMessage, userMessage)));
        } catch (Exception e) {
            // PROBLEM: catch-all with no structured fallback — caller gets a 500
            log.error("LLM call failed for requestId={}: {}", requestId, e.getMessage());
            return new QueryResponse("Unable to process your query. Please try again.", documentIds, requestId);
        }

        // Step 5: extract answer — old API shape
        // MIGRATE TO: chatResponse.getResult().getOutput().getText()
        String answer = chatResponse.getResult().getOutput().getContent();

        log.info("Query complete requestId={} sources={}", requestId, documentIds.size());

        // PROBLEM: no eval — we return the answer without checking for hallucinations
        // PROBLEM: sourceDocuments are IDs only — caller can't see what was actually used
        // PROBLEM: no evalScore, no hops, no transformMetadata in the response
        return new QueryResponse(answer, documentIds, requestId);
    }
}
