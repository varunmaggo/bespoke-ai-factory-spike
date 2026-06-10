# Transformation Definition: java-spring-to-spring-ai

Modernise a Spring Boot 2.7.x service that uses deprecated Spring AI 0.8.x patterns into
a Spring Boot 3.2.x service using Spring AI 1.x (Anthropic), Resilience4j, and OpenTelemetry.

This definition was authored against the concrete legacy service in
`spring/legacy/` and produces the output in `spring/modern/`.

Run with:
```bash
atx custom def exec \
    --definition java-spring-to-spring-ai \
    --source-path spring/legacy \
    --output-path spring/modern \
    --trust-all-tools
```

---

## Step 1 — Update pom.xml

Update the Maven parent and Spring AI dependency.

Before:
```xml
<parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>2.7.18</version>
</parent>

<dependency>
    <groupId>org.springframework.ai</groupId>
    <artifactId>spring-ai-openai-spring-boot-starter</artifactId>
    <version>0.8.1</version>
</dependency>
```

After:
```xml
<parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>3.2.5</version>
</parent>

<dependency>
    <groupId>org.springframework.ai</groupId>
    <artifactId>spring-ai-anthropic-spring-boot-starter</artifactId>
    <version>${spring-ai.version}</version>
</dependency>
```

Also add the following new dependencies that were absent in the legacy service:
- `spring-boot-starter-webflux` (for WebClient)
- `resilience4j-spring-boot3` version 2.2.0
- `spring-boot-starter-aop` (required for Resilience4j annotations)
- `spring-boot-starter-actuator`
- `micrometer-registry-prometheus`
- `micrometer-tracing-bridge-otel`
- `opentelemetry-exporter-otlp` version 1.37.0

---

## Step 2 — Replace ChatClient with ChatModel

### Import change
Before:
```java
import org.springframework.ai.chat.ChatClient;
```

After:
```java
import org.springframework.ai.anthropic.AnthropicChatModel;
```

### Field declaration
Before:
```java
private final ChatClient chatClient;
```

After:
```java
private final AnthropicChatModel chatModel;
```

### Constructor injection
Before:
```java
public LegacyQueryService(ChatClient chatClient, SolrSearchClient solrSearchClient) {
    this.chatClient = chatClient;
    this.solrSearchClient = solrSearchClient;
}
```

After:
```java
public AIFactoryService(AnthropicChatModel chatModel,
        @Qualifier("ragWebClient") WebClient ragWebClient,
        @Qualifier("evalWebClient") WebClient evalWebClient) {
    this.chatModel = chatModel;
    this.ragWebClient = ragWebClient;
    this.evalWebClient = evalWebClient;
}
```

---

## Step 3 — Replace ChatClient.call() with ChatModel.call()

### Method call
Before:
```java
ChatResponse chatResponse = chatClient.call(new Prompt(List.of(systemMessage, userMessage)));
```

After:
```java
ChatResponse chatResponse = chatModel.call(new Prompt(List.of(systemMessage, userMessage)));
```

### Response extraction — .getContent() → .getText()
Before:
```java
String answer = chatResponse.getResult().getOutput().getContent();
```

After:
```java
String answer = chatResponse.getResult().getOutput().getText();
```

### SystemPromptTemplate → SystemMessage
Before:
```java
SystemPromptTemplate systemPromptTemplate = new SystemPromptTemplate(systemText);
var systemMessage = systemPromptTemplate.createMessage(Map.of());
```

After:
```java
var systemMessage = new SystemMessage(systemText);
```

---

## Step 4 — Replace RestTemplate + SolrSearchClient with WebClient

Remove `SolrSearchClient` and `LegacyConfig.restTemplate()` bean entirely.

Before (two synchronous blocking calls — O(N) round trips):
```java
// spring/legacy/src/main/java/com/aifactory/legacy/service/LegacyQueryService.java
List<String> documentIds = solrSearchClient.keywordSearch(request.getQuery(), request.getDepartment());
List<String> contexts = documentIds.stream()
        .map(solrSearchClient::fetchDocumentContent)
        .filter(content -> !content.isBlank())
        .limit(5)
        .collect(Collectors.toList());
```

After (single non-blocking RAG service call with chunks + scores):
```java
// spring/modern/src/main/java/com/aifactory/modern/service/AIFactoryService.java
Map<String, Object> body = ragWebClient.post()
        .uri("/query")
        .bodyValue(Map.of(
                "query", request.getQuery(),
                "filters", Map.of("department", department),
                "top_k", 10
        ))
        .retrieve()
        .bodyToMono(Map.class)
        .timeout(Duration.ofSeconds(30))
        .block();
```

Add two `WebClient` beans in `AIFactoryConfig` (replacing `LegacyConfig`):
```java
@Bean("ragWebClient")
public WebClient ragWebClient(WebClient.Builder builder) {
    return builder.baseUrl(ragServiceUrl).build();
}

@Bean("evalWebClient")
public WebClient evalWebClient(WebClient.Builder builder) {
    return builder.baseUrl(evalServiceUrl).build();
}
```

---

## Step 5 — Replace javax.validation with jakarta.validation

In all model classes (`QueryRequest`, etc.) and controllers:

Before:
```java
// spring/legacy/src/main/java/com/aifactory/legacy/model/QueryRequest.java
import javax.validation.constraints.NotBlank;
import javax.validation.constraints.Size;

// spring/legacy/src/main/java/com/aifactory/legacy/controller/LegacyQueryController.java
import javax.validation.Valid;
```

After:
```java
// spring/modern/src/main/java/com/aifactory/modern/model/QueryRequest.java
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

// spring/modern/src/main/java/com/aifactory/modern/controller/AIFactoryController.java
import jakarta.validation.Valid;
```

---

## Step 6 — Add Resilience4j circuit breaker and retry

Before (no resilience — any failure throws directly to caller):
```java
// spring/legacy/src/main/java/com/aifactory/legacy/service/LegacyQueryService.java
try {
    chatResponse = chatClient.call(new Prompt(List.of(systemMessage, userMessage)));
} catch (Exception e) {
    log.error("LLM call failed for requestId={}: {}", requestId, e.getMessage());
    return new QueryResponse("Unable to process your query. Please try again.", documentIds, requestId);
}
```

After:
```java
// spring/modern/src/main/java/com/aifactory/modern/service/AIFactoryService.java
@CircuitBreaker(name = "ai-service", fallbackMethod = "fallbackAnswer")
@Retry(name = "ai-service")
public String callLlmWithResilience(Prompt prompt, String requestId) {
    ChatResponse response = chatModel.call(prompt);
    return response.getResult().getOutput().getText();
}

public String fallbackAnswer(Prompt prompt, String requestId, Throwable t) {
    log.error("LLM circuit breaker open requestId={}: {}", requestId, t.getMessage());
    return "The AI service is temporarily unavailable. Please try again in a few moments.";
}
```

Add to `application.yml`:
```yaml
resilience4j:
  circuitbreaker:
    instances:
      ai-service:
        sliding-window-size: 10
        failure-rate-threshold: 50
        wait-duration-in-open-state: 10s
  retry:
    instances:
      ai-service:
        max-attempts: 3
        wait-duration: 1s
```

---

## Step 7 — Add OpenTelemetry tracing

Before (no tracing — impossible to correlate slow requests):
```java
// spring/legacy/src/main/java/com/aifactory/legacy/service/LegacyQueryService.java
public QueryResponse query(QueryRequest request) {
```

After:
```java
// spring/modern/src/main/java/com/aifactory/modern/service/AIFactoryService.java
@Observed(name = "ai.factory.query", contextualName = "query")
public QueryResponse query(QueryRequest request) {
```

Add to `application.yml`:
```yaml
management:
  tracing:
    sampling:
      probability: 1.0

otel:
  exporter:
    otlp:
      endpoint: ${OTEL_EXPORTER_OTLP_ENDPOINT:http://localhost:4317}
```

---

## Step 8 — Add LLM evaluation gate

After generating the answer, call the eval service before returning to caller.
This was completely absent in the legacy service.

```java
// spring/modern/src/main/java/com/aifactory/modern/service/AIFactoryService.java
double evalScore = evalGateEnabled
        ? callEvalService(request.getQuery(), answer, contextBlock, requestId)
        : 1.0;
boolean evalPassed = evalScore >= evalMinScore;

if (!evalPassed) {
    answer = "I was unable to generate a sufficiently reliable answer. "
           + "Please rephrase your question or contact support.";
}
```

Update response model (`QueryResponse`) to include fields absent in the legacy version:
- `evalScore` (double, 0.0–1.0)
- `evalPassed` (boolean)
- `hops` (int — number of RAG retrieval iterations)
- `transformMetadata` (Map<String, Object> — AWS Transform output metadata)
- `timestamp` as `Instant` (UTC) instead of `LocalDateTime` (timezone-unaware)
- `sources` as `List<SourceDocument>` (id + score + excerpt) instead of bare `List<String>`

---

## Step 9 — Update application.yml

Before:
```yaml
spring:
  ai:
    openai:
      api-key: ${OPENAI_API_KEY}
      model: gpt-3.5-turbo

legacy:
  search:
    url: ${SOLR_URL:http://localhost:8983/solr/enterprise-docs/select}
    max-results: 10
```

After:
```yaml
spring:
  ai:
    anthropic:
      api-key: ${ANTHROPIC_API_KEY}
      chat:
        options:
          model: claude-3-5-sonnet-20241022
          max-tokens: 2048
  threads:
    virtual:
      enabled: true   # Java 21 virtual threads

ai-factory:
  rag:
    url: ${RAG_SERVICE_URL:http://localhost:8001}
    timeout-seconds: 30
  eval:
    url: ${EVAL_SERVICE_URL:http://localhost:8002}
    timeout-seconds: 15
  eval-gate:
    min-score: 0.75
    enabled: ${EVAL_GATE_ENABLED:true}
```

---

## Validation

After running this transformation:

```bash
# Compile modern service
mvn -f spring/modern/pom.xml compile

# Run unit tests
mvn -f spring/modern/pom.xml test

# Start full stack and smoke test
docker compose up -d
curl -s -X POST http://localhost:8080/api/v1/query \
     -H 'Content-Type: application/json' \
     -d '{"query":"What is our refund policy?","userId":"u1","department":"sales"}' \
     | jq '{evalScore, evalPassed, hops}'
```

Expected smoke test response fields: `evalScore`, `evalPassed`, `hops`, `transformMetadata` — all absent in the legacy service, all present after migration.
