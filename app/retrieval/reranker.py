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
from llama_index.core.schema import NodeWithScore
from app.utils.logger import get_logger

logger = get_logger(__name__)

_colbert_reranker = None


def _load_colbert(top_k: int):
    """
    Lazy-load LlamaIndex ColbertRerank postprocessor.
    Cached at module level — loads once per session.
    Downloads colbert-ir/colbertv2.0 (~440MB) on first call.
    """
    global _colbert_reranker

    if _colbert_reranker is not None:
        return _colbert_reranker

    # ── COLBERT ON ────────────────────────────────────────────────────────
    # To disable: set USE_COLBERT=False in config.py
    try:
        from llama_index.postprocessor.colbert_rerank import ColbertRerank
        import time

        logger.info("Loading ColBERT reranker (first load ~30s, downloads ~440MB)...")
        start = time.time()

        _colbert_reranker = ColbertRerank(
            top_n=top_k,
            model="colbert-ir/colbertv2.0",
            tokenizer="colbert-ir/colbertv2.0",
            keep_retrieval_score=True,
        )

        logger.info(f"ColBERT reranker loaded in {time.time() - start:.2f}s")
        return _colbert_reranker

    except ImportError:
        logger.warning(
            "llama-index-postprocessor-colbert-rerank not installed.\n"
            "Run: pip install llama-index-postprocessor-colbert-rerank\n"
            "Or set USE_COLBERT=False in config.py to disable."
        )
        return None

    except Exception as e:
        logger.warning(f"ColBERT load failed: {e} — falling back to RRF scores")
        return None
    # ── END COLBERT ON ────────────────────────────────────────────────────


def rerank_with_colbert(
    query: str,
    nodes: List[NodeWithScore],
    top_k: int = 5,
) -> List[NodeWithScore]:
    """
    Rerank nodes using ColBERT late-interaction scoring.

    Falls back to RRF score sorting if ColBERT is disabled or unavailable.

    Args:
        query:  user query string
        nodes:  NodeWithScore list from QueryFusionRetriever
        top_k:  nodes to return after reranking

    Returns:
        Reranked list of NodeWithScore, trimmed to top_k
    """
    if not nodes:
        return []

    # ── COLBERT ON ────────────────────────────────────────────────────────
    from app.config import USE_COLBERT

    if USE_COLBERT:
        reranker = _load_colbert(top_k)

        if reranker is not None:
            try:
                import time
                from llama_index.core import QueryBundle

                start = time.time()

                # ColbertRerank is a NodePostprocessor — takes nodes + query bundle
                reranked = reranker.postprocess_nodes(
                    nodes,
                    query_bundle=QueryBundle(query_str=query),
                )

                logger.info(
                    f"ColBERT reranked {len(nodes)} → {len(reranked)} nodes "
                    f"in {time.time() - start:.2f}s"
                )
                return reranked[:top_k]

            except Exception as e:
                logger.warning(f"ColBERT reranking failed: {e} — using RRF scores")
    # ── END COLBERT ON ────────────────────────────────────────────────────

    # Fallback: sort by RRF scores from QueryFusionRetriever
    logger.info("Using RRF scores for ranking (ColBERT disabled or unavailable)")
    sorted_nodes = sorted(nodes, key=lambda n: n.score or 0.0, reverse=True)
    return sorted_nodes[:top_k]