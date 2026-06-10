# Partial backend configuration — supply the per-environment settings at init:
#
#   terraform init -backend-config=envs/backend-dev.hcl
#
# State is isolated per environment (separate key, ideally separate account).
terraform {
  backend "s3" {}
}
