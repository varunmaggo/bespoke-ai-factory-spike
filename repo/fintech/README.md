# Fintech Legacy Estate — Modernisation Demo

Six legacy Spring Boot 2.7.x fintech microservices and the machinery that
modernises them: **AWS Transform custom definitions** for the mechanical
migrations, **Kiro agent specs** for the agentic target states, and the
existing **agentic RAG + eval** stack as the quality gate.

## The estate

| Service | Port | Legacy sins (annotated in code) | Modernisation route |
|---|---|---|---|
| `payment-gateway` | 8081 | RestTemplate + `Thread.sleep` retry, in-memory idempotency map, `double` money, raw PAN, `javax.*` | `fintech-java-spring2-to-spring3` → **`payment-gateway/modern` (committed reference output, :9081)** |
| `ledger-service` | 8082 | Concatenated SQL, `double` + epsilon balance check, non-transactional posting, `Thread.sleep` EOD batch | `fintech-java-spring2-to-spring3` |
| `kyc-onboarding` | 8083 | Exact-match watchlist frozen in the binary, no narrative, no audit | `fintech-rules-to-agentic-rag` → `kiro/specs/kyc-screening-agent.kiro.yaml` |
| `fraud-detection` | 8084 | If/else rule engine, magic thresholds, uncalibrated additive score, per-JVM velocity state | `fintech-rules-to-agentic-rag` → `kiro/specs/fraud-triage-agent.kiro.yaml` |
| `loan-origination` | 8085 | Hand-built SOAP envelopes, regex response parsing, monolithic `decide()`, `-1` magic number | `fintech-soap-to-rest` |
| `fx-settlement` | 8086 | `public static HashMap` rate cache, data races, `double` cross-rates, stale rates with no flag | `fintech-java-spring2-to-spring3` |

Every legacy class carries `PROBLEM:` / `MIGRATE TO:` annotations, and the
unit tests include **DOCUMENTED GAP** cases that assert the broken behaviour
(e.g. `"Jon Doe"` passing sanctions screening) — the same scenarios appear in
`evals/deepeval/golden_dataset.json` (GOLD-006…008) as the post-migration
acceptance bar.

## Build

```bash
mvn -f fintech/pom.xml clean test
```

All seven modules (six legacy + the modern payment gateway) build with plain
Maven Central dependencies — no AWS access needed.

## Run a migration with AWS Transform

```bash
# Reference pair: regenerate the modern payment gateway from the legacy one
atx custom def exec \
    --definition fintech-java-spring2-to-spring3 \
    --source-path fintech/payment-gateway/legacy \
    --output-path fintech/payment-gateway/modern \
    --trust-all-tools

# Then prove behaviour parity
mvn -f fintech/payment-gateway/legacy/pom.xml test
mvn -f fintech/payment-gateway/modern/pom.xml test
```

The three definitions live in `../transformation_definitions/`:

| Definition | Pattern | Applies to |
|---|---|---|
| `fintech-java-spring2-to-spring3` | Framework upgrade | payment-gateway, ledger-service, fx-settlement (and as the baseline for the rest) |
| `fintech-rules-to-agentic-rag` | Rules → Kiro agentic RAG | kyc-onboarding, fraud-detection |
| `fintech-soap-to-rest` | Strangler-fig integration swap | loan-origination |

## Modernise at scale with the factory agent

`kiro/specs/fintech-modernisation-agent.kiro.yaml` runs the whole loop for
one service per invocation:

```text
inventory (static analysis)
  → retrieve playbook via agentic RAG     (data/sample-docs/fintech-modernisation-playbook.md)
  → select AWS Transform definition       (Claude, temperature 0)
  → atx custom def exec
  → mvn test (behaviour parity)
  → LLM-judge diff review ≥ 0.8
  → draft PR
```

The two runtime agents it produces for the rules-based services:

- **kyc-screening-agent** — semantic + graph alias matching over sanctions
  corpora, PII-redacting transform, cited risk narrative, eval gate ≥ 0.8,
  fails **closed** (REVIEW) on any outage.
- **fraud-triage-agent** — precedent-case retrieval, network signals from
  the transaction graph, calibrated risk band, eval gate ≥ 0.75, fails
  **safe** to the legacy rule score with `degraded: true`.

## Demo narrative (suggested order)

1. Show a legacy sin in code — e.g. `SanctionsScreeningService` and its
   passing `trivialSpellingVariantSlipsThrough` test.
2. Walk the matching transformation definition's before/after snippets.
3. Show the committed reference output: `payment-gateway/legacy` vs
   `payment-gateway/modern`, same test scenarios green on both.
4. Open the Kiro specs to show the agentic target state and the eval gates.
5. Close the loop: GOLD-006…008 in the golden dataset are the legacy gaps,
   now phrased as acceptance criteria the modernised estate must satisfy.
