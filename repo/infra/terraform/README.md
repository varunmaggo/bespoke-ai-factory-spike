# Terraform — AI Factory AWS environments

One reusable stack, four environments selected by var-file. Normally executed
by the `ai-factory-infra` Harness pipeline; run locally only for bootstrap.

```bash
terraform init -backend-config=envs/backend-dev.hcl
terraform plan  -var-file=envs/dev.tfvars
terraform apply -var-file=envs/dev.tfvars
```

Switching environments = re-init with the other backend file (state is fully
isolated per env):

```bash
terraform init -reconfigure -backend-config=envs/backend-prod.hcl
terraform apply -var-file=envs/prod.tfvars
```

| File | Contents |
|---|---|
| `network.tf` | VPC (terraform-aws-modules/vpc), subnets, NAT, security groups |
| `ecs.tf` | Fargate cluster, Cloud Map, IAM, task defs + services (4 apps, ADOT sidecar) |
| `alb.tf` | Public ALB → spring-service, optional HTTPS via `certificate_arn` |
| `datastores.tf` | OpenSearch domain, Neo4j on ECS + EFS |
| `ecr.tf` | ECR repos (dev stack only — shared across envs) |
| `secrets.tf` | Secrets Manager containers; Neo4j password generated |
| `envs/*.tfvars` | Per-environment sizing (dev / sit / preprod / prod) |
| `envs/backend-*.hcl` | Per-environment S3 state config |

Notes:

- `image_tag` defaults to `latest`; the Harness pipelines pass the git SHA.
- ECS services ignore `task_definition`/`desired_count` drift — Harness owns
  deployments, Terraform owns infrastructure.
- `deletion_protection = true` (preprod/prod) enables ALB delete protection
  and 30-day secret recovery; treat it as the "don't destroy this env" flag.
- Set the Anthropic key after the first apply:
  `aws secretsmanager put-secret-value --secret-id ai-factory/<env>/anthropic-api-key --secret-string "sk-ant-..."`
