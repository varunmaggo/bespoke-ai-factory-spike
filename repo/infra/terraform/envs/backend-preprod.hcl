# terraform init -backend-config=envs/backend-preprod.hcl
bucket         = "ai-factory-tfstate-preprod"        # create once per env (or per account)
key            = "ai-factory/preprod/terraform.tfstate"
region         = "ap-southeast-2"
dynamodb_table = "ai-factory-tflock-preprod"
encrypt        = true
