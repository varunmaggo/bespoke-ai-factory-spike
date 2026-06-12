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

output "alerts_topic_arn" {
  description = "SNS topic receiving CloudWatch alarms (subscribe via alerts_email var or manually)"
  value       = aws_sns_topic.alerts.arn
}

output "cloudwatch_dashboard" {
  description = "CloudWatch dashboard name (ALB + ECS view of the Grafana signals)"
  value       = aws_cloudwatch_dashboard.main.dashboard_name
}

output "payment_gateway_url" {
  description = "Public payment gateway endpoint (path-routed on the shared ALB)"
  value       = "http://${aws_lb.public.dns_name}/api/v1/payments"
}
