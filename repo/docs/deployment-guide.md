# AI Factory — AWS Deployment Guide

How to stand up the full AI Factory platform in AWS from scratch across four
environments (**dev → sit → preprod → prod**) using **Terraform** provisioned
through **Harness** pipelines, with **canary deployments** and **SAST/DAST**
gates.

Open [architecture.drawio](architecture.drawio) in [draw.io](https://app.diagrams.net)
for the diagrams referenced here (3 pages: AWS architecture, Harness CI/CD,
environment promotion).

## What gets built per environment

| Component | AWS resource |
|---|---|
| Network | VPC (10.x.0.0/16), public + private subnets, NAT |
| Compute | ECS Fargate cluster: spring (:8080), payment-gateway (:9081), rag (:8001), eval (:8002), transform (:8003) |
| Service discovery | Cloud Map private namespace `ai-factory.local` |
| Entry point | Public ALB → spring-service; `/api/v1/payments/*` path-routed to payment-gateway (HTTPS when `certificate_arn` is set) |
| Vector search | Amazon OpenSearch domain (k-NN + BM25) |
| Knowledge graph | Neo4j 5 on ECS with EFS persistence |
| Secrets | Secrets Manager: `ai-factory/<env>/anthropic-api-key`, Neo4j password |
| Images | ECR repos `ai-factory/<service>` (created with the dev stack) |
| Observability | CloudWatch logs/metrics, Container Insights, ADOT sidecar, X-Ray |
| Alerting | SNS topic + CloudWatch alarms (ALB 5xx/p95/unhealthy hosts, ECS CPU/mem, acquirer-outage log metric) and a CloudWatch dashboard — `infra/terraform/observability.tf`; subscribe via `alerts_email` |

Environment sizing lives entirely in [infra/terraform/envs/](../infra/terraform/envs/):
dev/sit are small and single-NAT; preprod/prod are 3-AZ, NAT-per-AZ, larger
OpenSearch, multiple tasks per service, and deletion protection on.

## One-time bootstrap (per environment / account)

```bash
ENV=dev   # then sit, preprod, prod

# 1. Terraform state backend
aws s3 mb s3://ai-factory-tfstate-$ENV --region ap-southeast-2
aws dynamodb create-table --table-name ai-factory-tflock-$ENV \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST --region ap-southeast-2

# 2. Provision (locally for bootstrap; afterwards always via the Harness infra pipeline)
cd infra/terraform
terraform init -backend-config=envs/backend-$ENV.hcl
terraform apply -var-file=envs/$ENV.tfvars

# 3. Set the Anthropic API key (Terraform creates the secret container only)
aws secretsmanager put-secret-value \
  --secret-id ai-factory/$ENV/anthropic-api-key \
  --secret-string "sk-ant-..."
```

Recommended: one AWS account per environment under AWS Organizations, with a
Harness AWS connector (IAM role) per account.

## Harness setup

Import the three pipelines from [harness/pipelines/](../harness/pipelines/)
(see [harness/README.md](../harness/README.md) for connector prerequisites):

1. **`ai-factory-ci`** — on push: unit tests (pytest + mvn) → **SAST**
   (Semgrep + Gitleaks + OWASP dependency check, fail on high) → build 4
   images → **Trivy** container scan (fail on critical) → push to ECR tagged
   with the git SHA.
2. **`ai-factory-infra`** — `terraform plan` (env tfvars + backend selected by
   runtime input) → human plan review → `terraform apply`, with
   `TerraformRollback` on failure.
3. **`ai-factory-cd`** — promotes one image tag:

   | Stage | Strategy | Gate to proceed |
   |---|---|---|
   | dev | ECS rolling | smoke tests (`/actuator/health`) |
   | sit | ECS rolling | **DAST**: OWASP ZAP against the SIT ALB (fail on high) |
   | preprod | **ECS canary** | approval, then canary 25% → 10-min verify → 100% |
   | prod | **ECS canary** | 2-person approval, same canary flow, auto-rollback |

### Canary mechanics

`EcsCanaryDeploy` starts a temporary `<service>-Canary` task set (25% of
desired count) registered behind the same target group. A verification window
watches ALB 5xx counts in CloudWatch (swap the ShellScript for a Harness CV
`Verify` step once a health source is connected). On pass: canary deleted and
a rolling deploy takes the service to 100% on the new revision. On fail: canary
deleted and `EcsRollingRollback` restores the previous revision.

Terraform deliberately sets `ignore_changes = [task_definition, desired_count]`
on ECS services — Harness owns deploy-time changes; Terraform owns everything
else.

## End-to-end flow

```text
git push → ai-factory-ci (tests, SAST, build, Trivy, ECR)
        → ai-factory-cd  (dev → smoke → sit → DAST → ✋ → preprod canary → ✋✋ → prod canary)
infra change? → ai-factory-infra per env (plan → ✋ → apply), dev first, prod last
```

## Costs to watch

- OpenSearch is the biggest fixed cost (prod: 3 × r6g.large.search).
- rag-service tasks are memory-heavy (embedding model); prod uses 16 GiB tasks.
- Lower envs use a single NAT gateway; prod/preprod pay for one per AZ.
- Dev/sit can be torn down overnight: `terraform destroy -var-file=envs/dev.tfvars`
  (blocked in preprod/prod by `deletion_protection`).
