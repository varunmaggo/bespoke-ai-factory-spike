# ── Cluster + service discovery ───────────────────────────────────────────────

resource "aws_ecs_cluster" "main" {
  name = local.name

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_service_discovery_private_dns_namespace" "main" {
  name = "${var.project}.local"
  vpc  = module.vpc.vpc_id
}

resource "aws_service_discovery_service" "service" {
  for_each = var.services

  name = each.key

  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.main.id
    dns_records {
      type = "A"
      ttl  = 10
    }
  }
}

# ── IAM ───────────────────────────────────────────────────────────────────────

data "aws_iam_policy_document" "ecs_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "execution" {
  name               = "${local.name}-task-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
}

resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "execution_secrets" {
  name = "read-app-secrets"
  role = aws_iam_role.execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = [aws_secretsmanager_secret.anthropic.arn, aws_secretsmanager_secret.neo4j.arn]
    }]
  })
}

resource "aws_iam_role" "task" {
  name               = "${local.name}-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
}

resource "aws_iam_role_policy" "task" {
  name = "app-runtime"
  role = aws_iam_role.task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["es:ESHttp*"]
        Resource = "${aws_opensearch_domain.main.arn}/*"
      },
      {
        Effect   = "Allow"
        Action   = ["xray:PutTraceSegments", "xray:PutTelemetryRecords"]
        Resource = "*"
      }
    ]
  })
}

# ── Logs / task definitions / services ───────────────────────────────────────

resource "aws_cloudwatch_log_group" "service" {
  for_each = var.services

  name              = "/ecs/${local.name}/${each.key}"
  retention_in_days = var.log_retention_days
}

locals {
  service_urls = {
    RAG_SERVICE_URL       = "http://rag-service.${var.project}.local:8001"
    EVAL_SERVICE_URL      = "http://eval-service.${var.project}.local:8002"
    TRANSFORM_SERVICE_URL = "http://transform-service.${var.project}.local:8003"
  }

  common_env = merge(local.service_urls, {
    AWS_REGION                  = var.aws_region
    OPENSEARCH_HOST             = aws_opensearch_domain.main.endpoint
    OPENSEARCH_PORT             = "443"
    OPENSEARCH_USE_AWS          = "true"
    NEO4J_URI                   = "bolt://neo4j.${var.project}.local:7687"
    NEO4J_USER                  = "neo4j"
    OTEL_EXPORTER_OTLP_ENDPOINT = "http://localhost:4317" # ADOT sidecar
  })
}

resource "aws_ecs_task_definition" "service" {
  for_each = var.services

  family                   = "${local.name}-${each.key}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = each.value.cpu
  memory                   = each.value.memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([
    {
      name      = each.key
      image     = "${local.ecr_registry}/${var.project}/${each.key}:${var.image_tag}"
      essential = true
      portMappings = [{
        containerPort = each.value.port
        protocol      = "tcp"
      }]
      environment = [
        for k, v in merge(local.common_env, { OTEL_SERVICE_NAME = each.key }) :
        { name = k, value = v }
      ]
      secrets = [
        { name = "ANTHROPIC_API_KEY", valueFrom = aws_secretsmanager_secret.anthropic.arn },
        { name = "NEO4J_PASSWORD", valueFrom = aws_secretsmanager_secret.neo4j.arn },
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.service[each.key].name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "app"
        }
      }
    },
    {
      name      = "adot-collector"
      image     = "public.ecr.aws/aws-observability/aws-otel-collector:latest"
      essential = false
      command   = ["--config=/etc/ecs/ecs-default-config.yaml"]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.service[each.key].name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "otel"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "service" {
  for_each = var.services

  name            = each.key
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.service[each.key].arn
  desired_count   = each.value.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = module.vpc.private_subnets
    security_groups = [aws_security_group.services.id]
  }

  service_registries {
    registry_arn = aws_service_discovery_service.service[each.key].arn
  }

  dynamic "load_balancer" {
    for_each = each.value.public ? [1] : []
    content {
      target_group_arn = aws_lb_target_group.public[each.key].arn
      container_name   = each.key
      container_port   = each.value.port
    }
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  # Harness owns task definition revisions + desired counts during deploys
  lifecycle {
    ignore_changes = [task_definition, desired_count]
  }
}
