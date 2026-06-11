# Transformation Definition: fintech-java-spring2-to-spring3

Modernise a legacy fintech Spring Boot 2.7.x service into a Spring Boot 3.2.x /
Java 21 service with WebClient, Resilience4j, OpenTelemetry, BigDecimal money
and externalised state.

This definition was authored against the concrete legacy service in
`fintech/payment-gateway/legacy/` and produces the output in
`fintech/payment-gateway/modern/`. It applies estate-wide to:

| Service | Extra steps that apply |
|---|---|
| `fintech/payment-gateway/legacy` | Steps 1–8 (reference pair) |
| `fintech/ledger-service/legacy` | Steps 1–4, plus Step 5 (SQL) and Step 6 (batch) |
| `fintech/fx-settlement/legacy` | Steps 1–4, plus Step 7 (shared mutable cache) |

(`kyc-onboarding` and `fraud-detection` additionally go through
`fintech-rules-to-agentic-rag`; `loan-origination` through
`fintech-soap-to-rest`. Run this definition first for the framework layer.)

Run with:
```bash
atx custom def exec \
    --definition fintech-java-spring2-to-spring3 \
    --source-path fintech/payment-gateway/legacy \
    --output-path fintech/payment-gateway/modern \
    --trust-all-tools
```

---

## Step 1 — Upgrade pom.xml to Boot 3.2 / Java 21

The estate spans a range of legacy Boot versions (2.1.18 → 2.6.15); the agent
reads the actual `<version>` from each module rather than assuming one. The
payment-gateway reference module is on 2.3.12.RELEASE.

Before:
```xml
<parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>2.3.12.RELEASE</version>   <!-- varies per service: 2.1.18 .. 2.6.15 -->
</parent>
<properties>
    <java.version>17</java.version>
</properties>
```

> Security note: any module below Spring Framework 5.2.20 / 5.3.18 is exposed
> to Spring4Shell (CVE-2022-22965); this upgrade closes it. Run
> `fintech-cve-remediation` alongside to clear the standalone-library and
> code-level CVEs the framework bump does not touch.

After:
```xml
<parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>3.2.5</version>
</parent>
<properties>
    <java.version>21</java.version>
    <resilience4j.version>2.2.0</resilience4j.version>
</properties>
```

Add the dependencies absent in every legacy service:
- `spring-boot-starter-webflux` (WebClient)
- `resilience4j-spring-boot3` 2.2.0 + `spring-boot-starter-aop`
- `micrometer-registry-prometheus`
- `micrometer-tracing-bridge-otel` + `opentelemetry-exporter-otlp` 1.37.0

Enable virtual threads in `application.yml`:
```yaml
spring:
  threads:
    virtual:
      enabled: true
```

---

## Step 2 — javax.* → jakarta.*

In all models and controllers:

Before:
```java
// fintech/payment-gateway/legacy/.../model/PaymentRequest.java
import javax.validation.constraints.NotBlank;
import javax.validation.Valid;
```

After:
```java
// fintech/payment-gateway/modern/.../model/PaymentRequest.java
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.Valid;
```

---

## Step 3 — RestTemplate + Thread.sleep retry → WebClient + Resilience4j

Before (hand-rolled retry burns a servlet thread per attempt):
```java
// fintech/payment-gateway/legacy/.../client/AcquirerClient.java
int attempt = 0;
while (true) {
    attempt++;
    try {
        return restTemplate.postForObject(acquirerUrl + "/authorise", body, Map.class);
    } catch (Exception e) {
        if (attempt >= maxAttempts) {
            throw new IllegalStateException("Acquirer unavailable after " + attempt + " attempts", e);
        }
        Thread.sleep(1000L * attempt);
    }
}
```

After (declarative retry + circuit breaker, typed outage signal):
```java
// fintech/payment-gateway/modern/.../client/AcquirerClient.java
@CircuitBreaker(name = "acquirer", fallbackMethod = "acquirerDown")
@Retry(name = "acquirer")
public Map<String, Object> authorise(String cardNumber, BigDecimal amount, String currency) {
    return acquirerWebClient.post()
            .uri("/authorise")
            .bodyValue(Map.of("panToken", panTokeniser.tokenise(cardNumber),
                              "amount", amount, "currency", currency))
            .retrieve()
            .bodyToMono(Map.class)
            .timeout(Duration.ofSeconds(10))
            .block();
}

public Map<String, Object> acquirerDown(String cardNumber, BigDecimal amount,
                                        String currency, Throwable t) {
    throw new AcquirerUnavailableException("Acquirer unavailable", t);
}
```

`application.yml` resilience block:
```yaml
resilience4j:
  circuitbreaker:
    instances:
      acquirer:
        sliding-window-size: 10
        failure-rate-threshold: 50
        wait-duration-in-open-state: 10s
  retry:
    instances:
      acquirer:
        max-attempts: 3
        wait-duration: 500ms
        enable-exponential-backoff: true
        exponential-backoff-multiplier: 2.0
```

---

## Step 4 — double money → BigDecimal; LocalDateTime → Instant

Before:
```java
private double amount;
private LocalDateTime timestamp;
```

After:
```java
private BigDecimal amount;   // setScale(2, RoundingMode.HALF_EVEN) at boundaries
private Instant timestamp;   // UTC — no settlement cut-off ambiguity
```

In the ledger this also deletes the epsilon balance check:

Before:
```java
// fintech/ledger-service/legacy/.../service/LedgerService.java
if (Math.abs(totalDebits - totalCredits) > BALANCE_EPSILON) { ... }
```

After:
```java
if (totalDebits.compareTo(totalCredits) != 0) { ... }   // exact, no epsilon
```

---

## Step 5 — Parameterise SQL (ledger-service)

Before (injectable, unparameterised):
```java
// fintech/ledger-service/legacy/.../repository/LedgerRepository.java
String sql = "INSERT INTO ledger_entries (journal_id, account_id, debit, credit) VALUES ('"
        + journalId + "', '" + entry.getAccountId() + "', "
        + entry.getDebit() + ", " + entry.getCredit() + ")";
jdbcTemplate.execute(sql);
```

After (bound parameters + journal wrapped in @Transactional):
```java
jdbcTemplate.update(
        "INSERT INTO ledger_entries (journal_id, account_id, debit, credit) VALUES (?, ?, ?, ?)",
        journalId, entry.getAccountId(), entry.getDebit(), entry.getCredit());
```

Add keyset pagination to `accountHistory` (`WHERE id > ? ... LIMIT ?`).

---

## Step 6 — In-JVM @Scheduled batches → event-driven (ledger-service)

Remove `EndOfDayBatchJob`'s poll-and-sleep loop. Replace with an EventBridge
schedule triggering a dedicated ECS task (or Step Functions state machine)
that is checkpointed and idempotent. The Spring service exposes a
`/reconcile` endpoint invoked by the task; a DynamoDB lock item prevents
double-runs across instances.

---

## Step 7 — Shared mutable state → externalised / immutable (payment-gateway, fx-settlement)

Payment gateway idempotency, before:
```java
// fintech/payment-gateway/legacy/.../service/PaymentService.java
private final Map<String, PaymentResponse> processedPayments = new HashMap<>();
synchronized (processedPayments) { ... }
```

After (port + Redis adapter in prod):
```java
// fintech/payment-gateway/modern/.../store/IdempotencyStore.java
public interface IdempotencyStore {
    Optional<PaymentResponse> find(String idempotencyKey);
    void put(String idempotencyKey, PaymentResponse response);
}
```

FX rate cache, before:
```java
// fintech/fx-settlement/legacy/.../service/FxRateCache.java
public static final Map<String, Double> RATES = new HashMap<>();
```

After: immutable snapshot record swapped via `AtomicReference<RateSnapshot>`,
each quote carrying `publishedAt` and a derived `stale` flag surfaced in API
responses.

---

## Step 8 — Add OpenTelemetry tracing and PCI-safe logging

```java
@Observed(name = "payments.authorise", contextualName = "authorise")
public PaymentResponse authorise(PaymentRequest request) {
```

Tokenise/mask the PAN before any outbound call or log line
(`PanTokeniser.tokenise` / `.mask`) — the raw card number must never leave
the service.

`application.yml`:
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

## Validation

```bash
# Behaviour parity: the same scenarios pass before and after
mvn -f fintech/payment-gateway/legacy/pom.xml test
mvn -f fintech/payment-gateway/modern/pom.xml test

# Modern-only assertions (typed outage status, exact money, masked PAN)
mvn -f fintech/payment-gateway/modern/pom.xml test -Dtest=PaymentServiceTest
```

The legacy and modern `PaymentServiceTest` classes assert the same three
business scenarios; the modern suite adds assertions the legacy service
cannot satisfy (ACQUIRER_UNAVAILABLE vs ERROR, `19.99` exactly representable,
no full PAN in any response).
