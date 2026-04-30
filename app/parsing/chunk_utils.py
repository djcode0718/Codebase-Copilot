from typing import List

def chunk_text(text: str, max_chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    """
    Splits text into chunks of maximum size with a specified overlap.
    """
    if not text:
        return []
        
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + max_chunk_size, len(text))
        
        # If we are not at the end, try to find a newline to break at
        if end < len(text):
            last_newline = text.rfind('\\n', start, end)
            if last_newline != -1 and last_newline > start + (max_chunk_size // 2):
                end = last_newline + 1
                
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
            
        start = end - overlap
        if start < 0:
            start = 0
            
    return chunks
