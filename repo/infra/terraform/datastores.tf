# ── Amazon OpenSearch (vector + BM25 hybrid retrieval) ───────────────────────

resource "aws_opensearch_domain" "main" {
  domain_name    = local.name
  engine_version = "OpenSearch_2.13"

  cluster_config {
    instance_type          = var.opensearch_instance_type
    instance_count         = var.opensearch_instance_count
    zone_awareness_enabled = var.opensearch_instance_count > 1

    dynamic "zone_awareness_config" {
      for_each = var.opensearch_instance_count > 1 ? [1] : []
      content {
        availability_zone_count = min(var.opensearch_instance_count, var.az_count)
      }
    }
  }

  ebs_options {
    ebs_enabled = true
    volume_size = var.opensearch_volume_size
    volume_type = "gp3"
  }

  vpc_options {
    subnet_ids = slice(
      module.vpc.private_subnets,
      0,
      var.opensearch_instance_count > 1 ? min(var.opensearch_instance_count, var.az_count) : 1
    )
    security_group_ids = [aws_security_group.data.id]
  }

  encrypt_at_rest {
    enabled = true
  }

  node_to_node_encryption {
    enabled = true
  }

  domain_endpoint_options {
    enforce_https       = true
    tls_security_policy = "Policy-Min-TLS-1-2-2019-07"
  }

  access_policies = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { AWS = aws_iam_role.task.arn }
      Action    = "es:ESHttp*"
      Resource  = "arn:aws:es:${var.aws_region}:${data.aws_caller_identity.current.account_id}:domain/${local.name}/*"
    }]
  })
}

# ── Neo4j on ECS with EFS persistence ────────────────────────────────────────

resource "aws_efs_file_system" "neo4j" {
  creation_token = "${local.name}-neo4j"
  encrypted      = true

  lifecycle_policy {
    transition_to_ia = "AFTER_30_DAYS"
  }
}

resource "aws_efs_mount_target" "neo4j" {
  count = var.az_count

  file_system_id  = aws_efs_file_system.neo4j.id
  subnet_id       = module.vpc.private_subnets[count.index]
  security_groups = [aws_security_group.data.id]
}

resource "aws_service_discovery_service" "neo4j" {
  name = "neo4j"

  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.main.id
    dns_records {
      type = "A"
      ttl  = 10
    }
  }
}

resource "aws_cloudwatch_log_group" "neo4j" {
  name              = "/ecs/${local.name}/neo4j"
  retention_in_days = var.log_retention_days
}

resource "aws_ecs_task_definition" "neo4j" {
  family                   = "${local.name}-neo4j"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.neo4j_cpu
  memory                   = var.neo4j_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  volume {
    name = "neo4j-data"
    efs_volume_configuration {
      file_system_id     = aws_efs_file_system.neo4j.id
      transit_encryption = "ENABLED"
    }
  }

  container_definitions = jsonencode([{
    name      = "neo4j"
    image     = "neo4j:5.14"
    essential = true
    portMappings = [
      { containerPort = 7687, protocol = "tcp" },
      { containerPort = 7474, protocol = "tcp" },
    ]
    environment = [
      { name = "NEO4J_PLUGINS", value = "[\"apoc\"]" },
      { name = "NEO4J_dbms_security_procedures_unrestricted", value = "apoc.*" },
    ]
    secrets = [
      # neo4j image expects NEO4J_AUTH=user/password; secret stores "neo4j/<password>"
      { name = "NEO4J_AUTH", valueFrom = aws_secretsmanager_secret.neo4j_auth.arn },
    ]
    mountPoints = [{
      sourceVolume  = "neo4j-data"
      containerPath = "/data"
    }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.neo4j.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "neo4j"
      }
    }
  }])
}

resource "aws_ecs_service" "neo4j" {
  name            = "neo4j"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.neo4j.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = module.vpc.private_subnets
    security_groups = [aws_security_group.services.id]
  }

  service_registries {
    registry_arn = aws_service_discovery_service.neo4j.arn
  }
}
