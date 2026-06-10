package com.aifactory.modern.service;

import com.aifactory.modern.model.QueryRequest;
import com.aifactory.modern.model.QueryResponse;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.ai.anthropic.AnthropicChatModel;
import org.springframework.ai.chat.model.ChatResponse;
import org.springframework.ai.chat.model.Generation;
import org.springframework.ai.chat.messages.AssistantMessage;
import org.springframework.ai.chat.prompt.Prompt;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;
import reactor.core.publisher.Mono;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

/**
 * Unit tests for AIFactoryService (modern Spring Boot 3.x).
 *
 * Mocks: AnthropicChatModel, ragWebClient, evalWebClient.
 * No Spring context — fast, isolated logic tests.
 */
@ExtendWith(MockitoExtension.class)
class AIFactoryServiceTest {

    @Mock private AnthropicChatModel chatModel;
    @Mock private WebClient ragWebClient;
    @Mock private WebClient evalWebClient;

    // WebClient fluent chain mocks
    @Mock private WebClient.RequestBodyUriSpec ragRequestBodyUriSpec;
    @Mock private WebClient.RequestBodySpec    ragRequestBodySpec;
    @Mock private WebClient.ResponseSpec       ragResponseSpec;

    @Mock private WebClient.RequestBodyUriSpec evalRequestBodyUriSpec;
    @Mock private WebClient.RequestBodySpec    evalRequestBodySpec;
    @Mock private WebClient.ResponseSpec       evalResponseSpec;

    @InjectMocks
    private AIFactoryService service;

    private QueryRequest sampleRequest;

    @BeforeEach
    void setUp() {
        ReflectionTestUtils.setField(service, "evalMinScore", 0.75);
        ReflectionTestUtils.setField(service, "evalGateEnabled", true);

        sampleRequest = new QueryRequest("What is our refund policy?", "user-1", "sales");
    }

    // ── helper stubs ─────────────────────────────────────────────────────────

    private void stubRagService(Map<String, Object> ragBody) {
        when(ragWebClient.post()).thenReturn(ragRequestBodyUriSpec);
        when(ragRequestBodyUriSpec.uri(anyString())).thenReturn(ragRequestBodySpec);
        when(ragRequestBodySpec.bodyValue(any())).thenReturn(ragRequestBodySpec);
        when(ragRequestBodySpec.retrieve()).thenReturn(ragResponseSpec);
        when(ragResponseSpec.bodyToMono(Map.class)).thenReturn(Mono.just(ragBody));
    }

    private void stubEvalService(double score) {
        when(evalWebClient.post()).thenReturn(evalRequestBodyUriSpec);
        when(evalRequestBodyUriSpec.uri(anyString())).thenReturn(evalRequestBodySpec);
        when(evalRequestBodySpec.bodyValue(any())).thenReturn(evalRequestBodySpec);
        when(evalRequestBodySpec.retrieve()).thenReturn(evalResponseSpec);
        when(evalResponseSpec.bodyToMono(Map.class)).thenReturn(Mono.just(Map.of("weighted_score", score)));
    }

    private void stubChatModel(String answer) {
        var assistantMessage = new AssistantMessage(answer);
        var generation       = new Generation(assistantMessage);
        var chatResponse     = new ChatResponse(List.of(generation));
        when(chatModel.call(any(Prompt.class))).thenReturn(chatResponse);
    }

    // ── happy path ───────────────────────────────────────────────────────────

    @Test
    void query_happyPath_returnAnswerWithMetadata() {
        stubRagService(Map.of(
                "answer", "RAG answer",
                "sources", List.of(Map.of("document_id", "doc-1", "score", 0.9, "content", "Refunds are 30 days")),
                "transform_metadata", Map.of("definition", "enterprise-context-normaliser"),
                "hops", 1
        ));
        stubChatModel("Our refund policy allows returns within 30 days.");
        stubEvalService(0.88);

        QueryResponse response = service.query(sampleRequest);

        assertThat(response.getAnswer()).contains("30 days");
        assertThat(response.isEvalPassed()).isTrue();
        assertThat(response.getEvalScore()).isEqualTo(0.88);
        assertThat(response.getHops()).isEqualTo(1);
        assertThat(response.getSources()).hasSize(1);
        assertThat(response.getSources().get(0).id()).isEqualTo("doc-1");
        assertThat(response.getTransformMetadata()).containsKey("definition");
    }

    @Test
    void query_evalGateFails_returnsFallbackMessage() {
        stubRagService(Map.of("answer", "", "sources", List.of(), "transform_metadata", Map.of(), "hops", 1));
        stubChatModel("This answer might be hallucinated.");
        stubEvalService(0.40);  // below threshold of 0.75

        QueryResponse response = service.query(sampleRequest);

        assertThat(response.isEvalPassed()).isFalse();
        assertThat(response.getEvalScore()).isEqualTo(0.40);
        assertThat(response.getAnswer()).contains("unable to generate");
    }

    @Test
    void query_evalGateDisabled_returnsAnswerRegardlessOfScore() {
        ReflectionTestUtils.setField(service, "evalGateEnabled", false);

        stubRagService(Map.of("answer", "", "sources", List.of(), "transform_metadata", Map.of(), "hops", 1));
        stubChatModel("Potentially unreliable answer.");

        QueryResponse response = service.query(sampleRequest);

        assertThat(response.isEvalPassed()).isTrue();  // score defaults to 1.0 when gate disabled
        assertThat(response.getEvalScore()).isEqualTo(1.0);
        assertThat(response.getAnswer()).contains("Potentially unreliable");
    }

    // ── circuit breaker / resilience ─────────────────────────────────────────

    @Test
    void callLlmWithResilience_fallback_returnsGracefulMessage() {
        // Simulate fallback being triggered directly (circuit open or retries exhausted)
        String fallback = service.fallbackAnswer(
                new Prompt("test"),
                "req-1",
                new RuntimeException("LLM timeout")
        );

        assertThat(fallback).contains("temporarily unavailable");
    }

    @Test
    void callRagService_ragDown_returnsFallbackEmptyContext() {
        when(ragWebClient.post()).thenReturn(ragRequestBodyUriSpec);
        when(ragRequestBodyUriSpec.uri(anyString())).thenReturn(ragRequestBodySpec);
        when(ragRequestBodySpec.bodyValue(any())).thenReturn(ragRequestBodySpec);
        when(ragRequestBodySpec.retrieve()).thenReturn(ragResponseSpec);
        when(ragResponseSpec.bodyToMono(Map.class))
                .thenReturn(Mono.error(new WebClientResponseException(503, "Service Unavailable", null, null, null)));

        var result = service.fallbackRagResult(sampleRequest, "req-1", new RuntimeException("503"));

        assertThat(result.sources()).isEmpty();
        assertThat(result.contextText()).isEqualTo("No context available.");
        assertThat(result.hops()).isEqualTo(0);
    }

    // ── eval service ─────────────────────────────────────────────────────────

    @Test
    void callEvalService_evalDown_defaultsTo0_5() {
        when(evalWebClient.post()).thenReturn(evalRequestBodyUriSpec);
        when(evalRequestBodyUriSpec.uri(anyString())).thenReturn(evalRequestBodySpec);
        when(evalRequestBodySpec.bodyValue(any())).thenReturn(evalRequestBodySpec);
        when(evalRequestBodySpec.retrieve()).thenReturn(evalResponseSpec);
        when(evalResponseSpec.bodyToMono(Map.class))
                .thenReturn(Mono.error(new WebClientResponseException(500, "Internal Server Error", null, null, null)));

        double score = service.callEvalService("q", "a", "ctx", "req-1");

        assertThat(score).isEqualTo(0.5);
    }

    @Test
    void callEvalService_perfectScore_returns1_0() {
        stubEvalService(1.0);

        double score = service.callEvalService("q", "a", "ctx", "req-1");

        assertThat(score).isEqualTo(1.0);
    }

    // ── requestId uniqueness ─────────────────────────────────────────────────

    @Test
    void query_twoCallsProduceDifferentRequestIds() {
        stubRagService(Map.of("answer", "", "sources", List.of(), "transform_metadata", Map.of(), "hops", 1));
        stubChatModel("Answer 1.");
        stubEvalService(0.9);

        QueryResponse r1 = service.query(sampleRequest);

        stubChatModel("Answer 2.");
        stubEvalService(0.9);

        QueryResponse r2 = service.query(sampleRequest);

        assertThat(r1.getRequestId()).isNotEqualTo(r2.getRequestId());
    }
}
