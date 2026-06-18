locals {
  public_services = { for k, v in var.services : k => v if v.public }
}

resource "aws_lb" "public" {
  name                       = local.name
  load_balancer_type         = "application"
  security_groups            = [aws_security_group.alb.id]
  subnets                    = module.vpc.public_subnets
  enable_deletion_protection = var.deletion_protection
}

resource "aws_lb_target_group" "public" {
  for_each = local.public_services

  name        = "${local.name}-${each.key}"
  port        = each.value.port
  protocol    = "HTTP"
  vpc_id      = module.vpc.vpc_id
  target_type = "ip"

  health_check {
    path                = each.value.health_check_path
    healthy_threshold   = 2
    unhealthy_threshold = 5
    interval            = 30
    timeout             = 10
    matcher             = "200"
  }

  deregistration_delay = 30
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.public.arn
  port              = 80
  protocol          = "HTTP"

  # Redirect to HTTPS when a certificate is configured, otherwise serve HTTP
  dynamic "default_action" {
    for_each = var.certificate_arn == "" ? [1] : []
    content {
      type             = "forward"
      target_group_arn = aws_lb_target_group.public["spring-service"].arn
    }
  }

  dynamic "default_action" {
    for_each = var.certificate_arn != "" ? [1] : []
    content {
      type = "redirect"
      redirect {
        port        = "443"
        protocol    = "HTTPS"
        status_code = "HTTP_301"
      }
    }
  }
}

resource "aws_lb_listener" "https" {
  count = var.certificate_arn != "" ? 1 : 0

  load_balancer_arn = aws_lb.public.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.public["spring-service"].arn
  }
}

# ── Path-based routing for additional public services ────────────────────────
# Services that declare path_patterns (e.g. payment-gateway → /api/v1/payments/*)
# get a listener rule on whichever listener actually serves traffic.

locals {
  routed_services = { for k, v in local.public_services : k => v if length(v.path_patterns) > 0 }
}

resource "aws_lb_listener_rule" "path" {
  for_each = local.routed_services

  # Attach to HTTPS when a certificate exists (HTTP only redirects then),
  # otherwise to the HTTP listener.
  listener_arn = var.certificate_arn != "" ? aws_lb_listener.https[0].arn : aws_lb_listener.http.arn
  priority     = 100 + index(sort(keys(local.routed_services)), each.key)

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.public[each.key].arn
  }

  condition {
    path_pattern {
      values = each.value.path_patterns
    }
  }
}
