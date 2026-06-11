# Transformation Definition: fintech-soap-to-rest

Replace a hand-rolled SOAP 1.1 integration with the provider's REST v2 API
behind a typed anti-corruption layer, and decompose the monolithic decision
method it was buried in.

Authored against the concrete legacy service in
`fintech/loan-origination/legacy/` (credit bureau integration).

Run with:
```bash
atx custom def exec \
    --definition fintech-soap-to-rest \
    --source-path fintech/loan-origination/legacy \
    --output-path fintech/loan-origination/modern \
    --trust-all-tools
```

Prerequisite: run `fintech-java-spring2-to-spring3` first for the Boot 3.x /
WebClient / Resilience4j baseline.

---

## Step 1 — Define the anti-corruption port

The domain must not know SOAP, REST, or the bureau's field names.

```java
// fintech/loan-origination/modern/.../bureau/BureauScorePort.java
public interface BureauScorePort {
    /** Empty when the applicant has no credit file (thin file). */
    Optional<BureauScore> fetchScore(String applicantId);
}

public record BureauScore(int score, Instant retrievedAt, String bureauReference) {}
```

This removes the legacy `-1` magic number — "no file" is `Optional.empty()`,
a parse/transport failure is a thrown `BureauUnavailableException`, and the
two are no longer conflated.

---

## Step 2 — Replace the string-built SOAP envelope with the REST v2 client

Before (unescaped XML interpolation + regex parsing):
```java
// fintech/loan-origination/legacy/.../client/CreditBureauSoapClient.java
String envelope = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
        + "<soapenv:Envelope ...>"
        + "<bur:ApplicantId>" + applicantId + "</bur:ApplicantId>"
        ...
Matcher matcher = SCORE_PATTERN.matcher(response == null ? "" : response);
if (!matcher.find()) {
    return -1;
}
```

After (typed DTO, schema-validated by Jackson, resilient):
```java
// fintech/loan-origination/modern/.../bureau/RestBureauAdapter.java
@CircuitBreaker(name = "bureau", fallbackMethod = "bureauDown")
@Retry(name = "bureau")
public Optional<BureauScore> fetchScore(String applicantId) {
    BureauScoreResponse response = bureauWebClient.get()
            .uri("/v2/credit-files/{applicantId}/score", applicantId)
            .retrieve()
            .onStatus(status -> status.value() == 404, r -> Mono.empty())
            .bodyToMono(BureauScoreResponse.class)
            .timeout(Duration.ofSeconds(8))
            .block();
    return Optional.ofNullable(response)
            .map(r -> new BureauScore(r.score(), Instant.now(), r.reference()));
}
```

During the migration window, keep the SOAP path behind the same port
(`SoapBureauAdapter implements BureauScorePort`) and switch adapters with a
feature flag — strangler-fig, no big-bang cutover.

---

## Step 3 — Decompose the monolithic decide() method

Before: one method mixing bureau I/O, affordability maths and policy
thresholds (`LoanDecisionService.decide`, ~50 lines, constants frozen in
code).

After, three units with single responsibilities:

```java
// Pure function — property-testable, no I/O
public final class AffordabilityCalculator {
    public static BigDecimal monthlyRepayment(BigDecimal principal, int termMonths, BigDecimal apr) { ... }
    public static BigDecimal debtToIncome(BigDecimal income, BigDecimal existingDebt, BigDecimal newRepayment) { ... }
}

// Versioned, externally-loaded decision table (S3/AppConfig), hot-reloadable
public record CreditPolicy(String version, int declineBelowScore, int referBelowScore,
                           BigDecimal maxDebtToIncome, BigDecimal baseApr, BigDecimal subprimeLoading) {}

// Thin orchestrator
public class LoanDecisionService {
    public LoanDecision decide(LoanApplication application) {
        Optional<BureauScore> score = bureauScorePort.fetchScore(application.applicantId());
        CreditPolicy policy = policyProvider.current();
        Decision decision = DecisionRules.apply(score, affordability, policy);
        auditPublisher.publish(DecisionAuditEvent.of(application, score, policy.version(), decision));
        return decision.toResponse();
    }
}
```

---

## Step 4 — Emit a decision audit event

Every decision (approve/refer/decline) publishes an immutable event with the
inputs, the bureau reference, the policy version applied and the outcome —
to EventBridge → S3 (Athena-queryable). "Why was this applicant declined?"
becomes a query, not a log grep.

---

## Validation

```bash
# Legacy boundary behaviour still documented
mvn -f fintech/loan-origination/legacy/pom.xml test

# Post-migration: same decision boundaries, plus thin-file vs outage split
mvn -f fintech/loan-origination/modern/pom.xml test
```

Parity matrix the modern tests must preserve (from the legacy suite):
score 720 + affordable → APPROVED @ 6.9; score 500 → DECLINED;
score 600 → REFERRED @ 11.9; DTI > 0.45 → DECLINED. The legacy "-1 → REFERRED"
case splits into: thin file → REFERRED, bureau outage → typed 503 retryable.
