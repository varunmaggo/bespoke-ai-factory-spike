# AI Factory — Sample Document

## Q2 Revenue Forecast

The APAC region Q2 2024 revenue forecast is AUD 4.2M.
Pipeline is confirmed as of June 1, 2024.
Regional breakdown: Australia 60%, New Zealand 20%, Singapore 20%.

Key assumptions:
- Pipeline conversion rate: 35%
- Average deal size: AUD 42,000
- Sales cycle: 6 weeks average

## Strategic Priorities (H2 2024)

1. Expand AI Factory to cover document processing workflows
2. Onboard 3 additional enterprise customers to the RAG platform
3. Reduce average eval latency from 4s to under 2s
4. Publish AWS Transform definitions to the account registry

## Architecture Decision: AWS Transform vs Custom Middleware

After evaluating custom Python middleware pipelines against AWS Transform Custom,
the team selected AWS Transform for the following reasons:

- Continual learning automatically improves transformation quality over time
- Natural language definitions reduce maintenance burden by ~60%
- Native AWS integration with IAM, CloudWatch, and ECR
- Knowledge items provide auditability for every transformation applied
