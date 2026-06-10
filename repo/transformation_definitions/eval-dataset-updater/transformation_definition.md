# Eval Dataset Updater

## Objective

Regenerate synthetic evaluation test cases when the underlying enterprise data schema
changes. Given a sample of the new schema and the existing golden eval dataset, produce
an updated dataset that:

1. Preserves all existing valid test cases (no regression)
2. Adds new test cases covering schema additions
3. Marks (but does not delete) test cases that reference removed/renamed fields

## Transformation Steps

### 1. Schema Diff Analysis

Compare `current_schema.json` (input) against `evals/deepeval/golden_dataset.json`
(existing baseline):

- Identify new fields: fields in current schema not covered by existing test cases
- Identify removed fields: fields referenced in test cases no longer in schema
- Identify renamed fields: fields that appear to be renamed (levenshtein distance ≤ 2)

Output a structured diff report.

### 2. Generate New Test Cases

For each new field or schema section:
1. Generate 3-5 realistic question-answer pairs that would require retrieving that field
2. Each test case must include:
   - `input`: a realistic user query
   - `expected_output`: a correct, grounded answer citing the field value
   - `context`: a minimal context chunk containing the field
   - `tags`: ["synthetic", "schema-v{version}", "field:{field_name}"]

Use realistic enterprise language. Avoid generic placeholders like "Sample Company".

### 3. Handle Deprecated Fields

For test cases referencing removed/renamed fields:
- Add `"status": "deprecated"` and `"deprecation_reason": "field renamed to {new_name}"` 
- Do NOT delete — keep for regression tracking
- Log to `_transform_metadata.deprecated_test_cases`

### 4. Validate Dataset Quality

Each new test case must satisfy:
- Expected output length: 50-500 words
- Context contains the exact data needed to answer the question
- No hallucinated data (all values in expected_output must exist in context)
- No PII in generated test cases

### 5. Output Format

Output `golden_dataset_v{version}.json`:

```json
{
  "_metadata": {
    "version": "2.1.0",
    "generated_at": "<ISO-8601>",
    "total_cases": 142,
    "new_cases": 18,
    "deprecated_cases": 3
  },
  "test_cases": [
    {
      "id": "tc-001",
      "status": "active",
      "tags": ["synthetic", "schema-v2", "field:revenue_forecast"],
      "input": "What is the Q2 revenue forecast for APAC?",
      "expected_output": "The Q2 APAC revenue forecast is AUD 4.2M, ...",
      "context": "Q2 APAC forecast: AUD 4,200,000 ..."
    }
  ]
}
```

## Validation

```bash
python -m pytest evals/deepeval/test_dataset_quality.py -v
```

## References

See `document_references/eval-dataset-spec.md` for quality criteria.
