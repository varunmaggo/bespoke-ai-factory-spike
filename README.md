# 🏭 Bespoke Agentic AI Factory

A production-grade, observable, and evaluated AI pipeline stack built on:

- **AWS Kiro** — spec-driven agentic orchestration
- **ATX Transforms** — composable deterministic data transforms
- **Agentic RAG** — multi-hop hybrid retrieval (vector + graph)
- **DeepEval + LLM-as-Judge** — automated quality gates
- **Java Spring Boot** — enterprise microservice integration
- **OpenTelemetry + Prometheus + Grafana** — full observability
- **GitHub Actions** — CI/CD with eval-gated deployments

---

## Repository Structure

```
ai-factory/
├── blog/                         # Companion blog post
│   └── agentic-ai-factory.md
│
├── kiro/
│   └── specs/
│       └── enterprise-rag-agent.kiro.yaml   # Kiro agent spec
│
├── services/
│   ├── rag-service/              # Agentic RAG — FastAPI (Python)
│   │   └── main.py
│   ├── eval-service/             # LLM-as-judge + DeepEval — FastAPI
│   │   └── main.py
│   ├── transform-service/        # ATX pipeline execution — FastAPI
│   │   └── main.py
│   └── spring-service/           # Java Spring Boot API gateway
│       ├── pom.xml
│       └── src/main/
│           ├── java/com/aifactory/
│           │   ├── controller/AIFactoryController.java
│           │   ├── service/AIFactoryService.java
│           │   └── metrics/AIFactoryMetrics.java
│           └── resources/application.yml
│
├── evals/
│   ├── deepeval/
│   │   ├── ci_suite.py           # Fast CI eval suite (~3 min)
│   │   └── rag_evaluator.py      # Full evaluator with all metrics
│   └── llm_judge/
│       └── judge.py              # LLM-as-judge implementation
│
├── atx/
│   ├── sdk/base.py               # ATX Transform base class
│   └── pipelines/
│       └── enterprise_context_normaliser.py
│
├── observability/
│   ├── otel-collector/config.yaml
│   ├── prometheus/
│   │   ├── prometheus.yml
│   │   └── alerts.yaml
│   └── grafana/
│       └── dashboards/
│           └── ai-factory-overview.json
│
├── infrastructure/
│   └── terraform/
│       └── modules/
│           └── ecs-service/main.tf
│
├── tests/
│   ├── unit/
│   └── smoke/
│       └── test_smoke.py
│
├── .github/
│   └── workflows/
│       ├── ci.yml                # PR validation
│       ├── cd.yml                # Deploy to staging → production
│       └── templates/
│           └── eval-template.yml # Reusable eval workflow
│
├── docker-compose.yml
├── requirements.txt
├── requirements-eval.txt
└── requirements-dev.txt
```

---

## Quick Start

### Prerequisites

- Docker & Docker Compose v2+
- Python 3.12+
- Java 21+ (for Spring service)
- An Anthropic API key

### 1. Configure

```bash
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

### 2. Start everything

```bash
docker compose up -d
docker compose ps   # Wait until all services are healthy
```

### 3. Seed the vector store

```bash
python scripts/seed_data.py --source ./data/sample-docs/
```

### 4. Run a query

```bash
curl -X POST http://localhost:8080/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are our Q2 2025 financial results?",
    "userId": "user-123"
  }'
```

### 5. View observability

| Dashboard | URL |
|---|---|
| Grafana | http://localhost:3000 (admin/admin) |
| Jaeger traces | http://localhost:16686 |
| Prometheus | http://localhost:9090 |
| Spring Actuator | http://localhost:8080/actuator |

### 6. Run evaluations

```bash
# Fast CI suite (use locally before pushing)
pytest evals/deepeval/ci_suite.py -v --deepeval

# Full evaluation suite
pytest evals/ -v --deepeval
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | ✅ | Anthropic API key |
| `OPENSEARCH_URL` | ✅ | OpenSearch endpoint |
| `NEO4J_URI` | ✅ | Neo4j bolt URI |
| `NEO4J_PASSWORD` | ✅ | Neo4j password |
| `RAG_MAX_HOPS` | ❌ | Max retrieval hops (default: 3) |
| `RAG_SUFFICIENCY_THRESHOLD` | ❌ | Retrieval sufficiency (default: 0.75) |
| `AI_FACTORY_EVAL_THRESHOLD` | ❌ | Eval pass threshold (default: 0.75) |
| `JUDGE_MODEL` | ❌ | Judge model (default: claude-sonnet-4-20250514) |
| `NUM_JUDGES` | ❌ | Self-consistency judges (default: 1) |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | ❌ | OTEL collector endpoint |

---

## CI/CD

Every PR that touches `services/rag`, `evals/`, or `kiro/` triggers the **eval gate** in addition to standard lint and test jobs. A PR cannot merge unless:

1. All unit tests pass with ≥80% line coverage
2. All DeepEval CI metrics clear their thresholds
3. Docker images build successfully

Deployments to production require **manual approval** via the GitHub Environment protection rule.

---

## Architecture Decisions

### Why Kiro over LangChain?
Kiro gives spec-driven, declarative agent definitions that are auditable, testable, and linked directly to implementation. The YAML spec serves as both documentation and deployment contract.

### Why DeepEval + LLM-as-judge?
DeepEval handles metric computation cheaply; Claude-as-judge handles nuanced quality assessment for complex cases. Running both gives defence in depth.

### Why hybrid RAG (vector + graph + BM25)?
Pure vector search misses exact-match queries (codes, IDs, names). Graph traversal adds relationship context that embeddings cannot capture. BM25 provides a fast keyword baseline that consistently outperforms dense-only retrieval on enterprise terminology.

---

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md). All PRs must pass the full CI suite including the eval gate.

## License

MIT
