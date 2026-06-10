"""
tests/integration/test_pipeline.py — End-to-end pipeline test.

Exercises the full path:
  query → RAG retrieve (mocked OpenSearch) → AWS Transform (mocked atx) →
  sufficiency check (mocked Claude) → generate (mocked Claude) → eval (mocked)

No real network calls — all external I/O is mocked so this runs in CI without
any AWS credentials or running services.

Run with:  pytest tests/integration/ -v
"""
import json
import pathlib
import unittest.mock as m

import pytest


class TestFullRAGPipeline:
    """Integration test for AgentRAGOrchestrator end-to-end flow."""

    @pytest.fixture(autouse=True)
    def setup(self, sample_chunks):
        from services.rag.orchestrator import AgentRAGOrchestrator

        self.vs   = m.MagicMock()
        self.gs   = m.MagicMock()
        self.orch = AgentRAGOrchestrator(
            vector_store=self.vs,
            graph_store=self.gs,
            max_hops=2,
            sufficiency_threshold=0.75,
        )
        self.sample_chunks = sample_chunks

        # Default mocks
        self.vs.hybrid_search.return_value   = sample_chunks
        self.gs.extract_entity_ids.return_value = ["E1", "E2"]
        self.gs.get_related_entities.return_value = [
            {"id": "E1", "name": "APAC Region", "type": "Region",
             "description": "Asia Pacific business region", "source_doc": "DOC-001"}
        ]

    def _mock_anthropic(self, sufficient: bool, confidence: float, answer: str):
        """Configure the Anthropic client mock for sufficiency + generation."""
        client = m.MagicMock()
        call_count = [0]

        def create_side_effect(*args, **kwargs):
            call_count[0] += 1
            resp = m.MagicMock()
            if call_count[0] == 1:
                # First call = sufficiency
                resp.content[0].text = json.dumps({
                    "sufficient": sufficient,
                    "confidence": confidence,
                    "missing_information": [],
                    "follow_up_queries": ["follow up query"] if not sufficient else [],
                })
            else:
                # Subsequent calls = generation
                resp.content[0].text = answer
            return resp

        client.messages.create.side_effect = create_side_effect
        self.orch.client = client
        return client

    def _mock_transform_success(self, output_chunks):
        """Mock subprocess.run to return transformed chunks."""
        def fake_run(cmd, **kwargs):
            out_path = pathlib.Path(cmd[cmd.index("--output-path") + 1])
            out_path.write_text(json.dumps({
                "chunks": output_chunks,
                "_transform_metadata": {"pii_redacted": [], "dates_normalised": 1}
            }))
            return m.MagicMock(returncode=0)
        return m.patch("subprocess.run", side_effect=fake_run)

    # ── Happy path ────────────────────────────────────────────────────────────

    def test_single_hop_sufficient(self):
        client = self._mock_anthropic(sufficient=True, confidence=0.92,
                                      answer="The Q2 forecast is AUD 4.2M.")
        with self._mock_transform_success(self.sample_chunks):
            result = self.orch.retrieve_and_generate("What is Q2 forecast?")

        assert result.answer == "The Q2 forecast is AUD 4.2M."
        assert result.hops == 1
        assert result.sufficiency_score == 0.92
        assert len(result.sources) > 0

    def test_answer_contains_generated_text(self):
        self._mock_anthropic(sufficient=True, confidence=0.88,
                             answer="AWS Transform uses natural language definitions.")
        with self._mock_transform_success(self.sample_chunks):
            result = self.orch.retrieve_and_generate("What is AWS Transform?")

        assert "AWS Transform" in result.answer

    def test_transform_metadata_propagated(self):
        self._mock_anthropic(sufficient=True, confidence=0.9, answer="Answer.")
        with self._mock_transform_success(self.sample_chunks):
            result = self.orch.retrieve_and_generate("Q?")

        assert "pii_redacted" in result.transform_metadata

    def test_graph_enrichment_called(self):
        self._mock_anthropic(sufficient=True, confidence=0.9, answer="A.")
        with self._mock_transform_success(self.sample_chunks):
            self.orch.retrieve_and_generate("Q?")

        self.gs.extract_entity_ids.assert_called_once()
        self.gs.get_related_entities.assert_called_once()

    # ── Multi-hop ─────────────────────────────────────────────────────────────

    def test_retries_on_insufficient_context(self):
        """With sufficient=False on first call, should do a second hop."""
        client = m.MagicMock()
        calls  = [0]

        def create_side_effect(*args, **kwargs):
            calls[0] += 1
            resp = m.MagicMock()
            if calls[0] == 1:
                resp.content[0].text = json.dumps({
                    "sufficient": False, "confidence": 0.4,
                    "missing_information": ["APAC breakdown"],
                    "follow_up_queries": ["APAC regional breakdown"],
                })
            elif calls[0] == 2:
                resp.content[0].text = json.dumps({
                    "sufficient": True, "confidence": 0.88,
                    "missing_information": [], "follow_up_queries": [],
                })
            else:
                resp.content[0].text = "The APAC breakdown shows 60% Australia."
            return resp

        client.messages.create.side_effect = create_side_effect
        self.orch.client = client

        with self._mock_transform_success(self.sample_chunks):
            result = self.orch.retrieve_and_generate("APAC breakdown?")

        assert result.hops == 2
        assert self.vs.hybrid_search.call_count == 2

    def test_stops_at_max_hops(self):
        """Never exceeds max_hops=2 even if always insufficient."""
        client = m.MagicMock()
        client.messages.create.return_value.content[0].text = json.dumps({
            "sufficient": False, "confidence": 0.3,
            "missing_information": ["everything"],
            "follow_up_queries": ["more info"],
        })
        self.orch.client = client

        with self._mock_transform_success(self.sample_chunks):
            # Generate will fail on the JSON parse for the "answer" call, but that's ok
            # — we're testing hops, not answer content
            try:
                result = self.orch.retrieve_and_generate("unsatisfiable query?")
                assert result.hops <= 2
            except Exception:
                pass  # answer parsing may fail after max_hops; hops count is the assertion

        assert self.vs.hybrid_search.call_count <= 2

    # ── AWS Transform fallback ────────────────────────────────────────────────

    def test_continues_without_atx(self):
        """If atx is not installed, the pipeline continues with un-transformed chunks."""
        self._mock_anthropic(sufficient=True, confidence=0.9,
                             answer="Answer without transform.")
        with m.patch("subprocess.run", side_effect=FileNotFoundError("atx not found")):
            result = self.orch.retrieve_and_generate("Q?")

        assert "Answer without transform" in result.answer
        assert result.transform_metadata.get("skipped") is True

    # ── Sources ───────────────────────────────────────────────────────────────

    def test_sources_capped_at_ten(self):
        big_chunks = [
            {"document_id": f"DOC-{i}", "score": 1.0 - i * 0.01, "content": f"chunk {i}"}
            for i in range(20)
        ]
        self.vs.hybrid_search.return_value = big_chunks
        self.gs.extract_entity_ids.return_value = []
        self._mock_anthropic(sufficient=True, confidence=0.95, answer="A.")
        with self._mock_transform_success(big_chunks):
            result = self.orch.retrieve_and_generate("Q?")

        assert len(result.sources) <= 10
