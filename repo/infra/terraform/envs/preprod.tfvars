environment        = "preprod"
aws_region         = "ap-southeast-2"
vpc_cidr           = "10.30.0.0/16"
az_count           = 3
single_nat_gateway = false

opensearch_instance_type  = "r6g.large.search"
opensearch_instance_count = 2
opensearch_volume_size    = 50

deletion_protection = true
log_retention_days  = 90

services = {
  spring-service = {
    port              = 8080
    cpu               = 1024
    memory            = 2048
    desired_count     = 2
    public            = true
    health_check_path = "/actuator/health"
  }
  rag-service = {
    port              = 8001
    cpu               = 2048
    memory            = 8192
    desired_count     = 2
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
    cpu               = 512
    memory            = 1024
    desired_count     = 1
    public            = false
    health_check_path = "/health"
  }
}
