# Fintech Legacy Estate — Modernisation Demo

Six legacy Spring Boot 2.7.x fintech microservices and the machinery that
modernises them: **AWS Transform custom definitions** for the mechanical
migrations, **Kiro agent specs** for the agentic target states, and the
existing **agentic RAG + eval** stack as the quality gate.

## The estate

| Service | Port | Boot | Legacy sins (annotated in code) | Modernisation route |
|---|---|---|---|---|
| `payment-gateway` | 8081 | 2.3.12 | RestTemplate + `Thread.sleep` retry, in-memory idempotency map, `double` money, raw PAN, `javax.*` | `fintech-java-spring2-to-spring3` → **`payment-gateway/modern` (committed reference output, :9081)** |
| `ledger-service` | 8082 | 2.1.18 | Concatenated SQL, `double` + epsilon balance check, non-transactional posting, `Thread.sleep` EOD batch | `fintech-java-spring2-to-spring3` |
| `kyc-onboarding` | 8083 | 2.6.15 | Exact-match watchlist frozen in the binary, no narrative, no audit | `fintech-rules-to-agentic-rag` → `kiro/specs/kyc-screening-agent.kiro.yaml` |
| `fraud-detection` | 8084 | 2.4.13 | If/else rule engine, magic thresholds, uncalibrated additive score, per-JVM velocity state | `fintech-rules-to-agentic-rag` → `kiro/specs/fraud-triage-agent.kiro.yaml` |
| `loan-origination` | 8085 | 2.2.13 | Hand-built SOAP envelopes, regex response parsing, monolithic `decide()`, `-1` magic number | `fintech-soap-to-rest` |
| `fx-settlement` | 8086 | 2.5.14 | `public static HashMap` rate cache, data races, `double` cross-rates, stale rates with no flag | `fintech-java-spring2-to-spring3` |

The six services are deliberately pinned to a **spread of old, CVE-bearing
Spring Boot versions (2.1 → 2.6)** plus vulnerable standalone libraries, so a
scanner reports a different critical set per service — the heterogeneous
estate the factory agent has to handle. Each carries a `CVE profile:` note in
its `pom.xml`. The full picture is in
[`../transformation_definitions/fintech-cve-remediation/document_references/cve-inventory.md`](../transformation_definitions/fintech-cve-remediation/document_references/cve-inventory.md):
Spring4Shell (CVE-2022-22965) on the four older services, plus Log4Shell
(fraud), Text4Shell (loan), commons-collections deserialization (ledger),
SnakeYAML (kyc) and Guava (fx).

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

## Run & observe locally

```bash
# Modern gateway + stub acquirer + the existing observability stack
docker compose --profile fintech up -d payment-gateway stub-acquirer prometheus grafana otel-collector jaeger

curl -X POST localhost:9081/api/v1/payments/authorise \
  -H 'Content-Type: application/json' \
  -d '{"merchantId":"m-1","cardNumber":"4111111111111111","amount":19.99,"currency":"GBP","idempotencyKey":"demo-1"}'
```

What you get:

- **Business metrics** at `:9081/actuator/prometheus` — `payments_authorised_total`,
  `payments_declined_total`, `payments_acquirer_unavailable_total`,
  `payments_idempotent_replays_total`, `payments_authorised_amount_total{currency}`,
  and a `payments_acquirer_latency_seconds` histogram.
- **Grafana board** `Fintech — Payment Gateway` (auth vs decline rate, decline
  ratio, circuit-breaker state, acquirer p50/p95/p99, value by currency).
- **Alert rules** in `otel/prometheus-alerts.yml`: `AcquirerCircuitOpen`,
  `PaymentDeclineRateHigh`, `AcquirerOutageBurst`, `AcquirerLatencyP99High`,
  plus platform-wide 5xx/latency/up alerts.
- **Trace-correlated logs** — every request line carries `[traceId,spanId]`
  matching the Jaeger trace, PAN already masked.
- Stop `stub-acquirer` to watch retries → typed `ACQUIRER_UNAVAILABLE`
  responses → the circuit-open panel and alert fire; restart it and the
  gateway recovers without a restart.

## Deploy to AWS

The modern gateway ships through the same machinery as the rest of the stack:

- **Terraform** (`infra/terraform/`): `payment-gateway` is in the `services`
  map — ECR repo, Fargate task + ADOT sidecar, Cloud Map entry, target group,
  and an ALB rule routing `/api/v1/payments/*`. Set `acquirer_url` per env;
  `observability.tf` adds the SNS alert topic, CloudWatch alarms (ALB
  5xx/p95/unhealthy-hosts, ECS CPU/memory, acquirer-outage log-metric burst)
  and a CloudWatch dashboard.
- **Harness** (`harness/pipelines/ci-build-and-scan.yaml`): the estate is unit
  tested (`mvn -f fintech/pom.xml test`), the gateway image is built and
  pushed to ECR and Trivy-scanned alongside the other services; promote with
  the existing CD pipeline (canary in preprod/prod).

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
| `fintech-cve-remediation` | Security remediation | whole estate — scan → map CVE → patch, runs alongside the framework upgrade |

## Find and fix vulnerabilities on the fly

`fintech-cve-remediation` scans each service (Trivy + OWASP dependency-check
for dependency CVEs, Semgrep for code-level weaknesses), maps every finding to
a remediation, and applies it — dependency bumps/removals plus the same code
fixes the framework migration makes (parameterised SQL, typed REST client,
PAN tokenisation). The framework upgrade closes the Spring-framework CVEs
(Spring4Shell) as a side effect; this definition closes the standalone-library
and code-level findings it doesn't touch.

In the factory agent (`fintech-modernisation-agent`) this is two gated steps:
a `scan_before` baseline and a `scan_after` re-scan, and **the agent refuses
to open a PR while any HIGH/CRITICAL finding remains** — the same Trivy + ZAP
DAST bar the Harness CD pipeline already enforces.

## Modernise at scale with the factory agent

`kiro/specs/fintech-modernisation-agent.kiro.yaml` runs the whole loop for
one service per invocation:

```text
inventory (static analysis)
  → scan_before (Trivy + OWASP DC + Semgrep — the CVE profile)
  → retrieve playbook via agentic RAG     (data/sample-docs/fintech-modernisation-playbook.md)
  → select AWS Transform definition(s)    (Claude, temperature 0)
  → atx custom def exec                    (framework / architecture)
  → atx custom def exec                    (fintech-cve-remediation, if CVEs found)
  → mvn test (behaviour parity)
  → scan_after (must report 0 HIGH/CRITICAL)
  → LLM-judge diff review ≥ 0.8
  → draft PR  (blocked unless tests green AND 0 HIGH/CRITICAL CVEs)
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
