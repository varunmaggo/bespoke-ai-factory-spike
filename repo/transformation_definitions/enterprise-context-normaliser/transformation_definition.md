# Enterprise Context Normaliser

## Objective

Prepare enterprise data payloads for LLM context windows by applying the following
transformations in order. Each transformation must be idempotent and auditable.

The output must always be valid JSON with the same top-level structure as the input,
plus a `_transform_metadata` key documenting what was changed.

## Transformation Steps

### 1. PII Redaction

Scan ALL string values recursively (including nested objects and arrays) for the
following field names (case-insensitive) and replace their values with `"[REDACTED]"`:

- ssn, social_security_number, national_id
- credit_card, card_number, cvv, card_expiry
- password, hashed_password, api_key, secret, token, access_token, refresh_token
- dob, date_of_birth, birth_date
- phone, phone_number, mobile, fax
- email, email_address

Do NOT redact:
- Field names themselves (only their values)
- Numeric fields (e.g., age: 32 stays as-is)
- Fields whose names contain these strings but in a different context
  (e.g., "phone_model" should NOT be redacted)

Record each redacted field path in `_transform_metadata.pii_redacted`.

### 2. Date Normalisation

Convert all date string values to ISO-8601 format (`YYYY-MM-DD`). Recognise and
normalise the following common formats:

- `DD/MM/YYYY` (e.g., 25/12/2024 → 2024-12-25)
- `MM/DD/YYYY` (e.g., 12/25/2024 → 2024-12-25)
- `YYYYMMDD` (e.g., 20241225 → 2024-12-25)
- `DD-Mon-YYYY` (e.g., 25-Dec-2024 → 2024-12-25)
- `Month DD, YYYY` (e.g., December 25, 2024 → 2024-12-25)
- `DD.MM.YYYY` (e.g., 25.12.2024 → 2024-12-25)
- Unix timestamps (integer seconds since epoch → ISO datetime)

If a string looks like a date but cannot be parsed, leave it unchanged and log to
`_transform_metadata.date_parse_failures`.

### 3. SAP Payload Flattening

SAP OData response payloads arrive deeply nested under keys like `d.results[]`.
Flatten these structures:

1. Unwrap `d.results` arrays to a flat list at the payload root
2. For each object in the array, flatten nested keys using dot-notation
   (e.g., `"Address": {"Street": "Main St"}` → `"address_street": "Main St"`)
3. Convert ALL keys from PascalCase / CamelCase to snake_case
4. Remove SAP internal metadata fields (keys starting with `__` or `@odata`)

Example input:
```json
{"d": {"results": [{"MaterialNumber": "MAT001", "Description": {"Text": "Widget"}}]}}
```
Example output:
```json
[{"material_number": "MAT001", "description_text": "Widget"}]
```

Only apply SAP flattening if the payload contains a top-level `d.results` key.

### 4. Context Window Truncation

After all other transformations, if the total estimated token count exceeds the
limit specified in the request (default: 80,000 tokens using cl100k_base encoding):

1. Sort chunks/items by `score` or `relevance_score` field descending
2. Iteratively drop the lowest-scoring chunks until under the token budget
3. Set `_transform_metadata.truncated = true`
4. Set `_transform_metadata.chunks_dropped` = number of chunks removed
5. Set `_transform_metadata.original_chunk_count` = original count

If no score field is present, truncate from the end of the array.

## Output Format

The output must include `_transform_metadata`:

```json
{
  "_transform_metadata": {
    "version": "1.2.0",
    "applied_at": "<ISO-8601 timestamp>",
    "pii_redacted": ["user.email", "user.phone"],
    "dates_normalised": 3,
    "date_parse_failures": [],
    "sap_flattened": false,
    "truncated": false,
    "chunks_dropped": 0,
    "original_chunk_count": 12
  },
  ...transformed_payload...
}
```

## Validation

Run the test suite to validate this definition against known inputs:

```bash
python -m pytest tests/unit/test_transform_logic.py -v --tb=short
```

## References

See `document_references/enterprise-data-schema.md` for the canonical field definitions
and examples of each enterprise data source format.
