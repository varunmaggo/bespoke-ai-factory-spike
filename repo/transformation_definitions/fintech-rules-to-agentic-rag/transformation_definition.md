# Transformation Definition: fintech-rules-to-agentic-rag

Convert a hardcoded rule engine into a Kiro agentic-RAG service: retrieval
over a governed document corpus, knowledge-graph entity resolution, Claude
reasoning with citations, and an eval gate before any decision reaches a
human or a downstream system.

Authored against two concrete legacy services:

| Legacy service | Rule engine being replaced | Target Kiro spec |
|---|---|---|
| `fintech/kyc-onboarding/legacy` | `SanctionsScreeningService` (exact-match watchlist) | `kiro/specs/kyc-screening-agent.kiro.yaml` |
| `fintech/fraud-detection/legacy` | `FraudRuleEngine` (if/else magic thresholds) | `kiro/specs/fraud-triage-agent.kiro.yaml` |

Run with:
```bash
atx custom def exec \
    --definition fintech-rules-to-agentic-rag \
    --source-path fintech/kyc-onboarding/legacy \
    --output-path fintech/kyc-onboarding/modern \
    --trust-all-tools
```

Prerequisite: run `fintech-java-spring2-to-spring3` first — this definition
assumes the Boot 3.x / WebClient / OTel baseline is already in place.

---

## Step 1 — Inventory the embedded rules and externalise them as documents

Extract every hardcoded list and threshold into versioned documents that the
RAG corpus can index, so domain teams update policy without a release.

Before (frozen in the binary):
```java
// fintech/kyc-onboarding/legacy/.../service/SanctionsScreeningService.java
private static final List<String> WATCHLIST = List.of(
        "JOHN DOE", "ACME SHELL HOLDINGS", "IVAN PETROV", "GLOBAL TRADE FZE");
private static final List<String> HIGH_RISK_COUNTRIES = List.of("KP", "IR", "SY");
```

After: the watchlist becomes the live OFAC/HMT/EU consolidated feeds ingested
nightly by `scripts/seed_data.py` into OpenSearch (chunks) and Neo4j
(entities + aliases + ownership edges); country risk policy becomes
`data/policy/country-risk-policy.md` with an effective-date header.

Same for the fraud engine:
```java
// fintech/fraud-detection/legacy/.../service/FraudRuleEngine.java
private static final double HIGH_AMOUNT_THRESHOLD = 10_000.00;
private static final int FLAG_SCORE_THRESHOLD = 50;
```
→ `data/policy/fraud-typologies.md` + the adjudicated-case corpus
(outcome-labelled alerts re-ingested nightly — the feedback loop the legacy
engine never had).

---

## Step 2 — Replace the rule evaluation with a Kiro agent invocation

Before (the whole decision in-process):
```java
// fintech/kyc-onboarding/legacy/.../service/SanctionsScreeningService.java
for (String listed : WATCHLIST) {
    if (name.contains(listed) || listed.contains(name)) {
        matches.add(listed);
    }
}
boolean blocked = !matches.isEmpty() || highRiskCountry;
return new ScreeningResult(blocked, matches);
```

After (delegate to the agent; service becomes a thin, resilient adapter):
```java
// fintech/kyc-onboarding/modern/.../service/ScreeningAgentClient.java
@CircuitBreaker(name = "kiro-agent", fallbackMethod = "agentDown")
@Retry(name = "kiro-agent")
public ScreeningOutcome screen(CustomerApplication application) {
    return kiroWebClient.post()
            .uri("/agents/kyc-screening-agent/invoke")
            .bodyValue(Map.of(
                    "applicant", Map.of(
                            "full_name", application.getFullName(),
                            "date_of_birth", application.getDateOfBirth(),
                            "nationality", application.getNationality(),
                            "residency_country", application.getResidencyCountry())))
            .retrieve()
            .bodyToMono(ScreeningOutcome.class)
            .timeout(Duration.ofSeconds(30))
            .block();
}
```

The agent pipeline (see the Kiro spec) is: `vector_search` over the sanctions
corpus → `graph_query` alias/associate resolution → `aws_transform`
(enterprise-context-normaliser: PII redaction before the LLM sees the case)
→ Claude generates a cited risk narrative → `eval_response` gates on
faithfulness ≥ 0.8.

---

## Step 3 — Fail-safe fallback policy

When the agent or its eval gate is unavailable, a compliance decision must
fail CLOSED (refer to a human), never OPEN:

```java
public ScreeningOutcome agentDown(CustomerApplication application, Throwable t) {
    return ScreeningOutcome.referred(
            "Automated screening unavailable — manual review required",
            List.of());
}
```

---

## Step 4 — Upgrade the response contract from binary to explainable

Before:
```java
// fintech/kyc-onboarding/legacy/.../model/ScreeningResult.java
private boolean blocked;
private List<String> matchedNames;
```

After:
```java
public class ScreeningOutcome {
    private RiskBand riskBand;              // PASS | REVIEW | BLOCK (typed)
    private double riskScore;               // calibrated 0.0–1.0
    private List<EntityMatch> matches;      // name, similarity, listSource, docId
    private String narrative;               // cited reasoning, [DOC-ID] markers
    private double evalScore;               // faithfulness score from the gate
    private boolean evalPassed;
    private String auditEventId;            // immutable audit trail reference
}
```

Every outcome is also emitted as an immutable audit event (the regulator's
"why was this blocked?" becomes a lookup, not a log grep).

---

## Step 5 — Golden-dataset regression for the decision boundary

The legacy unit tests documented the gaps; the modern eval suite must prove
they are closed. Add the gap cases to `evals/deepeval/golden_dataset.json`:

```json
{
  "input": "Screen applicant: Jon Doe, DOB 1980-01-01, GB national",
  "expected_behaviour": "REVIEW or BLOCK — fuzzy match on listed 'John Doe'",
  "legacy_behaviour": "PASS (exact-match miss)",
  "tags": ["kyc", "fuzzy-match"]
}
```

Cases to cover (from the legacy test suite's DOCUMENTED GAP tests):
- `Jon Doe` → spelling variant of listed `John Doe`
- `Iwan Petroff` → transliteration of listed `Ivan Petrov`
- velocity-only fraud burst that the additive score under-weighted

Run with `pytest evals/ -v -m deepeval` and gate the deployment in the
Harness CD pipeline on the eval pass rate, exactly as the existing
`enterprise-rag-agent` is gated.

---

## Validation

```bash
# Legacy gap tests still document the before-state
mvn -f fintech/kyc-onboarding/legacy/pom.xml test
mvn -f fintech/fraud-detection/legacy/pom.xml test

# Agent specs are valid and the golden gap-cases pass post-migration
kiro validate kiro/specs/kyc-screening-agent.kiro.yaml
kiro validate kiro/specs/fraud-triage-agent.kiro.yaml
pytest evals/ -v -m deepeval
```
