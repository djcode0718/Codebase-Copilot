from typing import List

# def chunk_text(text: str, max_chunk_size: int = 1000, overlap: int = 200) -> List[str]:
#     """
#     Splits text into chunks of maximum size with a specified overlap.
#     """
#     if not text:
#         return []
        
#     chunks = []
#     start = 0
#     while start < len(text):
#         end = min(start + max_chunk_size, len(text))
        
#         # If we are not at the end, try to find a newline to break at
#         if end < len(text):
#             last_newline = text.rfind('\\n', start, end)
#             if last_newline != -1 and last_newline > start + (max_chunk_size // 2):
#                 end = last_newline + 1
                
#         chunk = text[start:end].strip()
#         if chunk:
#             chunks.append(chunk)
            
#         start = end - overlap
#         if start < 0:
#             start = 0
            
#     return chunks


def chunk_text(text: str, max_chunk_size: int = 800, overlap: int = 100) -> List[str]:
    """
    Safe and efficient chunking for code/text.
    Prevents infinite loops and memory explosion.
    """

    if not text:
        return []

    # 🔒 Hard cap (protects RAM)
    MAX_TEXT_LIMIT = 20000
    text = text[:MAX_TEXT_LIMIT]

    # 🔒 Fix overlap
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

        # 🔒 Safety limit (VERY IMPORTANT)
        if len(chunks) >= 50:
            break

    return chunks
