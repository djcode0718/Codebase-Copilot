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
