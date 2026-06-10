# terraform init -backend-config=envs/backend-dev.hcl
bucket         = "ai-factory-tfstate-dev"        # create once per env (or per account)
key            = "ai-factory/dev/terraform.tfstate"
region         = "ap-southeast-2"
dynamodb_table = "ai-factory-tflock-dev"
encrypt        = true
