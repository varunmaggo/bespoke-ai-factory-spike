"""
tests/unit/test_transform_logic.py — Unit tests for the local
enterprise-context-normaliser implementation (services/transform/normaliser.py).
No external services required.
"""
import pytest

from services.transform.normaliser import (
    VERSION,
    _flatten_sap,
    _to_snake_case,
    _try_parse_date,
    normalise,
)


# ── Date normalisation ────────────────────────────────────────────────────────

class TestDateParsing:
    @pytest.mark.parametrize("raw,expected", [
        ("01/06/2024",     "2024-06-01"),   # ambiguous → DD/MM/YYYY
        ("15/03/1985",     "1985-03-15"),   # day > 12 → unambiguous
        ("20240601",       "2024-06-01"),
        ("01.06.2024",     "2024-06-01"),
        ("1-Jun-2024",     "2024-06-01"),
        ("June 1, 2024",   "2024-06-01"),
    ])
    def test_recognised_formats(self, raw, expected):
        assert _try_parse_date(raw) == expected

    def test_unix_timestamp_returns_iso_datetime(self):
        result = _try_parse_date("1717200000")
        assert result is not None
        assert result.startswith("2024-06-01")
        assert result.endswith("Z")

    @pytest.mark.parametrize("raw", ["not a date", "99/99/2024", "SO-20240601-001"])
    def test_unparseable_returns_none(self, raw):
        assert _try_parse_date(raw) is None

    def test_iso_dates_pass_through_unchanged(self):
        payload = {"created_at": "2024-06-01"}
        result = normalise(payload)
        assert result["created_at"] == "2024-06-01"
        assert result["_transform_metadata"]["dates_normalised"] == 0


# ── PII redaction ─────────────────────────────────────────────────────────────

class TestPIIRedaction:
    def test_redacts_known_pii_fields(self):
        payload = {
            "ssn": "123-45-6789",
            "email": "john@example.com",
            "phone": "+61-400-123-456",
            "name": "John Doe",
        }
        result = normalise(payload)
        assert result["ssn"]   == "[REDACTED]"
        assert result["email"] == "[REDACTED]"
        assert result["phone"] == "[REDACTED]"
        assert result["name"]  == "John Doe"  # not a PII field name

    def test_redaction_is_recursive(self):
        payload = {"customer": {"details": {"credit_card": "4111-1111-1111-1111"}}}
        result = normalise(payload)
        assert result["customer"]["details"]["credit_card"] == "[REDACTED]"

    def test_redacted_paths_recorded_in_metadata(self):
        payload = {"customer": {"email": "a@b.com"}}
        result = normalise(payload)
        assert "customer.email" in result["_transform_metadata"]["pii_redacted"]

    def test_field_name_match_is_case_insensitive(self):
        payload = {"SSN": "123-45-6789"}
        result = normalise(payload)
        assert result["SSN"] == "[REDACTED]"


# ── SAP OData flattening ──────────────────────────────────────────────────────

class TestSAPFlattening:
    def test_to_snake_case(self):
        assert _to_snake_case("SalesOrderNumber") == "sales_order_number"
        assert _to_snake_case("CustomerEmail")    == "customer_email"

    def test_flattens_d_results_envelope(self):
        payload = {"d": {"results": [{"SalesOrderNumber": "SO-1", "Quantity": 5}]}}
        flattened, did = _flatten_sap(payload)
        assert did is True
        assert flattened == [{"sales_order_number": "SO-1", "quantity": 5}]

    def test_strips_odata_metadata_keys(self):
        payload = {"d": {"results": [{"__metadata": {"type": "X"}, "Quantity": 5}]}}
        flattened, _ = _flatten_sap(payload)
        assert "__metadata" not in flattened[0]

    def test_nested_objects_flattened_with_prefix(self):
        payload = {"d": {"results": [{"Address": {"City": "Sydney", "PostCode": "2000"}}]}}
        flattened, _ = _flatten_sap(payload)
        assert flattened[0]["address_city"]      == "Sydney"
        assert flattened[0]["address_post_code"] == "2000"

    def test_non_sap_payload_untouched(self):
        payload = {"chunks": [{"content": "plain"}]}
        result, did = _flatten_sap(payload)
        assert did is False
        assert result == payload


# ── Truncation ────────────────────────────────────────────────────────────────

class TestTruncation:
    def _chunk(self, doc_id, words, score):
        return {"document_id": doc_id, "content": " ".join(["word"] * words), "score": score}

    def test_no_truncation_under_budget(self):
        payload = {"chunks": [self._chunk("A", 10, 0.9)]}
        result = normalise(payload, max_tokens=1_000)
        meta = result["_transform_metadata"]
        assert meta["truncated"] is False
        assert meta["chunks_dropped"] == 0

    def test_drops_lowest_scored_chunks_first(self):
        payload = {"chunks": [
            self._chunk("HIGH", 50, 0.9),
            self._chunk("LOW",  50, 0.1),
        ]}
        result = normalise(payload, max_tokens=60)
        kept_ids = [c["document_id"] for c in result["chunks"]]
        assert "HIGH" in kept_ids
        assert "LOW" not in kept_ids
        assert result["_transform_metadata"]["truncated"] is True
        assert result["_transform_metadata"]["chunks_dropped"] == 1

    def test_original_chunk_count_recorded(self):
        payload = {"chunks": [self._chunk(str(i), 5, 0.5) for i in range(4)]}
        result = normalise(payload, max_tokens=1_000)
        assert result["_transform_metadata"]["original_chunk_count"] == 4


# ── End-to-end over the sample fixture shape ──────────────────────────────────

class TestNormaliseEndToEnd:
    def test_sample_payload_shape(self):
        payload = {
            "chunks": [
                {
                    "content": "Q2 forecast AUD 4.2M",
                    "score": 0.92,
                    "document_id": "DOC-001",
                    "metadata": {"created_at": "01/06/2024"},
                },
                {
                    "d": {"results": [{
                        "__metadata": {"type": "SalesOrderItem"},
                        "SalesOrderNumber": "SO-1",
                        "CustomerEmail": "alice@corp.com",
                    }]}
                },
            ]
        }
        result = normalise(payload)
        meta = result["_transform_metadata"]

        assert meta["version"] == VERSION
        assert meta["dates_normalised"] >= 1
        assert meta["sap_flattened"] is True
        # SAP item flattened into the chunks list
        assert any("sales_order_number" in c for c in result["chunks"] if isinstance(c, dict))

    def test_input_payload_not_mutated(self):
        payload = {"email": "a@b.com"}
        normalise(payload)
        assert payload["email"] == "a@b.com"
