# Fintech Estate Modernisation Playbook

Corpus document for the `fintech-modernisation-agent` (retrieved via the RAG
service, `corpus: modernisation-playbooks`). One section per anti-pattern the
`code_inventory` tool can detect; the agent retrieves the sections matching a
service's fingerprint before selecting an AWS Transform definition.

## Anti-pattern: Spring Boot 2.x + javax.*

Apply `fintech-java-spring2-to-spring3`. Order matters: framework upgrade
first, then domain-specific definitions (`fintech-rules-to-agentic-rag`,
`fintech-soap-to-rest`) on the Boot 3.x baseline. Behaviour parity is proven
by running the legacy module's test scenarios unchanged against the migrated
module.

## Anti-pattern: RestTemplate with hand-rolled retry (Thread.sleep)

Replace with WebClient + Resilience4j `@Retry` (exponential backoff with
jitter) and `@CircuitBreaker` with a typed fallback exception. Never retry
non-idempotent operations without an idempotency key. Learning from the
payment-gateway migration: the legacy retry loop also retried 4xx responses —
the modern config must restrict retries to transport errors and 5xx.

## Anti-pattern: double for money or FX rates

Migrate to `BigDecimal` with explicit scale and `HALF_EVEN` rounding at
boundaries (or minor-unit `long` for high-throughput paths). Delete any
epsilon-based balance comparisons — with exact arithmetic, the ledger must
balance exactly. Learning from the ledger migration: search for `Math.abs(`
near comparison operators; every hit was masking drift.

## Anti-pattern: in-process shared mutable state (idempotency maps, rate caches)

Externalise idempotency to Redis behind a port interface; replace mutable
caches with immutable snapshots swapped via `AtomicReference`, each snapshot
carrying `publishedAt` so staleness is surfaced to callers instead of being
silently served.

## Anti-pattern: in-JVM @Scheduled batch with polling

Move to EventBridge schedule → ECS task / Step Functions with checkpointed,
idempotent steps and a distributed lock (DynamoDB conditional put). The
service keeps a `/reconcile` endpoint; the schedule owns the trigger.

## Anti-pattern: hardcoded compliance/fraud rule engines

Apply `fintech-rules-to-agentic-rag`. Decision data (watchlists, typologies,
thresholds) becomes governed documents in the RAG corpus; decisions come from
a Kiro agent with citation requirements and an eval gate. Fallback policy is
domain-specific and non-negotiable:

- KYC/sanctions: fail CLOSED (refer to human) — never auto-pass on outage.
- Fraud triage in the authorisation path: fail SAFE to the legacy rule score,
  marked `degraded: true`, so payments are not blocked by an agent outage.

## Anti-pattern: hand-built SOAP envelopes with regex parsing

Apply `fintech-soap-to-rest`. Strangler-fig: define the port
(`BureauScorePort`), implement REST and SOAP adapters side by side, cut over
with a feature flag, delete the SOAP adapter after one clean billing cycle.
Split "no data" (`Optional.empty()`) from "provider failure" (typed
exception) — the legacy `-1` conflated them and silently mis-routed
decisions.

## Verification standard (all migrations)

1. `mvn test` green on legacy and migrated modules; parity scenarios identical.
2. Golden-dataset gap cases added to `evals/deepeval/golden_dataset.json`
   and passing (`pytest evals/ -m deepeval`).
3. LLM-judge diff review score ≥ 0.8 before the agent opens the PR.
4. Harness CD gates (SAST, Trivy, DAST, canary) unchanged — the modernised
   service ships through the same pipeline as everything else.
