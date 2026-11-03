"""
reranker.py
───────────
Reranking via sentence-transformers CrossEncoder using the BAAI/bge-reranker-base model.
No Colbert IR late-interaction is used; this is plain cross-encoder pairwise scoring with sigmoid normalization.

Model: BAAI/bge-reranker-base (~440MB, CPU inference, runs well on M4)
Latency: ~2-3s per query for 10 chunks on M4 16GB

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TO DISABLE RERANKER:
  In config.py → set USE_RERANKER = False
  No other file needs to change.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import asyncio
from typing import List, Optional
import math
from collections import OrderedDict
import threading
import re

from llama_index.core.schema import NodeWithScore
from app.utils.logger import get_logger

logger = get_logger(__name__)

_cross_encoder = None


class LRUCache:
    def __init__(self, capacity: int = 200):
        self.capacity = capacity
        self.cache = OrderedDict()
        self.lock = threading.Lock()

    def get(self, key):
        with self.lock:
            if key not in self.cache:
                return None
            self.cache.move_to_end(key)
            return self.cache[key]

    def put(self, key, value):
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
            self.cache[key] = value
            if len(self.cache) > self.capacity:
                self.cache.popitem(last=False)


_reranker_cache = LRUCache(200)


def _normalize_query(query: str) -> str:
    q = query.lower().strip()
    q = re.sub(r'[^\w\s]', '', q)
    return " ".join(q.split())


def _get_node_set_hash(nodes: List[NodeWithScore]) -> int:
    node_ids = sorted([node.node.node_id for node in nodes])
    return hash(tuple(node_ids))


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
            "Or set USE_RERANKER=False in config.py to disable."
        )
        return None

    except Exception as e:
        logger.warning(f"CrossEncoder load failed: {e}; falling back to RRF scores")
        return None


def rerank_with_cross_encoder(
    query: str,
    nodes: List[NodeWithScore],
    top_k: int = 5,
    index_name: Optional[str] = None,
) -> List[NodeWithScore]:
    """
    Rerank nodes using a CrossEncoder model (BAAI/bge-reranker-base).

    Falls back to RRF score sorting if reranking is disabled or unavailable.

    Args:
        query:      user query string
        nodes:      NodeWithScore list from QueryFusionRetriever
        top_k:      nodes to return after reranking
        index_name: optional name of the active index for caching scope

    Returns:
        Reranked list of NodeWithScore, trimmed to top_k
    """
    if not nodes:
        return []

    from app.config import USE_RERANKER
    if USE_RERANKER:
        norm_query = _normalize_query(query)
        node_hash = _get_node_set_hash(nodes)
        cache_key = (index_name or "", norm_query, node_hash)

        cached_scores = _reranker_cache.get(cache_key)
        if cached_scores is not None:
            logger.info(f"Reranker cache hit: reusing scores for {len(nodes)} nodes")
            for node in nodes:
                node.score = cached_scores.get(node.node.node_id, 0.0)
            reranked = sorted(nodes, key=lambda n: n.score or 0.0, reverse=True)
            return reranked[:top_k]
        reranker = _load_cross_encoder()

        if reranker is not None:
            try:
                import time

                start = time.time()

                # Prepare sanitized pairs of (query, document text) for the cross-encoder
                clean_query = (query or " ").replace("\x00", "").strip()[:1000]
                pairs = []
                for node in nodes:
                    txt = (node.node.get_content() or " ").replace("\x00", "").strip()
                    meta = getattr(node.node, "metadata", {}) or {}
                    path = meta.get("path") or meta.get("file_name") or meta.get("file_path") or ""
                    symbol = meta.get("symbol_name") or meta.get("function_name") or meta.get("class_name") or meta.get("name") or ""

                    header_parts = []
                    if path and not txt.startswith("File:") and not txt.startswith(f"[{path}]"):
                        header_parts.append(f"File: {path}")
                    if symbol and f"Symbol: {symbol}" not in txt:
                        header_parts.append(f"Symbol: {symbol}")

                    if header_parts:
                        header = "\n".join(header_parts)
                        doc_text = f"{header}\n\nContent:\n{txt}"
                    else:
                        doc_text = txt

                    # Cap to 4000 chars to avoid memory/tokenizer crashes
                    pairs.append([clean_query, doc_text[:4000] if doc_text else " "])

                scores = reranker.predict(pairs)

                # Assign scores to the nodes (sigmoid normalization to [0, 1])
                node_scores = {}
                for node, score in zip(nodes, scores):
                    sig_score = 1 / (1 + math.exp(-float(score)))
                    node.score = sig_score
                    node_scores[node.node.node_id] = sig_score

                # Populate cache
                _reranker_cache.put(cache_key, node_scores)

                # Sort descending by cross-encoder score
                reranked = sorted(nodes, key=lambda n: n.score or 0.0, reverse=True)

                logger.info(
                    f"CrossEncoder reranked {len(nodes)} -> {len(reranked)} nodes "
                    f"in {time.time() - start:.2f}s"
                )
                return reranked[:top_k]

            except (asyncio.CancelledError, GeneratorExit, KeyboardInterrupt, SystemExit):
                raise
            except Exception as e:
                logger.warning(f"CrossEncoder reranking failed: {e}; using RRF scores")

    # Fallback: sort by RRF scores from QueryFusionRetriever
    logger.info("Using RRF scores for ranking (CrossEncoder disabled or unavailable)")
    sorted_nodes = sorted(nodes, key=lambda n: n.score or 0.0, reverse=True)
    return sorted_nodes[:top_k]


# Backward-compatible alias for existing callers
rerank_with_colbert = rerank_with_cross_encoder