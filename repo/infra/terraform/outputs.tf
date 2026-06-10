output "alb_dns_name" {
  description = "Public entry point (spring-service)"
  value       = aws_lb.public.dns_name
}

output "ecs_cluster_name" {
  description = "ECS cluster — used by the Harness CD pipeline"
  value       = aws_ecs_cluster.main.name
}

output "ecr_repository_urls" {
  description = "ECR repositories (created in the dev stack only)"
  value       = { for k, r in aws_ecr_repository.service : k => r.repository_url }
}

output "opensearch_endpoint" {
  value = aws_opensearch_domain.main.endpoint
}

output "service_discovery_namespace" {
  value = aws_service_discovery_private_dns_namespace.main.name
}

output "private_subnet_ids" {
  value = module.vpc.private_subnets
}

output "services_security_group_id" {
  value = aws_security_group.services.id
}
