# terraform init -backend-config=envs/backend-sit.hcl
bucket         = "ai-factory-tfstate-sit"        # create once per env (or per account)
key            = "ai-factory/sit/terraform.tfstate"
region         = "ap-southeast-2"
dynamodb_table = "ai-factory-tflock-sit"
encrypt        = true
