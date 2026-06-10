"""
tests/unit/test_rag_logic.py — Unit tests for RAG retrieval logic.
No external services required — all I/O is mocked via conftest.py stubs.
"""
import json
import pathlib
import subprocess
import tempfile
import unittest.mock as m

import pytest

from services.rag.vector_store import EnterpriseVectorStore
from services.rag.orchestrator import AgentRAGOrchestrator, RAGResult, _merge_deduplicate


# ── _merge_deduplicate ────────────────────────────────────────────────────────

class TestMergeDeduplicate:
    def test_deduplicates_by_document_id(self):
        existing = [{"document_id": "A", "score": 0.9, "content": "hello"}]
        new      = [{"document_id": "A", "score": 0.5, "content": "hello dup"},
                    {"document_id": "B", "score": 0.7, "content": "world"}]
        result = _merge_deduplicate(existing, new)
        ids = [r["document_id"] for r in result]
        assert ids.count("A") == 1, "A should appear only once"
        assert "B" in ids

    def test_sorted_by_score_descending(self):
        c1 = [{"document_id": "LOW",  "score": 0.3, "content": "low"}]
        c2 = [{"document_id": "HIGH", "score": 0.9, "content": "high"}]
        result = _merge_deduplicate(c1, c2)
        assert result[0]["document_id"] == "HIGH"

    def test_handles_missing_document_id(self):
        chunks = [{"content": "no id chunk", "score": 0.5},
                  {"content": "another",      "score": 0.4}]
        result = _merge_deduplicate([], chunks)
        assert len(result) == 2

    def test_empty_inputs(self):
        assert _merge_deduplicate([], []) == []

    def test_preserves_all_fields(self, sample_chunks):
        result = _merge_deduplicate([], sample_chunks)
        assert all("metadata" in r for r in result)
        assert all("source"   in r for r in result)


# ── RRF Fusion ────────────────────────────────────────────────────────────────

class TestRRFFusion:
    @pytest.fixture(autouse=True)
    def vs(self):
        self.vs = object.__new__(EnterpriseVectorStore)
        self.vs.RRF_K = 60

    def test_returns_top_k(self, sample_dense_hits, sample_bm25_hits):
        result = self.vs._rrf_fusion(sample_dense_hits, sample_bm25_hits, top_k=3, dense_weight=0.7)
        assert len(result) == 3

    def test_scores_sorted_descending(self, sample_dense_hits, sample_bm25_hits):
        result = self.vs._rrf_fusion(sample_dense_hits, sample_bm25_hits, top_k=5, dense_weight=0.7)
        scores = [r["score"] for r in result]
        assert scores == sorted(scores, reverse=True)

    def test_shared_doc_scores_higher(self):
        shared = [{"_source": {"document_id": "SHARED", "content": "shared", "metadata": {}}}]
        unique = [{"_source": {"document_id": "UNIQUE", "content": "unique", "metadata": {}}}]
        both = self.vs._rrf_fusion(shared, shared, top_k=1, dense_weight=0.5)
        one  = self.vs._rrf_fusion(shared, unique, top_k=1, dense_weight=0.5)
        # shared doc appears in both lists → boosted score
        shared_in_both = next(r for r in self.vs._rrf_fusion(shared, shared, top_k=2, dense_weight=0.5) if r["document_id"] == "SHARED")
        shared_in_one  = next(r for r in self.vs._rrf_fusion(shared, unique, top_k=2, dense_weight=0.5) if r["document_id"] == "SHARED")
        assert shared_in_both["score"] > shared_in_one["score"]

    def test_dense_weight_affects_ranking(self):
        dense = [{"_source": {"document_id": "D", "content": "d", "metadata": {}}}]
        bm25  = [{"_source": {"document_id": "B", "content": "b", "metadata": {}}}]
        result_dense_heavy = self.vs._rrf_fusion(dense, bm25, top_k=2, dense_weight=0.9)
        assert result_dense_heavy[0]["document_id"] == "D"
        result_bm25_heavy  = self.vs._rrf_fusion(dense, bm25, top_k=2, dense_weight=0.1)
        assert result_bm25_heavy[0]["document_id"] == "B"

    def test_empty_bm25_returns_dense_only(self, sample_dense_hits):
        result = self.vs._rrf_fusion(sample_dense_hits, [], top_k=3, dense_weight=0.7)
        assert len(result) == 3
        assert all(r["document_id"].startswith("DENSE") for r in result)

    def test_all_scores_positive(self, sample_dense_hits, sample_bm25_hits):
        result = self.vs._rrf_fusion(sample_dense_hits, sample_bm25_hits, top_k=10, dense_weight=0.7)
        assert all(r["score"] > 0 for r in result)


# ── _format_context ───────────────────────────────────────────────────────────

class TestFormatContext:
    @pytest.fixture(autouse=True)
    def orch(self):
        self.orch = object.__new__(AgentRAGOrchestrator)

    def test_labels_each_chunk_with_doc_id(self):
        chunks = [{"document_id": "DOC-001", "content": "Revenue 4.2M"}]
        ctx = self.orch._format_context(chunks)
        assert "[DOC-001]" in ctx
        assert "Revenue 4.2M" in ctx

    def test_falls_back_to_metadata_document_id(self):
        chunks = [{"content": "No top-level ID", "metadata": {"document_id": "META-001"}}]
        ctx = self.orch._format_context(chunks)
        assert "[META-001]" in ctx

    def test_separates_chunks_with_divider(self):
        chunks = [
            {"document_id": "A", "content": "first"},
            {"document_id": "B", "content": "second"},
        ]
        ctx = self.orch._format_context(chunks)
        assert "---" in ctx

    def test_empty_chunks_returns_empty_string(self):
        assert self.orch._format_context([]) == ""

    def test_missing_content_is_safe(self):
        chunks = [{"document_id": "X"}]
        ctx = self.orch._format_context(chunks)
        assert "[X]" in ctx  # should not raise


# ── AWS Transform CLI invocation ──────────────────────────────────────────────

class TestRunAWSTransform:
    @pytest.fixture(autouse=True)
    def orch(self):
        self.orch = object.__new__(AgentRAGOrchestrator)
        self.orch.transform_definition = "enterprise-context-normaliser"

    def test_returns_original_chunks_when_atx_not_installed(self, sample_chunks):
        with m.patch("subprocess.run", side_effect=FileNotFoundError("atx not found")):
            result, meta = self.orch._run_aws_transform(sample_chunks)
        assert result == sample_chunks
        assert meta["skipped"] is True
        assert "atx_not_installed" in meta["reason"]

    def test_returns_transformed_chunks_on_success(self, sample_chunks, tmp_path):
        transformed = [{"document_id": "DOC-001", "content": "REDACTED content", "score": 0.92}]
        output_payload = json.dumps({"chunks": transformed, "_transform_metadata": {"pii_redacted": ["email"]}})

        def fake_run(cmd, **kwargs):
            # Write transformed output to the expected output path
            out_path = pathlib.Path(cmd[cmd.index("--output-path") + 1])
            out_path.write_text(output_payload)
            proc = m.MagicMock()
            proc.returncode = 0
            return proc

        with m.patch("subprocess.run", side_effect=fake_run):
            result, meta = self.orch._run_aws_transform(sample_chunks)

        assert result == transformed
        assert meta.get("pii_redacted") == ["email"]

    def test_returns_original_on_subprocess_error(self, sample_chunks):
        with m.patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "atx", stderr="Transform failed")):
            result, meta = self.orch._run_aws_transform(sample_chunks)
        assert result == sample_chunks
        assert "error" in meta

    def test_atx_cli_args_are_correct(self, sample_chunks):
        """Verify atx is called with the right flags."""
        called_with = []

        def capture_run(cmd, **kwargs):
            called_with.extend(cmd)
            raise FileNotFoundError  # short-circuit

        with m.patch("subprocess.run", side_effect=capture_run):
            self.orch._run_aws_transform(sample_chunks)

        assert "atx" in called_with
        assert "custom" in called_with
        assert "def" in called_with
        assert "exec" in called_with
        assert "--definition" in called_with
        assert "enterprise-context-normaliser" in called_with
        assert "--trust-all-tools" in called_with


# ── Sufficiency assessment parsing ────────────────────────────────────────────

class TestAssessSufficiency:
    @pytest.fixture(autouse=True)
    def orch(self):
        self.orch = object.__new__(AgentRAGOrchestrator)
        self.orch.threshold = 0.75

    def test_parses_sufficient_true(self):
        mock_client = m.MagicMock()
        mock_client.messages.create.return_value.content[0].text = json.dumps({
            "sufficient": True, "confidence": 0.92,
            "missing_information": [], "follow_up_queries": []
        })
        self.orch.client = mock_client
        result = self.orch._assess_sufficiency("What is Q2 forecast?", "Revenue is 4.2M")
        assert result["sufficient"] is True
        assert result["confidence"] == 0.92

    def test_returns_fallback_on_json_parse_error(self):
        mock_client = m.MagicMock()
        mock_client.messages.create.return_value.content[0].text = "not valid json"
        self.orch.client = mock_client
        result = self.orch._assess_sufficiency("Q?", "context")
        assert result["sufficient"] is True   # fallback = proceed
        assert "confidence" in result

    def test_returns_fallback_on_api_error(self):
        mock_client = m.MagicMock()
        mock_client.messages.create.side_effect = Exception("API error")
        self.orch.client = mock_client
        result = self.orch._assess_sufficiency("Q?", "context")
        assert isinstance(result, dict)
        assert "sufficient" in result
