"""
reranker.py
───────────
ColBERT reranking via LlamaIndex's native ColbertRerank postprocessor.
No RAGatouille dependency — uses the official LlamaIndex integration
which is stable and actively maintained.

Model: colbert-ir/colbertv2.0 (~440MB, CPU inference, runs well on M4)
Latency: ~2-3s per query for 10 chunks on M4 16GB

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TO DISABLE COLBERT:
  In config.py → set USE_COLBERT = False
  No other file needs to change.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from typing import List, Optional
import math
from llama_index.core.schema import NodeWithScore
from app.utils.logger import get_logger

logger = get_logger(__name__)

_cross_encoder = None


def _load_cross_encoder():
    """
    Lazy-load sentence-transformers CrossEncoder.
    Cached at module level — loads once per session.
    Downloads BAAI/bge-reranker-base on first call.
    """
    global _cross_encoder

    if _cross_encoder is not None:
        logger.info("CrossEncoder reranker cache hit: reusing loaded model instance")
        return _cross_encoder

    try:
        from sentence_transformers import CrossEncoder
        import time

        logger.info("Loading CrossEncoder reranker (BAAI/bge-reranker-base)...")
        start = time.time()

        _cross_encoder = CrossEncoder("BAAI/bge-reranker-base")

        logger.info(f"CrossEncoder reranker loaded in {time.time() - start:.2f}s (cache miss, initialized model instance)")
        return _cross_encoder

    except ImportError:
        logger.warning(
            "sentence-transformers not installed.\n"
            "Run: pip install sentence-transformers\n"
            "Or set USE_COLBERT=False in config.py to disable."
        )
        return None

    except Exception as e:
        logger.warning(f"CrossEncoder load failed: {e}; falling back to RRF scores")
        return None


def rerank_with_colbert(
    query: str,
    nodes: List[NodeWithScore],
    top_k: int = 5,
) -> List[NodeWithScore]:
    """
    Rerank nodes using a CrossEncoder model (BAAI/bge-reranker-base).

    Falls back to RRF score sorting if reranking is disabled or unavailable.

    Args:
        query:  user query string
        nodes:  NodeWithScore list from QueryFusionRetriever
        top_k:  nodes to return after reranking

    Returns:
        Reranked list of NodeWithScore, trimmed to top_k
    """
    if not nodes:
        return []

    from app.config import USE_COLBERT

    if USE_COLBERT:
        reranker = _load_cross_encoder()

        if reranker is not None:
            try:
                import time

                start = time.time()

                # Prepare pairs of (query, document text) for the cross-encoder
                pairs = [[query, node.node.get_content()] for node in nodes]
                scores = reranker.predict(pairs)

                # Assign scores to the nodes (sigmoid normalization to [0, 1])
                for node, score in zip(nodes, scores):
                    node.score = 1 / (1 + math.exp(-float(score)))

                # Sort descending by cross-encoder score
                reranked = sorted(nodes, key=lambda n: n.score or 0.0, reverse=True)

                logger.info(
                    f"CrossEncoder reranked {len(nodes)} -> {len(reranked)} nodes "
                    f"in {time.time() - start:.2f}s"
                )
                return reranked[:top_k]

            except Exception as e:
                logger.warning(f"CrossEncoder reranking failed: {e}; using RRF scores")

    # Fallback: sort by RRF scores from QueryFusionRetriever
    logger.info("Using RRF scores for ranking (CrossEncoder disabled or unavailable)")
    sorted_nodes = sorted(nodes, key=lambda n: n.score or 0.0, reverse=True)
    return sorted_nodes[:top_k]