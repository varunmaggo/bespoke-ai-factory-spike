environment        = "dev"
aws_region         = "ap-southeast-2"
vpc_cidr           = "10.10.0.0/16"
az_count           = 2
single_nat_gateway = true

opensearch_instance_type  = "t3.small.search"
opensearch_instance_count = 1
opensearch_volume_size    = 20

deletion_protection = false
log_retention_days  = 14
