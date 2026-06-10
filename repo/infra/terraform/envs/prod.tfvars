environment        = "prod"
aws_region         = "ap-southeast-2"
vpc_cidr           = "10.40.0.0/16"
az_count           = 3
single_nat_gateway = false

opensearch_instance_type  = "r6g.large.search"
opensearch_instance_count = 3
opensearch_volume_size    = 100

deletion_protection = true
log_retention_days  = 365

# certificate_arn = "arn:aws:acm:ap-southeast-2:ACCOUNT_ID:certificate/..."

services = {
  spring-service = {
    port              = 8080
    cpu               = 2048
    memory            = 4096
    desired_count     = 3
    public            = true
    health_check_path = "/actuator/health"
  }
  rag-service = {
    port              = 8001
    cpu               = 4096
    memory            = 16384
    desired_count     = 3
    public            = false
    health_check_path = "/health"
  }
  eval-service = {
    port              = 8002
    cpu               = 1024
    memory            = 2048
    desired_count     = 2
    public            = false
    health_check_path = "/health"
  }
  transform-service = {
    port              = 8003
    cpu               = 1024
    memory            = 2048
    desired_count     = 2
    public            = false
    health_check_path = "/health"
  }
}
