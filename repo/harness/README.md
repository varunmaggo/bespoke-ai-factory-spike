# Harness pipelines

Importable Harness NextGen pipeline definitions. Replace the `<...>`
placeholders after import.

| File | Pipeline | Purpose |
|---|---|---|
| [pipelines/ci-build-and-scan.yaml](pipelines/ci-build-and-scan.yaml) | `ai-factory-ci` | Unit tests → SAST (Semgrep, Gitleaks, OWASP) → build 4 images → Trivy scan → push ECR |
| [pipelines/infra-terraform.yaml](pipelines/infra-terraform.yaml) | `ai-factory-infra` | Terraform plan → approval → apply for one env (runtime input) |
| [pipelines/cd-deploy.yaml](pipelines/cd-deploy.yaml) | `ai-factory-cd` | dev (rolling) → sit (rolling) → DAST (ZAP) → preprod (canary) → prod (canary) |

## Prerequisites

1. **Connectors**
   - `<GITHUB_CONNECTOR>` — GitHub connector to `varunmaggo/bespoke-ai-factory-spike`
   - `<AWS_CONNECTOR>` — AWS connector per environment account (IAM role with
     ECR push, ECS deploy, CloudWatch read, Terraform-level permissions)
2. **Modules enabled**: CI, CD, STO (Security Testing Orchestration for the
   Semgrep/Gitleaks/OWASP/Trivy/ZAP steps).
3. **CD entities** (Project → Environments / Services):
   - Environments `dev`, `sit`, `preprod`, `prod`, each with an ECS
     Infrastructure Definition (`ecs_dev` … `ecs_prod`) pointing at the
     Terraform-created cluster `ai-factory-<env>` and the env's AWS connector.
   - Environment variables used by the pipeline: `alb_dns_name`,
     `alb_arn_suffix` (from the Terraform outputs).
   - Service `ai_factory_spring` (ECS deployment type) with an ECR artifact
     source `ecr_image` for `ai-factory/spring-service` and an ECS task
     definition / service definition manifest. Clone it for the rag/eval/
     transform services (or convert the deploy stages into a stage template
     and loop with a matrix strategy).
4. **User groups**: `<PLATFORM_APPROVERS_GROUP>` (infra plan review) and
   `<RELEASE_APPROVERS_GROUP>` (preprod single approval, prod two approvals).

## Wiring

- A trigger on `ai-factory-ci` (push to `main`) chains into `ai-factory-cd`
  with `image_tag = <+codebase.commitSha>`.
- `ai-factory-infra` is run on demand (or triggered by changes under
  `repo/infra/terraform/**`), promoting the change dev → sit → preprod → prod
  with a plan approval each time.
- SAST gates fail the build on **high** severity; Trivy and OWASP dependency
  check fail on **critical**; ZAP DAST fails promotion past SIT on **high**.
