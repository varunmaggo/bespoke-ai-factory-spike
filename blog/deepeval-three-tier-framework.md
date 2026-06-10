# A Three-Tier Evaluation Framework for Multi-Agent AI Pipelines

## How we used DeepEval to build deterministic rules, slice disparity checks, and automated CI/CD safety gates for a complex agentic workflow — and how to run it all locally without an API key

---

Imagine this: You deploy an AI-driven lending assistant built on a state-of-the-art LLM. For weeks, it performs flawlessly. Then, a borrower slightly tweaks their application text, bypassing fraud detection using a subtle prompt injection. The LLM agent enthusiastically approves a high-risk, $100,000 bad loan, writing a beautifully composed, highly logical-sounding justification for the approval.

By the time your risk team realises what happened, the funds are gone.

Testing multi-agent LLM systems in production is one of the hardest problems in modern AI engineering. Traditional unit tests fail because LLM outputs are semantic, non-deterministic, and context-dependent. Manual prompt verification doesn't scale.

In this article, we'll demonstrate how we solved this in our enterprise AI factory pipeline. We built a **Three-Tier Evaluation Framework using DeepEval** — integrating hard gates, fairness slice checks, and nightly LLM judges directly into our CI/CD pipeline. And crucially, we designed Tiers 1 and 2 to run **fully offline, with zero API calls**, so every developer can run the safety suite locally before pushing a single line of code.

---

## The Evaluation Challenge: Why Agentic AI Breaks Traditional Testing

Multi-agent architectures introduce unique, emergent testing challenges that traditional testing suites simply cannot capture:

| Testing Challenge | Impact in Production | Why Traditional Testing Fails | Why LLM-Specific Evals Win |
| :--- | :--- | :--- | :--- |
| 🔗 **Cross-Agent Dependencies** | Logic breaks during handoffs between agents | Unit testing per agent misses integration bugs | **E2E Integration Datasets** capture inter-agent communication |
| 🛡️ **Policy Compliance** | Subtle prompt changes violate lending laws | Regex checks are too brittle for variable natural language | **Deterministic Policy Metrics** audit decisions from raw agent outputs |
| ⚖️ **Bias & Slice Disparity** | Unintentional bias against customer groups | Ad-hoc analytics catch bias weeks after deployment | **Automated Slice Disparity Analysis** blocks biased builds in CI/CD |
| ✍️ **Reasoning Quality** | Hallucinated underwriting justifications | Exact-match checks fail valid language variations | **GEval Semantic Judges** evaluate reasoning quality against guidelines |

### The High Cost of Poor Evaluation

Without automated semantic testing, your pipeline suffers from:

- **Manual Testing Overhead:** 20–40 hours per week wasted manually inspecting logs
- **Leaked Regressions:** 5–10 reasoning bugs reaching production monthly
- **Compliance Risks:** Silently failing regulatory criteria, risking heavy audits
- **Inflated MTTR:** Days spent trying to reproduce and debug flaky LLM behaviour

---

## What to Evaluate: The Five Critical Layers

To ensure complete production safety, we break down our evaluation strategy into five distinct logical layers:

1. **Schema Integrity:** Ensures the output contains all mandatory JSON fields and conforms to typing rules. *(Deterministic | CI/CD)*
2. **Policy Compliance:** Audits the final decision against hard business rules based on the raw outputs of the specialist agents. *(Deterministic | CI/CD)*
3. **Model Calibration:** Checks recommendations and risk bands against standard test datasets. *(Deterministic | CI/CD)*
4. **Coherence & Groundedness:** Validates that the reasoning is factual and grounded in the outputs of the specialists. *(Semantic Judge | Nightly)*
5. **End-to-End Integration:** Simulates complete agent workflows, tracking state across multiple steps. *(Deterministic | CI/CD)*

### The Three-Tier Evaluation Strategy

We organise these layers into three separate execution tiers, striking the perfect balance between build speed, API costs, and evaluation depth:

- **Tier 1 (Hard Gates):** Runs on every pull request. Fast, 100% deterministic, and free. A single failure blocks the build.
- **Tier 2 (Fairness & Bias Checks):** Runs on every pull request. Identifies systematic bias or slice disparities across applicant groups.
- **Tier 3 (Cognitive LLM Judges):** Runs nightly or on release candidates. Requires an LLM API key. Evaluates nuance and reasoning quality.

The key insight: **Tiers 1 and 2 require no API key whatsoever.** Any developer can run them locally with a single command.

---

## Project Structure

We implemented the framework in two variants — a lending pipeline demo (mirrors the article's use case exactly) and an adapted version for our RAG service:

```
evals/deepeval/
├── lending_demo/
│   ├── loan_triage/           # Stub multi-agent pipeline
│   │   ├── schemas.py         # Pydantic models
│   │   └── orchestrator.py    # Rule-based decision stub
│   ├── metrics.py             # Tier 1 + Tier 2 metrics
│   ├── test_tier1_gates.py    # Hard gate tests
│   └── test_tier2_disparity.py
├── rag_tiers/
│   ├── metrics.py             # RAG-adapted metrics
│   ├── test_tier1_gates.py
│   └── test_tier2_disparity.py
├── ci_suite.py                # Tier 3 — LLM judge suite (needs API key)
└── run_local.sh               # One-command local runner
```

---

## Building the Test Harness

To test a multi-agent system, we must capture not just the final output but the entire trace of inter-agent interactions. Our stub pipeline uses Pydantic models and a deterministic rule-based orchestrator so the eval suite can run without any live LLM:

```python
# loan_triage/schemas.py
from pydantic import BaseModel, Field
from typing import Any, Dict, List

class LoanApplication(BaseModel):
    application_id: str
    applicant: Applicant
    loan_amount: float
    loan_purpose: str

class TriageDecision(BaseModel):
    application_id: str
    recommendation: str   # "approve" | "approve_fast_track" | "reject" | "human_review"
    status: str
    risk_band: str
    reasons: List[str]

class RunMemory(BaseModel):
    run_id: str
    application_id: str
    messages: List[AgentMessage] = Field(default_factory=list)
    tool_outputs: Dict[str, Any] = Field(default_factory=dict)
```

The orchestrator simulates credit scoring, KYC verification, and risk banding — allowing us to write deterministic tests against known inputs:

```python
# loan_triage/orchestrator.py
def run_triage_system(application: LoanApplication) -> AgentRun:
    memory = RunMemory(run_id=str(uuid.uuid4()), application_id=application.application_id)
    orchestrator = Orchestrator()
    result = orchestrator.process(application.model_dump(), memory)
    memory.mark_complete()
    return AgentRun(
        run_id=memory.run_id,
        application_id=application.application_id,
        decision=TriageDecision(**result["decision"]),
        messages=memory.messages,
        tool_outputs=memory.tool_outputs,
    )
```

We then wrap the execution result in a DeepEval `LLMTestCase`, storing the raw agent tool outputs in `additional_metadata` so our policy metric can re-audit them:

```python
def _run_to_test_case(application: LoanApplication) -> LLMTestCase:
    run = run_triage_system(application)
    return LLMTestCase(
        input=json.dumps(application.model_dump()),
        actual_output=json.dumps(run.decision.model_dump()),
        additional_metadata={
            "tool_outputs": run.tool_outputs,
            "slice": application.applicant.risk_band,
        },
    )
```

---

## Tier 1: Deterministic Metrics (The Hard Gates)

Tier 1 metrics are fast, cost nothing, and run on every commit. They ensure the multi-agent system never violates hard business rules.

### PolicyComplianceMetric

Re-audits the Decision Agent's output against hard business rules using the raw specialist agent tool outputs — not the final prose justification. This means a convincing-sounding approval for a 580 credit-score applicant gets caught immediately:

```python
class PolicyComplianceMetric(BaseMetric):
    @property
    def __name__(self):
        return "PolicyComplianceMetric"

    def measure(self, test_case: LLMTestCase) -> float:
        actual = json.loads(test_case.actual_output)
        tool_outputs = (test_case.additional_metadata or {}).get("tool_outputs", {})

        # Rule 1 — credit floor
        credit = tool_outputs.get("credit_agent", {})
        if credit.get("credit_score", 999) < 650 and actual.get("recommendation") != "reject":
            self.score, self.success = 0.0, False
            return 0.0

        # Rule 2 — KYC gate
        kyc = tool_outputs.get("kyc_agent", {})
        if not kyc.get("verified", True) and actual.get("recommendation") not in ("reject", "human_review"):
            self.score, self.success = 0.0, False
            return 0.0

        self.score, self.success = 1.0, True
        return 1.0

    def is_successful(self) -> bool:
        return self.success
```

**Why this matters:** The metric re-derives the correct answer from raw specialist outputs independently of what the Decision Agent said. It can't be fooled by a fluent justification.

### SchemaValidityMetric

Ensures the agent produces complete, well-formed JSON. A single missing field or an invalid `recommendation` value scores below threshold and blocks the build:

```python
class SchemaValidityMetric(BaseMetric):
    REQUIRED_FIELDS = ["application_id", "recommendation", "status", "risk_band", "reasons"]

    def measure(self, test_case: LLMTestCase) -> float:
        actual = json.loads(test_case.actual_output)
        present = sum(1 for f in self.REQUIRED_FIELDS if f in actual)
        reasons_ok = isinstance(actual.get("reasons"), list) and len(actual.get("reasons", [])) > 0
        recommendation_ok = actual.get("recommendation") in (
            "approve", "approve_fast_track", "reject", "human_review"
        )
        self.score = (present + int(reasons_ok) + int(recommendation_ok)) / (len(self.REQUIRED_FIELDS) + 2)
        self.success = self.score >= self.threshold
        return self.score
```

### ExactMatchMetric

For regression testing: verifies that `recommendation` and `risk_band` exactly match our golden calibration baseline. Catches model drift when the underlying LLM is updated:

```python
class ExactMatchMetric(BaseMetric):
    def measure(self, test_case: LLMTestCase) -> float:
        actual   = json.loads(test_case.actual_output)
        expected = json.loads(test_case.expected_output)
        rec_match  = actual.get("recommendation") == expected.get("recommendation")
        band_match = actual.get("risk_band")       == expected.get("risk_band")
        self.score   = float(rec_match and band_match)
        self.success = self.score >= self.threshold
        return self.score
```

### Running Tier 1 Tests

The test file uses three sub-suites:

```python
# test_tier1_gates.py

# Suite 1 — Happy path: stub orchestrator produces correct decisions
@pytest.mark.parametrize("app_id,credit,kyc,band,exp_rec,exp_risk", HAPPY_PATH_CASES)
def test_policy_compliance(app_id, credit, kyc, band, exp_rec, exp_risk):
    tc = _run_to_test_case(_make_application(app_id, credit, kyc, band))
    assert_test(tc, [PolicyComplianceMetric(threshold=0.85)])

# Suite 2 — Regression: known golden Q&A; ExactMatch verifies calibration
@pytest.mark.parametrize("case", REGRESSION_CASES)
def test_exact_match_regression(case):
    tc = _run_to_test_case(_make_application(...), expected=case["expected"])
    assert_test(tc, [ExactMatchMetric(threshold=0.90)])

# Suite 3 — Violations: xfail tests that prove the metrics catch bad outputs
@pytest.mark.xfail(reason="Demonstrates PolicyComplianceMetric catching Rule 1 violation")
def test_policy_violation_low_credit_approved():
    bad_output = json.dumps({"recommendation": "approve", "risk_band": "medium", ...})
    tc = LLMTestCase(actual_output=bad_output, additional_metadata={
        "tool_outputs": {"credit_agent": {"credit_score": 580}, "kyc_agent": {"verified": True}}
    })
    assert_test(tc, [PolicyComplianceMetric(threshold=0.85)])
```

The `xfail` violation tests are a teaching tool: they run on every PR, show up in the pytest report as "expected failures", and make it immediately obvious that the metrics are actively catching the bad behaviour — not silently passing.

---

## Tier 2: Slice Disparity Analysis (Fairness Auditing)

To prevent unintentional bias, we analyse metrics across specific segments of our dataset. We compute the approval rate across risk bands and check that the Decision Agent is applying policy consistently:

```python
def calculate_slice_disparity(
    test_cases: List[LLMTestCase],
    max_disparity: float = 0.40,
) -> Dict[str, Any]:
    approvals: Dict[str, int] = {}
    totals:    Dict[str, int] = {}

    for case in test_cases:
        actual = json.loads(case.actual_output)
        band   = (case.additional_metadata or {}).get("slice", "unknown")
        totals[band] = totals.get(band, 0) + 1
        if actual.get("recommendation") in ("approve", "approve_fast_track"):
            approvals[band] = approvals.get(band, 0) + 1

    rates   = {b: approvals.get(b, 0) / totals[b] for b in totals}
    spread  = max(rates.values()) - min(rates.values())
    passed  = spread <= max_disparity

    return {
        "rates":     rates,
        "disparity": round(spread, 4),
        "passed":    passed,
        "violation": None if passed else f"Disparity {spread:.2%} exceeds {max_disparity:.2%}. Rates: {rates}",
    }
```

The Tier 2 test generates a visual report and a threshold check:

```
── Tier 2 Slice Disparity Report ──────────────────────────────
  high       0%
  low      100%  ████████████████████
  medium    50%  ██████████

  Disparity (max − min): 100.00%
  Status: ❌ FAILED
  Note: Approval-rate disparity 100.00% exceeds threshold 40.00%.
────────────────────────────────────────────────────────────────
```

This large gap is **intentional and expected** for the stub: all `high`-band applicants route to human review by policy. In a real system you would tune `max_disparity` to reflect your acceptable business-driven spread, or add sub-slices that distinguish policy-driven rejections from model-driven ones.

---

## Adapting Tier 1 & 2 for a RAG Pipeline

The same framework adapts naturally to a RAG service. We replace the lending-specific rules with three RAG-specific metrics:

### RAGSchemaValidityMetric

Checks the response is structurally sound: non-empty, minimum length (rejects trivial "Yes"/"No" answers), context was provided, and no error prefix leaked through:

```python
class RAGSchemaValidityMetric(BaseMetric):
    ERROR_PREFIXES = ("error:", "traceback", "exception:", "500 ", "none", "null")

    def measure(self, test_case: LLMTestCase) -> float:
        output  = (test_case.actual_output or "").strip()
        context = test_case.retrieval_context or []
        checks = {
            "non_empty":       bool(output),
            "min_length":      len(output) >= self.min_length,
            "context_present": len(context) > 0,
            "no_error_prefix": not output.lower().startswith(self.ERROR_PREFIXES),
        }
        self.score   = sum(checks.values()) / len(checks)
        self.success = self.score >= self.threshold
        return self.score
```

### RAGPolicyComplianceMetric

Catches two production failure modes deterministically — no LLM required:

1. **Unjustified refusal:** if retrieval context was supplied, the model must not respond with "I don't know" / "I cannot answer"
2. **PII leakage:** response must not match SSN, credit card, or email regex patterns

```python
_REFUSAL_PATTERNS = re.compile(
    r"\b(i (don'?t|cannot) (know|answer|help)|no information|unable to (answer|provide))\b",
    re.IGNORECASE,
)
_PII_PATTERNS = re.compile(
    r"\b\d{3}-\d{2}-\d{4}\b"           # SSN
    r"|\b(?:\d{4}[\s-]?){3}\d{4}\b"    # Credit card
    r"|\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",  # Email
)
```

### RAGKeywordMatchMetric

Token-level match against `expected_output`. Rather than brittle exact-string comparison, we extract meaningful tokens (numbers, domain terms, proper nouns) and check what fraction appear in the actual response — handling paraphrasing gracefully:

```python
def measure(self, test_case: LLMTestCase) -> float:
    expected_tokens = self._key_tokens(test_case.expected_output)
    actual_lower    = (test_case.actual_output or "").lower()
    matched  = [t for t in expected_tokens if t in actual_lower]
    self.score = len(matched) / len(expected_tokens)
    self.success = self.score >= self.threshold
    return self.score
```

### RAG Slice Disparity

For RAG we slice by **query category** (financial, compliance, operational, safety) and measure a heuristic quality score per category — catching the scenario where your knowledge base is well-indexed for financial queries but poorly chunked for compliance documents:

```
── Tier 2 RAG Slice Quality Report ─────────────────────────────
  compliance    100%  ████████████████████
  financial     100%  ████████████████████
  operational   100%  ████████████████████
  safety        100%  ████████████████████

  Disparity (max − min): 0.00%
  Status: ✅ PASSED
────────────────────────────────────────────────────────────────
```

---

## Tier 3: LLM Judges (Nightly)

Tiers 1 and 2 handle everything deterministic. Tier 3 adds semantic evaluation using an LLM as judge — this is where DeepEval's built-in metrics shine:

```python
# ci_suite.py — requires ANTHROPIC_API_KEY or OPENAI_API_KEY
from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric, HallucinationMetric

MODEL = os.getenv("EVAL_MODEL", "claude-sonnet-4-20250514")

answer_relevancy = AnswerRelevancyMetric(threshold=0.80, model=MODEL)
faithfulness     = FaithfulnessMetric(threshold=0.85, model=MODEL)
hallucination    = HallucinationMetric(threshold=0.10, model=MODEL)
```

These run nightly in CI, not on every PR — keeping build times fast while still catching semantic regressions before they reach the next release candidate.

---

## Running the Full Suite Locally

```bash
# Install dependencies (one-time)
pip install -r requirements-eval.txt

# Run everything — Tiers 1 & 2 only (no API key needed)
cd evals/deepeval
./run_local.sh all

# Target specific suites
./run_local.sh lending    # Lending demo: Tier 1 + Tier 2
./run_local.sh rag        # RAG pipeline: Tier 1 + Tier 2
./run_local.sh tier1      # Hard gates across both suites

# Tier 3 — requires API key
export ANTHROPIC_API_KEY=sk-ant-...
pytest ci_suite.py -v
```

The shell script disables DeepEval telemetry (`DEEPEVAL_TELEMETRY_OPT_OUT=YES`) and uses `-p no:deepeval` to suppress the DeepEval pytest plugin banner during local runs, keeping the output clean.

---

## CI/CD Integration

The three tiers map naturally to GitHub Actions jobs:

```yaml
# .github/workflows/eval.yml
jobs:
  tier1-hard-gates:        # Every PR — fast, free, offline
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install -r requirements-eval.txt
      - run: |
          cd evals/deepeval
          pytest lending_demo/test_tier1_gates.py rag_tiers/test_tier1_gates.py -v

  tier2-fairness:          # Every PR — slice disparity checks
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install -r requirements-eval.txt
      - run: |
          cd evals/deepeval
          pytest lending_demo/test_tier2_disparity.py rag_tiers/test_tier2_disparity.py -v -s

  tier3-llm-judges:        # Nightly — semantic evaluation
    runs-on: ubuntu-latest
    if: github.event_name == 'schedule'
    env:
      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
    steps:
      - uses: actions/checkout@v4
      - run: pip install -r requirements-eval.txt
      - run: cd evals/deepeval && pytest ci_suite.py -v
```

---

## Calibration Report: Results After Implementation

```
Tier 1 — Lending Demo Hard Gates
  PolicyComplianceMetric   8/8 PASSED ✅  (100% compliant)
  SchemaValidityMetric     8/8 PASSED ✅  (Valid JSON schema)
  ExactMatchMetric         3/3 PASSED ✅  (Calibration baseline met)
  Violation xfails         3/3 XFAIL  ✅  (Metrics catching violations as expected)

Tier 1 — RAG Pipeline Hard Gates
  RAGSchemaValidityMetric  5/5 PASSED ✅
  RAGPolicyComplianceMetric 5/5 PASSED ✅
  RAGKeywordMatchMetric    5/5 PASSED ✅
  Violation xfails         3/3 XFAIL  ✅

Tier 2 — Slice Disparity
  Lending  disparity report printed (expected xfail on 40% threshold)
  RAG      disparity 0.00% across 4 categories ✅
```

---

## Key Design Decisions

**Why custom `BaseMetric` rather than DeepEval's built-ins for Tiers 1 & 2?**
Built-in metrics like `AnswerRelevancyMetric` call an LLM judge internally. For hard gates and fairness checks, that's too slow, too expensive, and too non-deterministic for a PR gate. Custom metrics give you sub-millisecond deterministic evaluation.

**Why `xfail` for violation tests rather than skipping them?**
`xfail` tests run and are reported. A developer opening the pytest output sees the violation scenarios listed as "expected failures" — proof the safety net is active, not absent. If a violation test somehow starts *passing*, pytest promotes it to `XPASS` and flags it as unexpected, which is itself a signal worth investigating.

**Why store `tool_outputs` in `additional_metadata`?**
DeepEval test cases carry `actual_output` (what the final agent said) and `retrieval_context` (documents retrieved). Neither is the right place for intermediate agent state. `additional_metadata` is a free-form dict specifically designed for this — it lets Tier 1 metrics re-audit the raw specialist outputs independently of the final decision prose.

**Why token-level match rather than exact-string for RAG?**
RAG responses are paraphrased by design. "The ROE was 9.0%" and "Return on equity came to 9.0% for the quarter" carry the same information but fail exact-string comparison. Token-level matching on meaningful terms (numbers, entities, domain vocabulary) catches real hallucinations — wrong numbers, wrong names — without penalising valid rephrasing.

---

## What's Next

- **Tier 3 GEval criteria** for the lending pipeline: coherence and groundedness judges that verify the Decision Agent's reasoning traces against the raw specialist outputs
- **Dataset versioning**: storing the golden test sets in S3 and loading them at test time, so the same fixture serves both CI and nightly jobs
- **Prometheus integration**: emitting slice disparity as a gauge metric so dashboards can show fairness drift over time alongside latency and error rates
- **Prompt injection test cases**: adversarial inputs in the golden dataset that attempt to override policy rules through the input text, not just the output

---

## Summary

The three-tier framework gives you a layered defence against the failure modes that matter most in production multi-agent systems:

- **Tier 1** catches hard policy violations and schema breakage on every PR in milliseconds
- **Tier 2** surfaces systematic fairness gaps before they compound in production
- **Tier 3** evaluates the semantic quality that deterministic rules can't reach — nightly, with full LLM power

The critical property: **Tiers 1 and 2 run entirely offline.** No API key, no network call, no cost. Every developer on the team can run `./run_local.sh all` before pushing and get instant confidence that the safety gates are holding.

The full implementation lives in `evals/deepeval/` in the repository. Pull it, run it, and adapt the metrics to your domain — the patterns are the same whether you're evaluating a lending pipeline, a RAG service, or any other multi-agent workflow.
