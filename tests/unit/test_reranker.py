"""Smoke test for app/retrieval/reranker.py"""
from __future__ import annotations
import math
from unittest.mock import MagicMock, patch
from llama_index.core.schema import NodeWithScore, TextNode
import app.retrieval.reranker as reranker


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def test_reranker_module_importable():
    assert reranker is not None

def test_rerank_fallback_rrf():
    nodes = [
        NodeWithScore(node=TextNode(text="first"), score=0.2),
        NodeWithScore(node=TextNode(text="second"), score=0.8),
    ]
    with patch("app.config.USE_RERANKER", False):
        result = reranker.rerank_with_cross_encoder("query", nodes, top_k=2)
        assert len(result) == 2
        assert result[0].node.get_content() == "second"
        assert result[0].score == 0.8
        assert result[1].node.get_content() == "first"
        assert result[1].score == 0.2

def test_rerank_cross_encoder():
    """CrossEncoder logit scores are sigmoid-normalized before being stored on nodes."""
    nodes = [
        NodeWithScore(node=TextNode(text="first"), score=0.2),
        NodeWithScore(node=TextNode(text="second"), score=0.8),
    ]
    mock_encoder = MagicMock()
    mock_encoder.predict.return_value = [0.9, 0.1]

    with patch("app.config.USE_RERANKER", True), \
         patch("app.retrieval.reranker._load_cross_encoder", return_value=mock_encoder):
        result = reranker.rerank_with_cross_encoder("query", nodes, top_k=2)
        assert len(result) == 2
        assert result[0].node.get_content() == "first"
        assert result[1].node.get_content() == "second"
        assert abs(result[0].score - _sigmoid(0.9)) < 1e-6
        assert abs(result[1].score - _sigmoid(0.1)) < 1e-6

def test_reranker_cache():
    """Reranker cache prevents calling cross-encoder model again for identical queries/nodes."""
    nodes = [
        NodeWithScore(node=TextNode(text="first", id_="node_1"), score=0.2),
        NodeWithScore(node=TextNode(text="second", id_="node_2"), score=0.8),
    ]
    mock_encoder = MagicMock()
    mock_encoder.predict.return_value = [0.9, 0.1]

    from app.retrieval.reranker import _reranker_cache
    _reranker_cache.cache.clear()

    with patch("app.config.USE_RERANKER", True), \
         patch("app.retrieval.reranker._load_cross_encoder", return_value=mock_encoder):
        # First call: cache miss, calls model
        res1 = reranker.rerank_with_cross_encoder("query_text", nodes, top_k=2, index_name="test_idx")
        assert len(res1) == 2
        mock_encoder.predict.assert_called_once()
        
        # Reset mock
        mock_encoder.reset_mock()
        
        # Second call: cache hit, should NOT call model again
        res2 = reranker.rerank_with_cross_encoder("query_text", nodes, top_k=2, index_name="test_idx")
        assert len(res2) == 2
        mock_encoder.predict.assert_not_called()
        assert abs(res2[0].score - _sigmoid(0.9)) < 1e-6


def test_reranker_ordinary_exception_falls_back_to_rrf():
    """Ordinary exceptions during predict (e.g. PyO3 tokenization, runtime error) fall back to RRF."""
    import pytest
    nodes = [
        NodeWithScore(node=TextNode(text="low_rrf", id_="n1"), score=0.1),
        NodeWithScore(node=TextNode(text="high_rrf", id_="n2"), score=0.9),
    ]
    mock_encoder = MagicMock()
    mock_encoder.predict.side_effect = RuntimeError("PyO3 tokenizer panic or runtime failure")

    with patch("app.config.USE_RERANKER", True), \
         patch("app.retrieval.reranker._load_cross_encoder", return_value=mock_encoder):
        result = reranker.rerank_with_cross_encoder("query", nodes, top_k=2)
        assert len(result) == 2
        # Graceful fallback sorts by original RRF scores descending
        assert result[0].node.get_content() == "high_rrf"
        assert result[0].score == 0.9
        assert result[1].node.get_content() == "low_rrf"
        assert result[1].score == 0.1


def test_reranker_asyncio_cancelled_error_propagates():
    """asyncio.CancelledError must NOT be swallowed; it must propagate to the caller."""
    import asyncio
    import pytest
    nodes = [NodeWithScore(node=TextNode(text="doc", id_="n1"), score=0.5)]
    mock_encoder = MagicMock()
    mock_encoder.predict.side_effect = asyncio.CancelledError("Task was cancelled")

    with patch("app.config.USE_RERANKER", True), \
         patch("app.retrieval.reranker._load_cross_encoder", return_value=mock_encoder):
        with pytest.raises(asyncio.CancelledError):
            reranker.rerank_with_cross_encoder("query", nodes, top_k=1)


def test_reranker_generator_exit_propagates():
    """GeneratorExit must NOT be swallowed; it must propagate to the caller."""
    import pytest
    nodes = [NodeWithScore(node=TextNode(text="doc", id_="n1"), score=0.5)]
    mock_encoder = MagicMock()
    mock_encoder.predict.side_effect = GeneratorExit()

    with patch("app.config.USE_RERANKER", True), \
         patch("app.retrieval.reranker._load_cross_encoder", return_value=mock_encoder):
        with pytest.raises(GeneratorExit):
            reranker.rerank_with_cross_encoder("query", nodes, top_k=1)


def test_reranker_keyboard_interrupt_and_system_exit_propagate():
    """KeyboardInterrupt and SystemExit must NOT be swallowed."""
    import pytest
    nodes = [NodeWithScore(node=TextNode(text="doc", id_="n1"), score=0.5)]
    
    mock_encoder = MagicMock()
    mock_encoder.predict.side_effect = KeyboardInterrupt()
    with patch("app.config.USE_RERANKER", True), \
         patch("app.retrieval.reranker._load_cross_encoder", return_value=mock_encoder):
        with pytest.raises(KeyboardInterrupt):
            reranker.rerank_with_cross_encoder("query", nodes, top_k=1)

    mock_encoder.predict.side_effect = SystemExit(1)
    with patch("app.config.USE_RERANKER", True), \
         patch("app.retrieval.reranker._load_cross_encoder", return_value=mock_encoder):
        with pytest.raises(SystemExit):
            reranker.rerank_with_cross_encoder("query", nodes, top_k=1)


def test_cross_encoder_metadata_distinguishes_identical_code():
    """Identical code content from different files is distinguished using injected path metadata."""
    identical_code = "def process(data):\n    return [d.strip() for d in data]"
    node_impl = NodeWithScore(
        node=TextNode(text=identical_code, id_="node_impl", metadata={"path": "src/core/processor.py", "symbol_name": "process"}),
        score=0.5,
    )
    node_test = NodeWithScore(
        node=TextNode(text=identical_code, id_="node_test", metadata={"path": "tests/mocks/test_processor.py", "symbol_name": "process"}),
        score=0.5,
    )

    captured_pairs = []
    mock_encoder = MagicMock()
    def fake_predict(pairs):
        captured_pairs.extend(pairs)
        # Score the production implementation higher when query targets core processor
        return [2.5, -0.5]
    mock_encoder.predict.side_effect = fake_predict

    with patch("app.config.USE_RERANKER", True), \
         patch("app.retrieval.reranker._load_cross_encoder", return_value=mock_encoder):
        res = reranker.rerank_with_cross_encoder("how does src/core/processor.py implement process?", [node_impl, node_test], top_k=2)

        assert len(captured_pairs) == 2
        # Check that metadata headers were formatted explicitly
        assert "File: src/core/processor.py" in captured_pairs[0][1]
        assert "Symbol: process" in captured_pairs[0][1]
        assert "File: tests/mocks/test_processor.py" in captured_pairs[1][1]
        assert captured_pairs[0][1] != captured_pairs[1][1]
        assert res[0].node.node_id == "node_impl"
        assert res[0].score > res[1].score


def test_cross_encoder_prevents_systematic_readme_displacement():
    """Relevant implementation chunks with path metadata are not displaced by general README chunks."""
    impl_chunk = NodeWithScore(
        node=TextNode(
            text="def predict_single_image(model, img):\n    return model(img).argmax(dim=-1)",
            id_="code_chunk",
            metadata={"path": "compare/predict_single_image.py", "symbol_name": "predict_single_image"},
        ),
        score=0.6,
    )
    readme_chunk = NodeWithScore(
        node=TextNode(
            text="# Project Readme\nRun `python compare/predict_single_image.py` for inference.",
            id_="readme_chunk",
            metadata={"path": "README.md"},
        ),
        score=0.65,
    )

    captured_pairs = []
    mock_encoder = MagicMock()
    def fake_predict(pairs):
        captured_pairs.extend(pairs)
        # Code chunk scores higher because query specifically targets predict_single_image function
        return [3.0, 1.0] if "compare/predict_single_image.py" in pairs[0][1] else [1.0, 3.0]
    mock_encoder.predict.side_effect = fake_predict

    with patch("app.config.USE_RERANKER", True), \
         patch("app.retrieval.reranker._load_cross_encoder", return_value=mock_encoder):
        res = reranker.rerank_with_cross_encoder("where is predict_single_image defined?", [impl_chunk, readme_chunk], top_k=2)
        assert res[0].node.node_id == "code_chunk"
        assert res[0].score > res[1].score


def test_cross_encoder_missing_metadata_handled_safely():
    """Nodes missing path or symbol metadata format safely without errors or None values."""
    node_no_meta = NodeWithScore(node=TextNode(text="raw code without metadata", id_="n_nometa"), score=0.5)
    node_empty_meta = NodeWithScore(node=TextNode(text="code with empty dict", id_="n_empty", metadata={}), score=0.5)
    node_partial_meta = NodeWithScore(node=TextNode(text="code with path only", id_="n_path", metadata={"path": "utils.py"}), score=0.5)

    captured_pairs = []
    mock_encoder = MagicMock()
    mock_encoder.predict.side_effect = lambda pairs: (captured_pairs.extend(pairs), [1.0, 0.5, 0.2])[1]

    with patch("app.config.USE_RERANKER", True), \
         patch("app.retrieval.reranker._load_cross_encoder", return_value=mock_encoder):
        res = reranker.rerank_with_cross_encoder("sample query", [node_no_meta, node_empty_meta, node_partial_meta], top_k=3)
        assert len(res) == 3
        # First two should have no header or just raw text
        assert "File:" not in captured_pairs[0][1]
        assert "None" not in captured_pairs[0][1]
        assert "File:" not in captured_pairs[1][1]
        # Third should have File: utils.py and no Symbol: None
        assert "File: utils.py" in captured_pairs[2][1]
        assert "Symbol:" not in captured_pairs[2][1]

