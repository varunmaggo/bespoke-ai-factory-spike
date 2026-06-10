# Bespoke Agentic AI Factory — Spike

A production-ready reference architecture for building composable, observable AI pipelines using **AWS Kiro**, **AWS Transform Custom**, **Agentic RAG**, **DeepEval**, and **Spring AI**.

## Architecture

```text
Client (Spring :8080)
    └── AWS Kiro Agent Spec
            ├── 1. retrieve    → RAG Service :8001        (OpenSearch + Neo4j)
            ├── 2. enrich      → Knowledge Graph           (Neo4j)
            ├── 3. transform   → Transform Service :8003   (atx custom def exec,
            │                                               local fallback)
            ├── 4. generate    → Claude Sonnet
            └── 5. validate    → Eval Service :8002        (DeepEval + LLM-Judge)

Observability: OTel Collector → Prometheus / Jaeger / CloudWatch / Grafana

AWS:  Terraform (ECS Fargate, ALB, OpenSearch, Neo4j+EFS) deployed via Harness
      dev → sit → preprod → prod with SAST/DAST gates and canary releases
      — see docs/deployment-guide.md and docs/architecture.drawio
```

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+
- Java 21+, Maven 3.9+
- [atx CLI](https://docs.aws.amazon.com/transform/latest/userguide/custom.html) (AWS Transform)
- AWS credentials with Transform permissions

### 1. Clone & configure

```bash
git clone https://github.com/varunmaggo/bespoke-ai-factory-spike.git
cd bespoke-ai-factory-spike
cp .env.example .env
# Edit .env — fill in ANTHROPIC_API_KEY, AWS credentials
```

### 2. Start all services

```bash
docker compose up -d
```

Services will be available at:
| Service | URL |
|---|---|
| Spring API | http://localhost:8080 |
| RAG Service | http://localhost:8001 |
| Eval Service | http://localhost:8002 |
| Transform Service | http://localhost:8003 |
| Grafana | http://localhost:3000 |
| Jaeger | http://localhost:16686 |
| Prometheus | http://localhost:9090 |
| OpenSearch | http://localhost:9200 |
| Neo4j | http://localhost:7474 |

### 3. Seed data

```bash
pip install -r requirements.txt
python scripts/seed_data.py --source ./data/sample-docs/
```

### 4. Pilot your AWS Transform definition

```bash
# Interactive session to create/refine a transformation definition
atx custom

# Save as draft for testing
atx custom def save-draft --definition enterprise-context-normaliser

# Execute against sample data
atx custom def exec \
  --definition enterprise-context-normaliser \
  --source-path tests/fixtures/sample-payload.json \
  --output-path /tmp/transformed/ \
  --trust-all-tools

# List all definitions
atx custom def list

# Publish to account registry
atx custom def publish --definition enterprise-context-normaliser
```

### 5. Try the transform service directly

The transform service (:8003) wraps `atx custom def exec` behind an HTTP API and
falls back to a local Python implementation of `enterprise-context-normaliser`
when the atx CLI is not installed — so the demo works without AWS access.

```bash
curl -X POST http://localhost:8003/transform \
  -H "Content-Type: application/json" \
  -d "{\"definition\": \"enterprise-context-normaliser\", \"payload\": $(cat tests/fixtures/sample-payload.json)}"

# List available definitions
curl http://localhost:8003/definitions
```

### 6. Query end-to-end

```bash
curl -X POST http://localhost:8080/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is our Q2 revenue forecast?", "userId": "user-123"}'
```

### 7. Run evaluations

```bash
pytest evals/ -v -m deepeval
```

## AWS Transform Definitions

Three transformation definitions are in `transformation_definitions/`:

| Definition | Pattern | Purpose |
|---|---|---|
| `enterprise-context-normaliser` | Code Refactoring | PII redaction, date normalisation, SAP flattening, context truncation |
| `java-spring-to-spring-ai` | Framework Upgrade | Migrate legacy Spring AI code to Spring AI 1.x |
| `eval-dataset-updater` | Custom | Regenerate synthetic eval test cases on schema change |

## Project Layout

```
.
├── transformation_definitions/     # AWS Transform definition files
│   ├── enterprise-context-normaliser/
│   │   ├── transformation_definition.md
│   │   └── document_references/
│   ├── java-spring-to-spring-ai/
│   └── eval-dataset-updater/
├── kiro/
│   └── specs/
│       └── enterprise-rag-agent.kiro.yaml
├── services/
│   ├── rag/                        # Python RAG microservice (FastAPI :8001)
│   ├── eval/                       # Python eval microservice (FastAPI :8002)
│   └── transform/                  # AWS Transform CLI wrapper service
├── spring/                         # Java Spring microservice (:8080)
├── evals/
│   ├── deepeval/                   # DeepEval metric tests
│   └── llm_judge/                  # LLM-as-judge
├── otel/
│   └── collector-config.yaml
├── tests/
│   └── fixtures/
├── scripts/
│   └── seed_data.py
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── cd.yml
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## AWS Deployment (dev / sit / preprod / prod)

Production deployment runs on **ECS Fargate** provisioned by **Terraform** and
delivered through **Harness** pipelines with SAST/DAST gates and **canary**
releases to preprod/prod:

- [docs/deployment-guide.md](docs/deployment-guide.md) — end-to-end runbook
- [docs/architecture.drawio](docs/architecture.drawio) — diagrams (open in draw.io)
- [infra/terraform/](infra/terraform/) — one stack, four env var-files
- [harness/](harness/) — CI (build + SAST + Trivy), infra (TF plan/approve/apply), CD (canary + ZAP DAST)

## Docs

- [AWS Transform Custom](https://docs.aws.amazon.com/transform/latest/userguide/custom.html)
- [AWS Kiro](https://kiro.dev/)
- [DeepEval](https://docs.confident-ai.com/)
- [Spring AI](https://docs.spring.io/spring-ai/reference/)
- [OpenTelemetry](https://opentelemetry.io/docs/)
