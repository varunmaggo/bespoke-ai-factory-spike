# Secret *containers* only — values are set out-of-band (console / CLI / Harness):
#
#   aws secretsmanager put-secret-value \
#     --secret-id ai-factory/dev/anthropic-api-key --secret-string "sk-ant-..."

resource "aws_secretsmanager_secret" "anthropic" {
  name                    = "${var.project}/${var.environment}/anthropic-api-key"
  recovery_window_in_days = var.deletion_protection ? 30 : 0
}

resource "random_password" "neo4j" {
  length  = 24
  special = false
}

resource "aws_secretsmanager_secret" "neo4j" {
  name                    = "${var.project}/${var.environment}/neo4j-password"
  recovery_window_in_days = var.deletion_protection ? 30 : 0
}

resource "aws_secretsmanager_secret_version" "neo4j" {
  secret_id     = aws_secretsmanager_secret.neo4j.id
  secret_string = random_password.neo4j.result
}

# neo4j container's NEO4J_AUTH format: "user/password"
resource "aws_secretsmanager_secret" "neo4j_auth" {
  name                    = "${var.project}/${var.environment}/neo4j-auth"
  recovery_window_in_days = var.deletion_protection ? 30 : 0
}

resource "aws_secretsmanager_secret_version" "neo4j_auth" {
  secret_id     = aws_secretsmanager_secret.neo4j_auth.id
  secret_string = "neo4j/${random_password.neo4j.result}"
}
