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

## Anti-pattern: known-vulnerable dependencies and code (CVEs)

Apply `fintech-cve-remediation` alongside the framework upgrade. Scan with
Trivy + OWASP dependency-check (dependency CVEs) and Semgrep (code-level).
The framework upgrade closes Spring-framework CVEs (e.g. Spring4Shell
CVE-2022-22965) as a side effect; the remediation definition closes the rest:

- Log4Shell (CVE-2021-44228): remove `log4j-core` 2.14.1 (Logback is the Boot
  default) or pin `log4j2.version` to 2.17.1.
- Text4Shell (CVE-2022-42889): `commons-text` 1.9 → 1.10.0.
- Commons Collections deserialization (CVE-2015-7501): 3.2.1 → 3.2.2 / remove.
- SnakeYAML (CVE-2022-1471): 1.30 → 2.x with `SafeConstructor`.
- Guava (CVE-2020-8908 / CVE-2018-10237): 24.1-jre → 33.x / remove.
- Code-level: parameterise SQL (CWE-89), replace string-built XML with a typed
  client (CWE-91/611), tokenise/mask the PAN (CWE-312 / PCI DSS 3.4).

Non-negotiable gate: re-scan after remediation must report **zero HIGH or
CRITICAL** findings, or the migration does not proceed to a PR. Learning from
the estate: a mixed-version fleet means each service has a different critical
set — never assume one uniform bump fixes everything; scan each module.

## Verification standard (all migrations)

1. `mvn test` green on legacy and migrated modules; parity scenarios identical.
2. Golden-dataset gap cases added to `evals/deepeval/golden_dataset.json`
   and passing (`pytest evals/ -m deepeval`).
3. LLM-judge diff review score ≥ 0.8 before the agent opens the PR.
4. Harness CD gates (SAST, Trivy, DAST, canary) unchanged — the modernised
   service ships through the same pipeline as everything else.
