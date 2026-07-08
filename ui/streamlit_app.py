# import sys
# import os

# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# import streamlit as st
# from llama_index.core import Settings
# from llama_index.core.memory import ChatMemoryBuffer

# from app.services.qa_service import handle_user_query
# from app.services.repo_service import process_repository
# from app.retrieval.query_router import QueryMode
# from app.llm.llm_client import get_llm, get_embed_model

# # ─── Page config ──────────────────────────────────────────────────────────────
# st.set_page_config(
#     page_title="Codebase Copilot",
#     layout="wide",
#     page_icon="💬"
# )

# st.markdown("""
# <style>
# .block-container { padding-top: 2rem; }
# [data-testid="stChatMessage"] {
#     border-radius: 12px;
#     padding: 10px 14px;
#     margin-bottom: 8px;
# }
# section[data-testid="stSidebar"] { background-color: #0e1117; }
# .stButton>button { border-radius: 8px; width: 100%; }
# .stTextInput>div>div>input { border-radius: 8px; }
# h1 { font-size: 28px; }
# .mode-badge-code {
#     display: inline-block;
#     background: #1a3a5c;
#     color: #5dade2;
#     font-size: 11px;
#     padding: 2px 8px;
#     border-radius: 10px;
#     margin-bottom: 6px;
#     font-family: monospace;
# }
# .mode-badge-arch {
#     display: inline-block;
#     background: #1a3a2a;
#     color: #58d68d;
#     font-size: 11px;
#     padding: 2px 8px;
#     border-radius: 10px;
#     margin-bottom: 6px;
#     font-family: monospace;
# }
# </style>
# """, unsafe_allow_html=True)

# # ─── Session state ─────────────────────────────────────────────────────────────
# defaults = {
#     "index_name":      None,
#     "chat_engine":     None,
#     "memory":          None,
#     "last_mode":       None,
#     "display_history": [],
# }
# for k, v in defaults.items():
#     if k not in st.session_state:
#         st.session_state[k] = v

# # ─── Sidebar ──────────────────────────────────────────────────────────────────
# with st.sidebar:
#     st.title("⚙️ Setup")

#     repo_input = st.text_input(
#         "Repository",
#         placeholder="GitHub URL or local path"
#     )

#     if st.button("🚀 Process Repository"):
#         if repo_input:
#             Settings.llm         = get_llm()
#             Settings.embed_model = get_embed_model()

#             with st.spinner("Indexing repository — first run builds embeddings + context doc..."):
#                 index_name = process_repository(repo_input)

#             if index_name:
#                 st.session_state.index_name      = index_name
#                 st.session_state.chat_engine     = None
#                 st.session_state.last_mode       = None
#                 st.session_state.memory          = ChatMemoryBuffer.from_defaults(token_limit=4096)
#                 st.session_state.display_history = []
#                 st.success("Repository indexed!")
#             else:
#                 st.error("Indexing failed — check terminal logs.")
#         else:
#             st.warning("Please enter a repo URL or local path.")

#     st.divider()

#     if st.session_state.index_name:
#         st.success("✅ Ready")
#         st.caption(f"Index: `{st.session_state.index_name}`")
#         provider = os.getenv("LLM_PROVIDER", "ollama").upper()
#         embed    = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
#         colbert  = os.getenv("USE_COLBERT", "true")
#         st.caption(f"LLM: `{provider}` · Embed: `{embed}`")
#         st.caption(f"ColBERT reranking: `{'ON' if colbert == 'true' else 'OFF'}`")

#     st.divider()

#     with st.expander("Query modes"):
#         st.markdown("""
# **🔵 Code Lookup**
# Specific questions about functions, classes, files.
# Uses BM25 + dense hybrid retrieval.

# **🟢 Architectural**
# Broad questions: limitations, improvements, design.
# Uses dense retrieval + codebase summary context.
#         """)

#     if st.button("🧹 Clear Chat"):
#         st.session_state.display_history = []
#         st.session_state.chat_engine     = None
#         st.session_state.last_mode       = None
#         st.session_state.memory          = ChatMemoryBuffer.from_defaults(token_limit=4096)
#         st.rerun()

# # ─── Main ──────────────────────────────────────────────────────────────────────
# st.title("💬 Codebase Copilot")
# st.caption("Hybrid BM25 + Dense · ColBERT reranking · Dual-mode routing · nomic-embed-text")

# if not st.session_state.index_name:
#     st.info("👈 Start by processing a repository from the sidebar.")
#     st.stop()

# # Display history
# for msg in st.session_state.display_history:
#     with st.chat_message(msg["role"]):
#         if msg["role"] == "assistant" and "mode" in msg:
#             mode = msg["mode"]
#             if mode == QueryMode.CODE_LOOKUP.value:
#                 st.markdown('<span class="mode-badge-code">🔵 code lookup</span>', unsafe_allow_html=True)
#             else:
#                 st.markdown('<span class="mode-badge-arch">🟢 architectural</span>', unsafe_allow_html=True)
#         st.markdown(msg["content"])

# # Input
# user_query = st.chat_input("Ask something about the codebase...")

# if user_query:
#     with st.chat_message("user"):
#         st.markdown(user_query)
#     st.session_state.display_history.append({"role": "user", "content": user_query})

#     with st.chat_message("assistant"):
#         with st.spinner("Thinking..."):
#             if Settings.llm is None:
#                 Settings.llm = get_llm()
#             if Settings.embed_model is None:
#                 Settings.embed_model = get_embed_model()

#             response, chat_engine, memory, query_mode = handle_user_query(
#                 query       = user_query,
#                 index_name  = st.session_state.index_name,
#                 chat_engine = st.session_state.chat_engine,
#                 memory      = st.session_state.memory,
#                 last_mode   = st.session_state.last_mode,
#             )

#         st.session_state.chat_engine = chat_engine
#         st.session_state.memory      = memory
#         st.session_state.last_mode   = query_mode

#         # Show mode badge
#         if query_mode == QueryMode.CODE_LOOKUP:
#             st.markdown('<span class="mode-badge-code">🔵 code lookup</span>', unsafe_allow_html=True)
#         else:
#             st.markdown('<span class="mode-badge-arch">🟢 architectural</span>', unsafe_allow_html=True)

#         st.markdown(response)

#     st.session_state.display_history.append({
#         "role":    "assistant",
#         "content": response,
#         "mode":    query_mode.value,
#     })

import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
from llama_index.core import Settings
from llama_index.core.memory import ChatMemoryBuffer

from app.llm.llm_client import configure_llamaindex_settings
from app.services.repo_service import process_repository
from app.services.qa_service import handle_user_query
from app.retrieval.query_router import QueryMode

# ─── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Codebase Copilot",
    layout="wide",
    page_icon="💬"
)

st.markdown("""
<style>
.block-container { padding-top: 2rem; }
[data-testid="stChatMessage"] {
    border-radius: 12px;
    padding: 10px 14px;
    margin-bottom: 8px;
}
section[data-testid="stSidebar"] { background-color: #0e1117; }
.stButton>button { border-radius: 8px; width: 100%; }
.stTextInput>div>div>input { border-radius: 8px; }
h1 { font-size: 28px; }
.mode-badge-code {
    display: inline-block;
    background: #1a3a5c;
    color: #5dade2;
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 10px;
    margin-bottom: 6px;
    font-family: monospace;
}
.mode-badge-arch {
    display: inline-block;
    background: #1a3a2a;
    color: #58d68d;
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 10px;
    margin-bottom: 6px;
    font-family: monospace;
}
</style>
""", unsafe_allow_html=True)

# ─── Session state ─────────────────────────────────────────────────────────────
defaults = {
    "index_name":      None,
    "chat_engine":     None,
    "memory":          None,
    "last_mode":       None,
    "display_history": [],
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Setup")

    repo_input = st.text_input(
        "Repository",
        placeholder="GitHub URL or local path"
    )

    if st.button("🚀 Process Repository"):
        if repo_input:
            # FIX: use configure_llamaindex_settings() unconditionally.
            # The old pattern `if Settings.embed_model is None` was silently
            # skipped because LlamaIndex auto-sets embed_model=OpenAI at import
            # time when OPENAI_API_KEY is present. This override forces Ollama.
            configure_llamaindex_settings()

            with st.spinner("Indexing repository — first run builds embeddings + context doc..."):
                index_name = process_repository(repo_input)

            if index_name:
                st.session_state.index_name      = index_name
                st.session_state.chat_engine     = None
                st.session_state.last_mode       = None
                st.session_state.memory          = ChatMemoryBuffer.from_defaults(token_limit=4096)
                st.session_state.display_history = []
                st.success("Repository indexed!")
            else:
                st.error("Indexing failed — check terminal logs.")
        else:
            st.warning("Please enter a repo URL or local path.")

    st.divider()

    if st.session_state.index_name:
        st.success("✅ Ready")
        st.caption(f"Index: `{st.session_state.index_name}`")
        provider = os.getenv("LLM_PROVIDER", "ollama").upper()
        embed    = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
        colbert  = os.getenv("USE_COLBERT", "true")
        st.caption(f"LLM: `{provider}` · Embed: `{embed}`")
        st.caption(f"ColBERT reranking: `{'ON' if colbert == 'true' else 'OFF'}`")

    st.divider()

    with st.expander("Query modes"):
        st.markdown("""
**🔵 Code Lookup**
Specific questions about functions, classes, files.
Uses BM25 + dense hybrid retrieval.

**🟢 Architectural**
Broad questions: limitations, improvements, design.
Uses dense retrieval + codebase summary context.
        """)

    if st.button("🧹 Clear Chat"):
        st.session_state.display_history = []
        st.session_state.chat_engine     = None
        st.session_state.last_mode       = None
        st.session_state.memory          = ChatMemoryBuffer.from_defaults(token_limit=4096)
        st.rerun()

# ─── Main ──────────────────────────────────────────────────────────────────────
st.title("💬 Codebase Copilot")
st.caption("Hybrid BM25 + Dense · ColBERT reranking · Dual-mode routing · nomic-embed-text")

if not st.session_state.index_name:
    st.info("👈 Start by processing a repository from the sidebar.")
    st.stop()

# Display history
for msg in st.session_state.display_history:
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant" and "mode" in msg:
            mode = msg["mode"]
            if mode == QueryMode.CODE_LOOKUP.value:
                st.markdown('<span class="mode-badge-code">🔵 code lookup</span>', unsafe_allow_html=True)
            else:
                st.markdown('<span class="mode-badge-arch">🟢 architectural</span>', unsafe_allow_html=True)
        st.markdown(msg["content"])

# Input
user_query = st.chat_input("Ask something about the codebase...")

if user_query:
    with st.chat_message("user"):
        st.markdown(user_query)
    st.session_state.display_history.append({"role": "user", "content": user_query})

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            # FIX: use configure_llamaindex_settings() unconditionally — same
            # reason as above. The if-None guards were bypassed by OpenAI auto-init.
            configure_llamaindex_settings()

            response, chat_engine, memory, query_mode = handle_user_query(
                query       = user_query,
                index_name  = st.session_state.index_name,
                chat_engine = st.session_state.chat_engine,
                memory      = st.session_state.memory,
                last_mode   = st.session_state.last_mode,
            )

        st.session_state.chat_engine = chat_engine
        st.session_state.memory      = memory
        st.session_state.last_mode   = query_mode

        if query_mode == QueryMode.CODE_LOOKUP:
            st.markdown('<span class="mode-badge-code">🔵 code lookup</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span class="mode-badge-arch">🟢 architectural</span>', unsafe_allow_html=True)

        st.markdown(response)

    st.session_state.display_history.append({
        "role":    "assistant",
        "content": response,
        "mode":    query_mode.value,
    })