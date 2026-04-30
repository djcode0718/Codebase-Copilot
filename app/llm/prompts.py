from typing import List, Dict, Any

SYSTEM_INSTRUCTION = """You are a senior software engineer explaining a codebase.
Your goal is to provide clear, concise, and accurate explanations based ONLY on the provided code snippets.
Always reference the file names and specific function/class names when explaining.
Do not hallucinate or make up code that is not present in the provided context.
"""

def build_prompt(query: str, chunks: List[Dict[str, Any]]) -> str:
    """
    Construct the final prompt containing the system instruction, 
    the retrieved code snippets (context), and the user query.
    """
    context_str = ""
    for idx, chunk in enumerate(chunks, 1):
        meta = chunk.get("metadata", {})
        file_name = meta.get("file_name", "Unknown File")
        path = meta.get("path", "Unknown Path")
        entity = meta.get("entity_name", "Unknown Entity")
        text = chunk.get("text", "")
        
        context_str += f"--- Snippet {idx} ---\n"
        context_str += f"File: {path} ({file_name})\n"
        context_str += f"Entity: {entity}\n"
        context_str += f"Code:\n```\n{text}\n```\n\n"

    prompt = f"{SYSTEM_INSTRUCTION}\n\n"
    prompt += "Here is the relevant code context from the repository:\n\n"
    prompt += context_str
    prompt += f"User Question: {query}\n\n"
    prompt += "Explanation:"
    
    return prompt
