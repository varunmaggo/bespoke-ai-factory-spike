# ── Alerting & dashboards in AWS ─────────────────────────────────────────────
# Local/dev runs alert through Prometheus (otel/prometheus-alerts.yml); in AWS
# the equivalent signals come from ALB/ECS CloudWatch metrics plus the ADOT
# sidecar's EMF metrics, alarmed here and fanned out via SNS.

resource "aws_sns_topic" "alerts" {
  name = "${local.name}-alerts"
}

resource "aws_sns_topic_subscription" "alerts_email" {
  count = var.alerts_email != "" ? 1 : 0

  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alerts_email
}

# ── ALB-level alarms per public service ──────────────────────────────────────

resource "aws_cloudwatch_metric_alarm" "alb_5xx" {
  for_each = local.public_services

  alarm_name          = "${local.name}-${each.key}-5xx-rate"
  alarm_description   = "${each.key}: target 5xx responses above threshold"
  namespace           = "AWS/ApplicationELB"
  metric_name         = "HTTPCode_Target_5XX_Count"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 2
  threshold           = 10
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    LoadBalancer = aws_lb.public.arn_suffix
    TargetGroup  = aws_lb_target_group.public[each.key].arn_suffix
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "alb_p95_latency" {
  for_each = local.public_services

  alarm_name          = "${local.name}-${each.key}-p95-latency"
  alarm_description   = "${each.key}: p95 response time above 2s for 10 minutes"
  namespace           = "AWS/ApplicationELB"
  metric_name         = "TargetResponseTime"
  extended_statistic  = "p95"
  period              = 300
  evaluation_periods  = 2
  threshold           = 2
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    LoadBalancer = aws_lb.public.arn_suffix
    TargetGroup  = aws_lb_target_group.public[each.key].arn_suffix
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "alb_unhealthy_hosts" {
  for_each = local.public_services

  alarm_name          = "${local.name}-${each.key}-unhealthy-hosts"
  alarm_description   = "${each.key}: at least one target failing ALB health checks"
  namespace           = "AWS/ApplicationELB"
  metric_name         = "UnHealthyHostCount"
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 3
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    LoadBalancer = aws_lb.public.arn_suffix
    TargetGroup  = aws_lb_target_group.public[each.key].arn_suffix
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
}

# ── ECS task health per service ──────────────────────────────────────────────

resource "aws_cloudwatch_metric_alarm" "ecs_cpu" {
  for_each = var.services

  alarm_name          = "${local.name}-${each.key}-cpu-high"
  alarm_description   = "${each.key}: average CPU above 85% for 15 minutes"
  namespace           = "AWS/ECS"
  metric_name         = "CPUUtilization"
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 3
  threshold           = 85
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ClusterName = aws_ecs_cluster.main.name
    ServiceName = each.key
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "ecs_memory" {
  for_each = var.services

  alarm_name          = "${local.name}-${each.key}-memory-high"
  alarm_description   = "${each.key}: average memory above 90% for 15 minutes"
  namespace           = "AWS/ECS"
  metric_name         = "MemoryUtilization"
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 3
  threshold           = 90
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ClusterName = aws_ecs_cluster.main.name
    ServiceName = each.key
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
}

# ── Business alarms from application logs (trace-correlated JSON logs) ──────
# The payment gateway logs every acquirer-unavailable outcome; a metric filter
# turns that into a CloudWatch metric mirroring payments_acquirer_unavailable_total.

resource "aws_cloudwatch_log_metric_filter" "acquirer_unavailable" {
  count = contains(keys(var.services), "payment-gateway") ? 1 : 0

  name           = "${local.name}-acquirer-unavailable"
  log_group_name = aws_cloudwatch_log_group.service["payment-gateway"].name
  pattern        = "\"Acquirer circuit open\""

  metric_transformation {
    name          = "AcquirerUnavailable"
    namespace     = "${var.project}/payments"
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_metric_alarm" "acquirer_unavailable" {
  count = contains(keys(var.services), "payment-gateway") ? 1 : 0

  alarm_name          = "${local.name}-acquirer-unavailable-burst"
  alarm_description   = "Payment gateway: >10 acquirer-unavailable failures in 5 minutes (circuit likely open)"
  namespace           = "${var.project}/payments"
  metric_name         = "AcquirerUnavailable"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 10
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
}

# ── CloudWatch dashboard (ALB + ECS view of the same signals as Grafana) ────

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = local.name

  dashboard_body = jsonencode({
    widgets = concat(
      [
        {
          type   = "metric"
          x      = 0
          y      = 0
          width  = 12
          height = 6
          properties = {
            title  = "ALB requests / 5xx"
            region = var.aws_region
            stat   = "Sum"
            period = 300
            metrics = [
              ["AWS/ApplicationELB", "RequestCount", "LoadBalancer", aws_lb.public.arn_suffix],
              ["AWS/ApplicationELB", "HTTPCode_Target_5XX_Count", "LoadBalancer", aws_lb.public.arn_suffix]
            ]
          }
        },
        {
          type   = "metric"
          x      = 12
          y      = 0
          width  = 12
          height = 6
          properties = {
            title  = "ALB p95 latency (s)"
            region = var.aws_region
            stat   = "p95"
            period = 300
            metrics = [
              for k, v in local.public_services :
              ["AWS/ApplicationELB", "TargetResponseTime", "LoadBalancer", aws_lb.public.arn_suffix, "TargetGroup", aws_lb_target_group.public[k].arn_suffix, { label = k }]
            ]
          }
        }
      ],
      [
        {
          type   = "metric"
          x      = 0
          y      = 6
          width  = 12
          height = 6
          properties = {
            title  = "ECS CPU by service (%)"
            region = var.aws_region
            stat   = "Average"
            period = 300
            metrics = [
              for k, v in var.services :
              ["AWS/ECS", "CPUUtilization", "ClusterName", aws_ecs_cluster.main.name, "ServiceName", k, { label = k }]
            ]
          }
        },
        {
          type   = "metric"
          x      = 12
          y      = 6
          width  = 12
          height = 6
          properties = {
            title  = "ECS memory by service (%)"
            region = var.aws_region
            stat   = "Average"
            period = 300
            metrics = [
              for k, v in var.services :
              ["AWS/ECS", "MemoryUtilization", "ClusterName", aws_ecs_cluster.main.name, "ServiceName", k, { label = k }]
            ]
          }
        }
      ]
    )
  })
}
