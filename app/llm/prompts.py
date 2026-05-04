# from typing import List, Dict, Any

# SYSTEM_INSTRUCTION = """You are a senior software engineer explaining a codebase.
# Your goal is to provide clear, concise, and accurate explanations based ONLY on the provided code snippets.
# Always reference the file names and specific function/class names when explaining.
# Do not hallucinate or make up code that is not present in the provided context.
# STRICT RULES:
# 1. If the answer is not clearly present, say: "Not found in provided code."
# 2. DO NOT guess or hallucinate.
# 3. Prefer README or documentation if available.
# 4. Be precise and factual.

# Always mention file names when possible.
# """

# def build_prompt(query: str, chunks: List[Dict[str, Any]]) -> str:
#     """
#     Construct the final prompt containing the system instruction, 
#     the retrieved code snippets (context), and the user query.
#     """
#     MAX_CONTEXT_CHARS = 4000

#     context_str = ""
#     for idx, chunk in enumerate(chunks, 1):
#         text = chunk.get("text", "")

#         if len(context_str) + len(text) > MAX_CONTEXT_CHARS:
#             break
#         meta = chunk.get("metadata", {})
#         file_name = meta.get("file_name", "Unknown File")
#         path = meta.get("path", "Unknown Path")
#         entity = meta.get("entity_name", "Unknown Entity")
#         text = chunk.get("text", "")
        
#         context_str += f"--- Snippet {idx} ---\n"
#         context_str += f"File: {path} ({file_name})\n"
#         context_str += f"Entity: {entity}\n"
#         context_str += f"Code:\n```\n{text}\n```\n\n"

#     prompt = f"{SYSTEM_INSTRUCTION}\n\n"
#     prompt += """
#     Answer clearly and completely.
#     If the question is simple → be concise.
#     If it requires detail → provide a detailed explanation.
#     """
#     prompt += "Here is the relevant code context from the repository:\n\n"
#     prompt += context_str
#     prompt += f"User Question: {query}\n\n"
#     prompt += "Explanation:"
    
#     return prompt




# from typing import List, Dict, Any

# SYSTEM_INSTRUCTION = """You are a senior software engineer explaining a codebase.
# Your goal is to provide clear, concise, and accurate explanations based ONLY on the provided code snippets.
# Always reference the file names and specific function/class names when explaining.
# Do not hallucinate or make up code that is not present in the provided context.
# """

# def build_prompt(query: str, chunks: List[Dict[str, Any]]) -> str:
#     """
#     Construct the final prompt containing the system instruction, 
#     the retrieved code snippets (context), and the user query.
#     """
#     context_str = ""
#     for idx, chunk in enumerate(chunks, 1):
#         meta = chunk.get("metadata", {})
#         file_name = meta.get("file_name", "Unknown File")
#         path = meta.get("path", "Unknown Path")
#         entity = meta.get("entity_name", "Unknown Entity")
#         text = chunk.get("text", "")
        
#         context_str += f"--- Snippet {idx} ---\n"
#         context_str += f"File: {path} ({file_name})\n"
#         context_str += f"Entity: {entity}\n"
#         context_str += f"Code:\n```\n{text}\n```\n\n"

#     prompt = f"{SYSTEM_INSTRUCTION}\n\n"
#     prompt += "Here is the relevant code context from the repository:\n\n"
#     prompt += context_str
#     prompt += f"User Question: {query}\n\n"
#     prompt += "Explanation:"
    
#     return prompt


# from typing import List, Dict, Any

# SYSTEM_INSTRUCTION = """You are a senior software engineer explaining a codebase.
# Answer ONLY using the provided context.
# If information is not present, say: "Not found in provided code."
# Be concise unless the question asks for detail.
# """


# def build_prompt(query: str, chunks: List[Dict[str, Any]], history: List[Dict[str, str]] = None) -> str:
#     # 🔹 Build context
#     context_str = ""
#     for idx, chunk in enumerate(chunks, 1):
#         meta = chunk.get("metadata", {})
#         file_name = meta.get("file_name", "Unknown File")
#         path = meta.get("path", "Unknown Path")
#         entity = meta.get("entity_name", "Unknown Entity")
#         text = chunk.get("text", "")

#         context_str += f"--- Snippet {idx} ---\n"
#         context_str += f"File: {path} ({file_name})\n"
#         context_str += f"Entity: {entity}\n"
#         context_str += f"Code:\n```\n{text}\n```\n\n"

#     # 🔹 Build chat history (short, last few turns)
#     history_str = ""
#     if history:
#         for msg in history:
#             role = msg["role"]
#             content = msg["content"]
#             history_str += f"{role.upper()}: {content}\n"

#     prompt = f"{SYSTEM_INSTRUCTION}\n\n"

#     if history_str:
#         prompt += "Conversation so far:\n"
#         prompt += history_str + "\n"

#     prompt += "Relevant code context:\n\n"
#     prompt += context_str

#     prompt += f"User Question: {query}\n\n"
#     prompt += "Answer:"

#     return prompt

"""
prompts.py
──────────
Two prompt modes matched to the query router output:

  CODE_LOOKUP_PROMPT    strict — answer only from retrieved code chunks
  ARCHITECTURAL_PROMPT  relaxed — reason beyond the code for broad questions

Both are used as system prompts inside CondensePlusContextChatEngine.
"""

# ─── CODE LOOKUP ──────────────────────────────────────────────────────────────
# Used for: specific function/class/file questions
# Behaviour: strictly grounded in retrieved chunks, no speculation
CODE_LOOKUP_PROMPT = """You are a senior software engineer explaining a codebase.

RULES:
- Answer ONLY using the provided code context.
- If the answer is not present in the context, say exactly:
  "I couldn't find that in the retrieved code. Try rephrasing or asking about a specific file or function."
- Always reference the file name and function/class name when relevant.
- Be concise for simple questions, detailed for complex ones.
- Format code with markdown code blocks."""


# ─── ARCHITECTURAL ────────────────────────────────────────────────────────────
# Used for: limitations, improvements, design patterns, broad questions
# Behaviour: uses context as primary source but may reason beyond it
ARCHITECTURAL_PROMPT = """You are a senior software engineer and technical architect reviewing a codebase.

RULES:
- Use the provided codebase context as your PRIMARY source.
- You MAY reason beyond the literal code to identify patterns, limitations,
  and improvement opportunities — this is expected for architectural questions.
- When you cite something directly from the code, mention the file name.
- When you are reasoning or suggesting (not directly from code), say so clearly
  with phrases like "Based on the architecture..." or "A common improvement here would be..."
- Be thorough for broad questions. Use structured responses with headers when helpful.
- Do NOT make up function names or file names that aren't in the context.

RESPONSE STYLE for common question types:
- "What are the limitations?" → List them clearly with brief explanations
- "How can I improve this?"   → Prioritised suggestions with rationale
- "What design patterns?"     → Identify patterns visible in the code
- "How does X compare to Y?"  → Balanced comparison grounded in the code"""



# from typing import List, Dict, Any

# SYSTEM_INSTRUCTION = """You are a senior software engineer analyzing a codebase.

# STRICT RULES:
# 1. Answer ONLY using the provided code context.
# 2. If the answer is not clearly present, say: "Not found in provided code."
# 3. DO NOT guess or hallucinate.
# 4. Always reference file names when possible.

# ANSWERING STYLE:
# - If the question is HIGH-LEVEL (e.g., "what is the project about"):
#   → Give a short summary (2–4 lines max).
# - If the question is DETAILED (e.g., "how does X work"):
#   → Provide a detailed explanation with steps and references.
# - Be clear, precise, and structured.
# """


# def build_prompt(query: str, chunks: List[Dict[str, Any]]) -> str:
#     """
#     Construct the final prompt containing system instruction,
#     retrieved code snippets, and user query.
#     """

#     context_str = ""

#     MAX_CONTEXT_CHARS = 4000  # prevents token overflow

#     for idx, chunk in enumerate(chunks, 1):
#         meta = chunk.get("metadata", {})
#         file_name = meta.get("file_name", "Unknown File")
#         path = meta.get("path", "Unknown Path")
#         entity = meta.get("entity_name", "Unknown Entity")
#         text = chunk.get("text", "")

#         # limit context size
#         if len(context_str) + len(text) > MAX_CONTEXT_CHARS:
#             break

#         context_str += f"--- Snippet {idx} ---\n"
#         context_str += f"File: {path} ({file_name})\n"
#         context_str += f"Entity: {entity}\n"
#         context_str += f"Code:\n```\n{text}\n```\n\n"

#     prompt = f"{SYSTEM_INSTRUCTION}\n\n"

#     prompt += "Here is the relevant code context from the repository:\n\n"
#     prompt += context_str

#     prompt += f"User Question: {query}\n\n"

#     prompt += """
# Answer the question following the rules above.

# - Start with a direct answer.
# - Keep it concise unless detail is required.
# - Mention file names when relevant.
# """

#     return prompt