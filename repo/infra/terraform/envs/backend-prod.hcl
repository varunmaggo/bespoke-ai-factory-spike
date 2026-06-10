# terraform init -backend-config=envs/backend-prod.hcl
bucket         = "ai-factory-tfstate-prod"        # create once per env (or per account)
key            = "ai-factory/prod/terraform.tfstate"
region         = "ap-southeast-2"
dynamodb_table = "ai-factory-tflock-prod"
encrypt        = true
