# Bespoke Agentic AI Factory — Spike

A robust reference implementation for building **bespoke agentic AI
pipelines** for Java Spring microservices: **AWS Kiro** agent specs, **AWS
Transform Custom** modernisation, **Agentic RAG** (hybrid vector + knowledge
graph), **LLM evaluation gates** (DeepEval + LLM-as-judge), and a full
**AWS/Terraform/Harness** deployment platform with canary releases and
SAST/DAST security gates.

> All project sources live in [repo/](repo/) — see the
> [project README](repo/README.md) for the local quick start
> (`docker compose up`).

## What's inside

| Area | Where | Highlights |
|---|---|---|
| Agentic RAG service | [repo/services/rag/](repo/services/rag/) | FastAPI :8001 — multi-hop retrieval, OpenSearch hybrid search (dense k-NN + BM25 fused with RRF), Neo4j graph enrichment, Claude sufficiency checks |
| Eval service | [repo/services/eval/](repo/services/eval/) | FastAPI :8002 — DeepEval metrics (relevancy, faithfulness, hallucination…) + Claude LLM-as-judge with weighted rubric; gates every answer |
| Transform service | [repo/services/transform/](repo/services/transform/) | FastAPI :8003 — wraps `atx custom def exec` (AWS Transform CLI) with a local Python fallback: PII redaction, ISO-8601 date normalisation, SAP OData flattening, token-budget truncation |
| Spring modernisation | [repo/spring/](repo/spring/) | Before/after pair: legacy Spring Boot 2.7 (`ChatClient`, RestTemplate, Solr) → modern Spring Boot 3 + Spring AI 1.0 (`AnthropicChatModel`, WebClient, Resilience4j, OTel, eval gate) — the `java-spring-to-spring-ai` AWS Transform definition drives the migration |
| AWS Transform definitions | [repo/transformation_definitions/](repo/transformation_definitions/) | `enterprise-context-normaliser`, `java-spring-to-spring-ai`, `eval-dataset-updater` |
| Kiro agent spec | [repo/kiro/specs/](repo/kiro/specs/) | retrieve → enrich → transform → generate → validate pipeline with retry policy and OTel hooks |
| Evaluation suite | [repo/evals/](repo/evals/) | Golden dataset, DeepEval CI gate, LLM-judge with self-consistency |
| Tests | [repo/tests/](repo/tests/) | 75 unit/integration tests (all mocked, no infra needed) + smoke suite against live services |
| Observability | [repo/otel/](repo/otel/) | OTel Collector → Prometheus / Jaeger / Grafana (provisioned dashboards) |

## Architecture

Open [repo/docs/architecture.drawio](repo/docs/architecture.drawio) in
[draw.io](https://app.diagrams.net) — three pages with official AWS icons:

1. **AWS Architecture (per env)** — ALB → ECS Fargate services with ADOT
   sidecars, Cloud Map discovery, Amazon OpenSearch, Neo4j on ECS + EFS,
   ECR / Secrets Manager / CloudWatch
2. **Harness CI/CD Pipeline** — SAST → build → Trivy → ECR, then
   dev → sit → DAST → preprod → prod with canary execution detail
3. **Environment Promotion** — dev / sit / preprod / prod sizing and gates

## AWS deployment (dev → sit → preprod → prod)

| Piece | Where | Summary |
|---|---|---|
| Runbook | [repo/docs/deployment-guide.md](repo/docs/deployment-guide.md) | Bootstrap, Harness setup, canary mechanics, costs |
| Terraform | [repo/infra/terraform/](repo/infra/terraform/) | One stack, four env var-files; VPC, ECS Fargate, ALB, OpenSearch, Neo4j+EFS, ECR, Secrets Manager; isolated S3 state per env |
| Harness CI | [repo/harness/pipelines/ci-build-and-scan.yaml](repo/harness/pipelines/ci-build-and-scan.yaml) | pytest + mvn → **SAST** (Semgrep, Gitleaks, OWASP dep check) → 4 image builds → **Trivy** scan → ECR |
| Harness infra | [repo/harness/pipelines/infra-terraform.yaml](repo/harness/pipelines/infra-terraform.yaml) | terraform plan → human approval → apply (rollback on failure) |
| Harness CD | [repo/harness/pipelines/cd-deploy.yaml](repo/harness/pipelines/cd-deploy.yaml) | dev/sit rolling → **DAST** (OWASP ZAP vs SIT) → approvals → **ECS canary** (25% → 10-min verify → 100%, auto-rollback) for preprod/prod |

Promotion gates: smoke tests (dev) → ZAP clean + approval (sit) → canary
verified + approval (preprod) → 2-person approval + canary (prod).

## Quick start (local)

```bash
cd repo
cp .env.example .env       # add ANTHROPIC_API_KEY
docker compose up -d
python scripts/seed_data.py --source ./data/sample-docs/
curl -X POST http://localhost:8080/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is our Q2 revenue forecast?", "userId": "user-123"}'
```

Run the tests (no infrastructure needed — everything external is mocked):

```bash
cd repo && python -m pytest        # 75 tests
```

## Repository layout

```text
.
├── repo/                       # project sources (see repo/README.md)
│   ├── services/               # rag / eval / transform microservices (FastAPI)
│   ├── spring/                 # legacy + modern Spring Boot services
│   ├── transformation_definitions/  # AWS Transform Custom definitions
│   ├── kiro/                   # AWS Kiro agent spec
│   ├── evals/                  # DeepEval + LLM-judge + golden dataset
│   ├── tests/                  # unit / integration / smoke
│   ├── infra/terraform/        # AWS environments (dev/sit/preprod/prod)
│   ├── harness/                # CI/CD pipeline definitions
│   ├── docs/                   # architecture.drawio + deployment guide
│   ├── otel/                   # local observability stack config
│   └── docker-compose.yml      # full local stack
└── .github/                    # repo automation
```
