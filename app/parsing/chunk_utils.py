from typing import List


def chunk_text(text: str, max_chunk_size: int = 800, overlap: int = 100) -> List[str]:
    """
    Safe and efficient text/code chunking with overlap.

    Hard limits:
    - Input text capped at 20,000 chars to protect memory
    - Max 200 chunks per call (raised from 50 — the old limit was too aggressive
      and silently truncated large files; 200 is safe on M4 16GB)
    - Overlap is clamped to half of max_chunk_size if misconfigured
    """

    if not text:
        return []

    # 🔒 Hard input cap
    MAX_TEXT_LIMIT = 20000
    text = text[:MAX_TEXT_LIMIT]

    # 🔒 Clamp overlap
    if overlap >= max_chunk_size:
        overlap = max_chunk_size // 2

    step = max_chunk_size - overlap

    # 🔒 Prevent zero/negative step
    if step <= 0:
        step = max_chunk_size

    chunks = []

    for i in range(0, len(text), step):
        chunk = text[i:i + max_chunk_size].strip()

        if chunk:
            chunks.append(chunk)

        # 🔒 Per-call safety limit
        # 200 is generous enough for all real files while still protecting RAM.
        # Will be removed entirely in LlamaIndex migration (CodeSplitter handles this).
        if len(chunks) >= 200:
            break

    return chunks