# import os
# import time
# from app.utils.logger import get_logger

# logger = get_logger(__name__)

# # Load provider from env
# LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").lower()


# # =========================
# # GEMINI
# # =========================
# def generate_gemini(prompt: str) -> str:
#     try:
#         import google.generativeai as genai

#         genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

#         model = genai.GenerativeModel("gemini-1.5-flash-latest")

#         response = model.generate_content(prompt)

#         return response.text

#     except Exception as e:
#         return f"Gemini error: {e}"


# # =========================
# # GROQ (FAST + FREE)
# # =========================
# def generate_groq(prompt: str) -> str:
#     try:
#         import requests
#         api_key = os.getenv("GROQ_API_KEY")

#         url = "https://api.groq.com/openai/v1/chat/completions"

#         headers = {
#             "Authorization": f"Bearer {api_key}",
#             "Content-Type": "application/json"
#         }

#         data = {
#             "model": "openai/gpt-oss-20b",
#             "messages": [{"role": "user", "content": prompt}]
#         }

#         response = requests.post(url, headers=headers, json=data)
#         result = response.json()

#         # DEBUG print (optional)
#         # print(result)

#         if "choices" not in result:
#             return f"Groq API Error: {result}"

#         return result["choices"][0]["message"]["content"]

#     except Exception as e:
#         return f"Groq error: {e}"


# # =========================
# # OPENAI
# # =========================
# def generate_openai(prompt: str) -> str:
#     try:
#         from openai import OpenAI

#         client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

#         response = client.chat.completions.create(
#             model="gpt-4o-mini",
#             messages=[{"role": "user", "content": prompt}]
#         )

#         return response.choices[0].message.content

#     except Exception as e:
#         logger.error(f"OpenAI error: {e}")
#         return f"OpenAI error: {e}"


# # =========================
# # OLLAMA (LOCAL)
# # =========================
# def generate_ollama(prompt: str) -> str:
#     try:
#         import requests

#         model = os.getenv("OLLAMA_MODEL", "llama3:8b")

#         response = requests.post(
#             "http://localhost:11434/api/generate",
#             json={
#                 "model": model,
#                 "prompt": prompt,
#                 "stream": False
#             }
#         )

#         return response.json()["response"]

#     except Exception as e:
#         logger.error(f"Ollama error: {e}")
#         return f"Ollama error: {e}"

# def generate_summary(prompt: str) -> str:
#     try:
#         import requests

#         model = os.getenv("OLLAMA_MODEL", "phi3:mini")

#         response = requests.post(
#             "http://localhost:11434/api/generate",
#             json={
#                 "model": model,
#                 "prompt": prompt,
#                 "stream": False
#             }
#         )

#         return response.json()["response"]

#     except Exception as e:
#         logger.error(f"Ollama error: {e}")
#         return f"Ollama error: {e}"


# # =========================
# # MAIN ROUTER
# # =========================
# def generate_response(prompt: str) -> str:
#     """
#     Unified LLM interface
#     """

#     logger.info(f"Using LLM provider: {LLM_PROVIDER}")

#     # Retry logic (for robustness)
#     for attempt in range(3):
#         try:
#             if LLM_PROVIDER == "gemini":
#                 return generate_gemini(prompt)

#             elif LLM_PROVIDER == "groq":
#                 return generate_groq(prompt)

#             elif LLM_PROVIDER == "openai":
#                 return generate_openai(prompt)

#             elif LLM_PROVIDER == "ollama":
#                 return generate_ollama(prompt)

#             else:
#                 return f"Unknown LLM_PROVIDER: {LLM_PROVIDER}"

#         except Exception as e:
#             if attempt < 2:
#                 time.sleep(2)
#             else:
#                 return f"LLM failed after retries: {e}"

# import os
# import time
# from app.utils.logger import get_logger

# logger = get_logger(__name__)

# LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").lower()


# def generate_gemini(prompt: str) -> str:
#     try:
#         import google.generativeai as genai
#         genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
#         model = genai.GenerativeModel("gemini-1.5-flash-latest")
#         response = model.generate_content(prompt)
#         return response.text
#     except Exception as e:
#         return f"Gemini error: {e}"


# def generate_groq(prompt: str) -> str:
#     try:
#         import requests
#         url = "https://api.groq.com/openai/v1/chat/completions"
#         headers = {
#             "Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}",
#             "Content-Type": "application/json"
#         }
#         data = {
#             # "model": "llama3-8b-8192",
#             "model": "openai/gpt-oss-20b",
#             "messages": [{"role": "user", "content": prompt}]
#         }
#         response = requests.post(url, headers=headers, json=data)
#         result = response.json()
#         if "choices" not in result:
#             return f"Groq API error: {result}"
#         return result["choices"][0]["message"]["content"]
#     except Exception as e:
#         return f"Groq error: {e}"


# def generate_openai(prompt: str) -> str:
#     try:
#         from openai import OpenAI
#         client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
#         response = client.chat.completions.create(
#             model="gpt-4o-mini",
#             messages=[{"role": "user", "content": prompt}]
#         )
#         return response.choices[0].message.content
#     except Exception as e:
#         logger.error(f"OpenAI error: {e}")
#         return f"OpenAI error: {e}"


# def generate_ollama(prompt: str) -> str:
#     try:
#         import requests
#         model = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
#         response = requests.post(
#             "http://localhost:11434/api/generate",
#             json={"model": model, "prompt": prompt, "stream": False}
#         )
#         return response.json()["response"]
#     except Exception as e:
#         logger.error(f"Ollama error: {e}")
#         return f"Ollama error: {e}"


# def generate_summary(prompt: str) -> str:
#     """
#     Used by file_map_builder for file-level summarization.
#     Runs locally via Ollama — phi3:mini is fast and light on M4.
#     """
#     try:
#         import requests
#         model = os.getenv("OLLAMA_MODEL", "phi3:mini")
#         response = requests.post(
#             "http://localhost:11434/api/generate",
#             json={"model": model, "prompt": prompt, "stream": False}
#         )
#         return response.json()["response"]
#     except Exception as e:
#         logger.error(f"Ollama summary error: {e}")
#         return f"Ollama error: {e}"


# def generate_response(prompt: str) -> str:
#     """
#     Unified LLM interface with 3-attempt retry logic.
#     Provider is selected via LLM_PROVIDER env variable.
#     """
#     logger.info(f"Using LLM provider: {LLM_PROVIDER}")

#     for attempt in range(3):
#         try:
#             if LLM_PROVIDER == "gemini":
#                 return generate_gemini(prompt)
#             elif LLM_PROVIDER == "groq":
#                 return generate_groq(prompt)
#             elif LLM_PROVIDER == "openai":
#                 return generate_openai(prompt)
#             elif LLM_PROVIDER == "ollama":
#                 return generate_ollama(prompt)
#             else:
#                 return f"Unknown LLM_PROVIDER: {LLM_PROVIDER}"
#         except Exception as e:
#             logger.warning(f"LLM attempt {attempt + 1} failed: {e}")
#             if attempt < 2:
#                 time.sleep(2)
#             else:
#                 return f"LLM failed after 3 attempts: {e}"

# """
# llm_client.py
# ─────────────
# Returns LlamaIndex-compatible LLM and embedding model instances.
# The rest of the pipeline (qa_service, index_builder) imports from here
# so the provider can be swapped via .env without touching any other file.
# """

# import os
# from app.config import (
#     LLM_PROVIDER,
#     OLLAMA_BASE_URL,
#     OLLAMA_LLM_MODEL,
#     OLLAMA_EMBED_MODEL,
#     GEMINI_API_KEY,
#     GROQ_API_KEY,
#     OPENAI_API_KEY,
# )
# from app.utils.logger import get_logger

# logger = get_logger(__name__)


# def get_llm():
#     """
#     Returns a LlamaIndex LLM instance based on LLM_PROVIDER env var.
#     Default: Ollama (fully local, no API key needed).
#     """
#     """
#     Returns LLM based on config:
#     - USE_EVAL_LLM=True  → Groq fast model
#     - else               → normal provider
#     """

#     logger.info(f"Loading LLM — provider: {LLM_PROVIDER}")

#     if LLM_PROVIDER == "ollama":
#         from llama_index.llms.ollama import Ollama
#         return Ollama(
#             model=OLLAMA_LLM_MODEL,
#             base_url=OLLAMA_BASE_URL,
#             request_timeout=120.0,
#         )

#     elif LLM_PROVIDER == "gemini":
#         from llama_index.llms.gemini import Gemini
#         return Gemini(
#             model="models/gemini-1.5-flash",
#             api_key=GEMINI_API_KEY,
#         )

#     elif LLM_PROVIDER == "groq":
#         from llama_index.llms.groq import Groq
#         return Groq(
#             model="openai/gpt-oss-20b",
#             api_key=GROQ_API_KEY,
#         )

#     elif LLM_PROVIDER == "openai":
#         from llama_index.llms.openai import OpenAI
#         return OpenAI(
#             model="gpt-4o-mini",
#             api_key=OPENAI_API_KEY,
#         )

#     else:
#         raise ValueError(f"Unknown LLM_PROVIDER: '{LLM_PROVIDER}'. "
#                          f"Valid options: ollama, gemini, groq, openai")


# def get_embed_model():
#     """
#     Returns a LlamaIndex embedding model.
#     Always uses nomic-embed-text via local Ollama — no API cost,
#     runs fast on M4 unified memory (768-dim dense embeddings).
#     """
#     from llama_index.embeddings.ollama import OllamaEmbedding
#     logger.info(f"Loading embedding model: {OLLAMA_EMBED_MODEL} via Ollama")
#     return OllamaEmbedding(
#         model_name=OLLAMA_EMBED_MODEL,
#         base_url=OLLAMA_BASE_URL,
#     )


"""
llm_client.py
─────────────
Returns LlamaIndex-compatible LLM and embedding model instances.
The rest of the pipeline (qa_service, index_builder, query_router, etc.)
imports from here — so the provider can be swapped via .env without
touching any other file.

── FAST LLM TOGGLE ──────────────────────────────────────────────────────────
Set USE_FAST_LLM=true in .env to switch the entire project to Groq cloud LLM.

  USE_FAST_LLM=false (default) → uses LLM_PROVIDER (e.g. local Ollama)
  USE_FAST_LLM=true            → uses Groq with GROQ_FAST_MODEL

  GROQ_FAST_MODEL options (set in .env):
    "llama-3.3-70b-versatile"  → better quality,  ~2-3s latency  (default, good for evals)
    "llama-3.1-8b-instant"   → faster,          ~0.5-1s latency (good for quick demos)

Embedding model is ALWAYS local Ollama (nomic-embed-text) — never affected
by this toggle. Only the generative LLM switches.
─────────────────────────────────────────────────────────────────────────────
"""

import os
from app.config import (
    USE_FAST_LLM,
    GROQ_FAST_MODEL,
    LLM_PROVIDER,
    OLLAMA_BASE_URL,
    OLLAMA_LLM_MODEL,
    OLLAMA_EMBED_MODEL,
    GEMINI_API_KEY,
    GROQ_API_KEY,
    OPENAI_API_KEY,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


def get_llm():
    """
    Returns a LlamaIndex LLM instance.

    Resolution order:
      1. USE_FAST_LLM=true  → Groq (GROQ_FAST_MODEL), ignores LLM_PROVIDER
      2. USE_FAST_LLM=false → LLM_PROVIDER (ollama / gemini / groq / openai)

    This is the single point of control for the generative LLM across the
    entire project. Every component that needs an LLM calls this function
    (or picks it up via Settings.llm set in repo_service / main).
    """

    # ── FAST LLM ON ───────────────────────────────────────────────────────────
    # To disable: set USE_FAST_LLM=false in .env
    if USE_FAST_LLM:
        logger.info(f"[FAST LLM] Using Groq — model: {GROQ_FAST_MODEL}")
        from llama_index.llms.groq import Groq
        return Groq(
            model=GROQ_FAST_MODEL,
            api_key=GROQ_API_KEY,
        )
    # ── FAST LLM OFF ──────────────────────────────────────────────────────────

    # Normal provider path — controlled by LLM_PROVIDER in .env
    logger.info(f"Loading LLM — provider: {LLM_PROVIDER}")

    if LLM_PROVIDER == "ollama":
        from llama_index.llms.ollama import Ollama
        return Ollama(
            model=OLLAMA_LLM_MODEL,
            base_url=OLLAMA_BASE_URL,
            request_timeout=120.0,
        )

    elif LLM_PROVIDER == "gemini":
        from llama_index.llms.gemini import Gemini
        return Gemini(
            model="models/gemini-1.5-flash",
            api_key=GEMINI_API_KEY,
        )

    elif LLM_PROVIDER == "groq":
        from llama_index.llms.groq import Groq
        return Groq(
            model="openai/gpt-oss-20b",
            api_key=GROQ_API_KEY,
        )

    elif LLM_PROVIDER == "openai":
        from llama_index.llms.openai import OpenAI
        return OpenAI(
            model="gpt-4o-mini",
            api_key=OPENAI_API_KEY,
        )

    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER: '{LLM_PROVIDER}'. "
            f"Valid options: ollama, gemini, groq, openai"
        )


def get_embed_model():
    """
    Returns a LlamaIndex embedding model.

    Always uses nomic-embed-text via local Ollama — regardless of USE_FAST_LLM
    or LLM_PROVIDER. Embedding stays local: no API cost, no latency variance,
    runs fast on M4 unified memory (768-dim dense embeddings).

    This is intentional: switching the generative LLM should never affect
    how chunks are embedded or how the index is built.
    """
    from llama_index.embeddings.ollama import OllamaEmbedding
    logger.info(f"Loading embedding model: {OLLAMA_EMBED_MODEL} via Ollama")
    return OllamaEmbedding(
        model_name=OLLAMA_EMBED_MODEL,
        base_url=OLLAMA_BASE_URL,
    )


def generate_summary(prompt: str) -> str:
    """
    Used by file_map_builder for file-level summarization at index time.
    Respects USE_FAST_LLM — if the toggle is on, uses Groq for faster
    indexing too. Falls back gracefully on error.
    """
    try:
        llm = get_llm()
        response = llm.complete(prompt)
        return str(response).strip()
    except Exception as e:
        logger.error(f"generate_summary failed: {e}")
        return ""