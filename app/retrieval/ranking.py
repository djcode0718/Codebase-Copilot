from typing import List, Dict, Any
from app.utils.logger import get_logger

logger = get_logger(__name__)


def rerank_chunks(query: str, chunks: List[Dict[str, Any]], top_k: int = 5):
    """
    Lightweight re-ranking
    """

    if not chunks:
        return []

    # 🔹 Filter weak chunks
    filtered = [c for c in chunks if c.get("score", 0) > 0.05]

    if not filtered:
        logger.warning("All scores low → fallback")
        filtered = chunks

    # 🔹 Sort again (safety)
    filtered.sort(key=lambda x: x.get("score", 0), reverse=True)

    logger.info(f"Reranked → returning {top_k} chunks")

    return filtered[:top_k]

