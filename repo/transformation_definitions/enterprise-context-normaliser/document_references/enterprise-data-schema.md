# Enterprise Data Schema Reference

## SAP OData Response Format

SAP systems return data wrapped in `d.results`:

```json
{
  "d": {
    "results": [
      {
        "__metadata": {"type": "SalesOrderItem"},
        "SalesOrderNumber": "SO-20241201-001",
        "CustomerEmail": "john.doe@example.com",
        "OrderDate": "01/12/2024",
        "MaterialNumber": "MAT-789",
        "Quantity": 5,
        "Address": {
          "Street": "123 Main St",
          "City": "Sydney"
        }
      }
    ]
  }
}
```

After normalisation:
```json
{
  "_transform_metadata": { "sap_flattened": true, "pii_redacted": ["customer_email"] },
  "data": [
    {
      "sales_order_number": "SO-20241201-001",
      "customer_email": "[REDACTED]",
      "order_date": "2024-12-01",
      "material_number": "MAT-789",
      "quantity": 5,
      "address_street": "123 Main St",
      "address_city": "Sydney"
    }
  ]
}
```

## Salesforce Response Format

Salesforce returns paginated records with `records[]` arrays. No special flattening
is needed — only PII redaction and date normalisation apply.

## Standard Document Chunk Format

RAG chunks arrive as:
```json
{
  "chunks": [
    {
      "content": "...",
      "score": 0.87,
      "metadata": {
        "document_id": "DOC-123",
        "source": "s3://bucket/file.pdf",
        "created_at": "20240115"
      }
    }
  ]
}
```
