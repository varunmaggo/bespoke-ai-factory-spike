variable "project" {
  description = "Project slug used to name all resources"
  type        = string
  default     = "ai-factory"
}

variable "environment" {
  description = "Environment name: dev | sit | preprod | prod"
  type        = string

  validation {
    condition     = contains(["dev", "sit", "preprod", "prod"], var.environment)
    error_message = "environment must be one of: dev, sit, preprod, prod."
  }
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "ap-southeast-2"
}

# ── Network ───────────────────────────────────────────────────────────────────

variable "vpc_cidr" {
  description = "VPC CIDR (10.10/16 dev, 10.20/16 sit, 10.30/16 preprod, 10.40/16 prod)"
  type        = string
}

variable "az_count" {
  description = "Number of availability zones"
  type        = number
  default     = 2
}

variable "single_nat_gateway" {
  description = "Use one NAT gateway (cheap, lower envs) instead of one per AZ"
  type        = bool
  default     = true
}

# ── ECS services ──────────────────────────────────────────────────────────────

variable "image_tag" {
  description = "Container image tag to deploy (git SHA — set by the Harness pipeline)"
  type        = string
  default     = "latest"
}

variable "services" {
  description = "AI Factory microservices to run on ECS Fargate"
  type = map(object({
    port              = number
    cpu               = number
    memory            = number
    desired_count     = number
    public            = bool # exposed via the public ALB
    health_check_path = string
  }))
  default = {
    spring-service = {
      port              = 8080
      cpu               = 1024
      memory            = 2048
      desired_count     = 1
      public            = true
      health_check_path = "/actuator/health"
    }
    rag-service = {
      port              = 8001
      cpu               = 2048
      memory            = 8192 # embedding model is memory-hungry
      desired_count     = 1
      public            = false
      health_check_path = "/health"
    }
    eval-service = {
      port              = 8002
      cpu               = 1024
      memory            = 2048
      desired_count     = 1
      public            = false
      health_check_path = "/health"
    }
    transform-service = {
      port              = 8003
      cpu               = 512
      memory            = 1024
      desired_count     = 1
      public            = false
      health_check_path = "/health"
    }
  }
}

variable "certificate_arn" {
  description = "Optional ACM certificate ARN for HTTPS on the public ALB (empty = HTTP only)"
  type        = string
  default     = ""
}

# ── Data stores ───────────────────────────────────────────────────────────────

variable "opensearch_instance_type" {
  description = "OpenSearch data node instance type"
  type        = string
  default     = "t3.small.search"
}

variable "opensearch_instance_count" {
  description = "OpenSearch data node count"
  type        = number
  default     = 1
}

variable "opensearch_volume_size" {
  description = "EBS volume size per OpenSearch node (GiB)"
  type        = number
  default     = 20
}

variable "neo4j_cpu" {
  description = "Neo4j task CPU units"
  type        = number
  default     = 1024
}

variable "neo4j_memory" {
  description = "Neo4j task memory (MiB)"
  type        = number
  default     = 4096
}

# ── Safety / retention ────────────────────────────────────────────────────────

variable "deletion_protection" {
  description = "Protect stateful resources from destroy (ON for preprod/prod)"
  type        = bool
  default     = false
}

variable "log_retention_days" {
  description = "CloudWatch log retention"
  type        = number
  default     = 30
}
