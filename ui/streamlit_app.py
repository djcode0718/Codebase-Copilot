# import os
# import sys

# # Add the root project directory to the python path so we can import 'app'
# sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# import streamlit as st
# from app.services.repo_service import process_repository
# from app.services.qa_service import handle_user_query

# st.set_page_config(page_title="Codebase Copilot", page_icon="🤖", layout="wide")

# st.title("🤖 Codebase Copilot")
# st.markdown("Ask natural language questions about your GitHub repository or local codebase.")

# # Sidebar for repo loading
# with st.sidebar:
#     st.header("1. Load Repository")
#     source = st.text_input("GitHub URL or Local Path", placeholder="https://github.com/user/repo")
    
#     if st.button("Process Repo"):
#         if not source:
#             st.warning("Please enter a repository source.")
#         else:
#             with st.spinner("Processing repository... This may take a few minutes depending on the size."):
#                 index_name = process_repository(source)
#                 if index_name:
#                     st.session_state["index_name"] = index_name
#                     st.success(f"Repository processed successfully! Index: {index_name}")
#                 else:
#                     st.error("Failed to process repository. Check logs for details.")
                    
# # Main area for QA
# st.header("2. Ask Questions")
# query = st.text_input("What would you like to know about the codebase?")

# if st.button("Ask"):
#     if "index_name" not in st.session_state:
#         st.warning("Please process a repository first.")
#     elif not query:
#         st.warning("Please enter a question.")
#     else:
#         with st.spinner("Thinking..."):
#             response = handle_user_query(query, st.session_state["index_name"])
#             st.markdown("### Answer:")
#             st.markdown(response)




# import sys
# import os

# # 🔥 Add project root to Python path
# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# import streamlit as st
# from app.services.qa_service import handle_user_query
# from app.memory.chat_memory import ChatMemory

# st.set_page_config(page_title="Codebase Copilot", layout="wide")

# st.title("💬 Codebase Copilot")

# # 🔹 Session state for memory
# if "memory" not in st.session_state:
#     st.session_state.memory = ChatMemory(max_turns=6)

# if "index_name" not in st.session_state:
#     st.session_state.index_name = None

# # 🔹 Input for repo (one-time)
# repo_input = st.text_input("Enter GitHub repo URL or local path")

# if st.button("Process Repo"):
#     from app.services.repo_service import process_repository
#     index_name = process_repository(repo_input)
#     st.session_state.index_name = index_name
#     st.success(f"Processed: {index_name}")

# # 🔹 Chat UI
# if st.session_state.index_name:
#     # Display history
#     for msg in st.session_state.memory.get_history():
#         with st.chat_message(msg["role"]):
#             st.markdown(msg["content"])

#     # Input box
#     user_query = st.chat_input("Ask about the codebase...")

#     if user_query:
#         with st.chat_message("user"):
#             st.markdown(user_query)

#         response = handle_user_query(
#             user_query,
#             st.session_state.index_name,
#             memory=st.session_state.memory
#         )

#         with st.chat_message("assistant"):
#             st.markdown(response)

# import sys
# import os

# # 🔥 Add project root to Python path
# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# import streamlit as st
# from app.services.qa_service import handle_user_query
# from app.memory.chat_memory import ChatMemory

# # ------------------ PAGE CONFIG ------------------
# st.set_page_config(
#     page_title="Codebase Copilot",
#     layout="wide",
#     page_icon="💬"
# )

# # ------------------ CUSTOM STYLING ------------------
# st.markdown("""
# <style>
# /* Main background */
# .block-container {
#     padding-top: 2rem;
# }

# /* Chat bubbles */
# [data-testid="stChatMessage"] {
#     border-radius: 12px;
#     padding: 10px 14px;
#     margin-bottom: 8px;
# }

# /* User message */
# [data-testid="stChatMessage"]:has(div[data-testid="chatAvatarIcon-user"]) {
#     background-color: #1e1e1e;
# }

# /* Assistant message */
# [data-testid="stChatMessage"]:has(div[data-testid="chatAvatarIcon-assistant"]) {
#     background-color: #111;
# }

# /* Sidebar */
# section[data-testid="stSidebar"] {
#     background-color: #0e1117;
# }

# /* Buttons */
# .stButton>button {
#     border-radius: 8px;
#     width: 100%;
# }

# /* Input */
# .stTextInput>div>div>input {
#     border-radius: 8px;
# }

# /* Title */
# h1 {
#     font-size: 28px;
# }
# </style>
# """, unsafe_allow_html=True)

# # ------------------ STATE ------------------
# if "memory" not in st.session_state:
#     st.session_state.memory = ChatMemory(max_turns=6)

# if "index_name" not in st.session_state:
#     st.session_state.index_name = None

# # ------------------ SIDEBAR ------------------
# with st.sidebar:
#     st.title("⚙️ Setup")

#     repo_input = st.text_input(
#         "Repository",
#         placeholder="GitHub URL or local path"
#     )

#     if st.button("🚀 Process Repository"):
#         if repo_input:
#             from app.services.repo_service import process_repository

#             with st.spinner("Processing repository..."):
#                 index_name = process_repository(repo_input)
#                 st.session_state.index_name = index_name

#             st.success("Repository indexed successfully!")
#         else:
#             st.warning("Please enter a valid repo.")

#     st.divider()

#     if st.session_state.index_name:
#         st.success("✅ Ready")
#         st.caption(f"Index: `{st.session_state.index_name}`")

#     if st.button("🧹 Clear Chat"):
#         st.session_state.memory = ChatMemory(max_turns=6)
#         st.rerun()

# # ------------------ MAIN HEADER ------------------
# st.title("💬 Codebase Copilot")
# st.caption("Ask questions about your codebase intelligently")

# # ------------------ EMPTY STATE ------------------
# if not st.session_state.index_name:
#     st.info("👈 Start by processing a repository from the sidebar.")
#     st.stop()

# # ------------------ CHAT DISPLAY ------------------
# chat_container = st.container()

# with chat_container:
#     for msg in st.session_state.memory.get_history():
#         with st.chat_message(msg["role"]):
#             st.markdown(msg["content"])

# # ------------------ INPUT ------------------
# user_query = st.chat_input("Ask something about the codebase...")

# if user_query:
#     # Display user message
#     with st.chat_message("user"):
#         st.markdown(user_query)

#     # Assistant response with loader
#     with st.chat_message("assistant"):
#         with st.spinner("Thinking..."):
#             response = handle_user_query(
#                 user_query,
#                 st.session_state.index_name,
#                 memory=st.session_state.memory
#             )
#         st.markdown(response)

# import sys
# import os

# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# import streamlit as st
# from llama_index.core import Settings
# from llama_index.core.memory import ChatMemoryBuffer

# from app.services.qa_service import handle_user_query, build_chat_engine
# from app.services.repo_service import process_repository
# from app.llm.llm_client import get_llm, get_embed_model

# # ─── Page config ──────────────────────────────────────────────────────────────
# st.set_page_config(
#     page_title="Codebase Copilot",
#     layout="wide",
#     page_icon="💬"
# )

# # ─── Styling ──────────────────────────────────────────────────────────────────
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
# </style>
# """, unsafe_allow_html=True)

# # ─── Session state ─────────────────────────────────────────────────────────────
# if "index_name" not in st.session_state:
#     st.session_state.index_name = None

# if "chat_engine" not in st.session_state:
#     st.session_state.chat_engine = None

# if "memory" not in st.session_state:
#     st.session_state.memory = None

# # Store display history separately (LlamaIndex memory is token-based internally)
# if "display_history" not in st.session_state:
#     st.session_state.display_history = []

# # ─── Sidebar ──────────────────────────────────────────────────────────────────
# with st.sidebar:
#     st.title("⚙️ Setup")

#     repo_input = st.text_input(
#         "Repository",
#         placeholder="GitHub URL or local path"
#     )

#     if st.button("🚀 Process Repository"):
#         if repo_input:
#             # Configure LlamaIndex settings once at app startup
#             Settings.llm = get_llm()
#             Settings.embed_model = get_embed_model()

#             with st.spinner("Indexing repository — this may take a few minutes on first run..."):
#                 index_name = process_repository(repo_input)

#             if index_name:
#                 st.session_state.index_name = index_name
#                 # Reset chat engine so it's rebuilt against the new index
#                 st.session_state.chat_engine = None
#                 st.session_state.memory = ChatMemoryBuffer.from_defaults(token_limit=4096)
#                 st.session_state.display_history = []
#                 st.success("Repository indexed successfully!")
#             else:
#                 st.error("Indexing failed — check terminal logs for details.")
#         else:
#             st.warning("Please enter a repository URL or local path.")

#     st.divider()

#     if st.session_state.index_name:
#         st.success("✅ Ready")
#         st.caption(f"Index: `{st.session_state.index_name}`")

#         provider = os.getenv("LLM_PROVIDER", "ollama").upper()
#         embed = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
#         st.caption(f"LLM: `{provider}` · Embed: `{embed}`")

#     if st.button("🧹 Clear Chat"):
#         st.session_state.display_history = []
#         st.session_state.chat_engine = None
#         st.session_state.memory = ChatMemoryBuffer.from_defaults(token_limit=4096)
#         st.rerun()

# # ─── Main ──────────────────────────────────────────────────────────────────────
# st.title("💬 Codebase Copilot")
# st.caption("Hybrid BM25 + semantic search · nomic-embed-text · LlamaIndex")

# if not st.session_state.index_name:
#     st.info("👈 Start by processing a repository from the sidebar.")
#     st.stop()

# # Display conversation history
# for msg in st.session_state.display_history:
#     with st.chat_message(msg["role"]):
#         st.markdown(msg["content"])

# # Input
# user_query = st.chat_input("Ask something about the codebase...")

# if user_query:
#     # Show user message immediately
#     with st.chat_message("user"):
#         st.markdown(user_query)

#     st.session_state.display_history.append({"role": "user", "content": user_query})

#     with st.chat_message("assistant"):
#         with st.spinner("Thinking..."):
#             # Ensure LlamaIndex settings are loaded (handles page refresh)
#             if Settings.llm is None:
#                 Settings.llm = get_llm()
#             if Settings.embed_model is None:
#                 Settings.embed_model = get_embed_model()

#             response, chat_engine, memory = handle_user_query(
#                 query=user_query,
#                 index_name=st.session_state.index_name,
#                 chat_engine=st.session_state.chat_engine,
#                 memory=st.session_state.memory,
#             )

#         # Cache engine and memory for next turn
#         st.session_state.chat_engine = chat_engine
#         st.session_state.memory = memory

#         st.markdown(response)

#     st.session_state.display_history.append({"role": "assistant", "content": response})


import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
from llama_index.core import Settings
from llama_index.core.memory import ChatMemoryBuffer

from app.services.qa_service import handle_user_query
from app.services.repo_service import process_repository
from app.retrieval.query_router import QueryMode
from app.llm.llm_client import get_llm, get_embed_model

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
            Settings.llm         = get_llm()
            Settings.embed_model = get_embed_model()

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
            if Settings.llm is None:
                Settings.llm = get_llm()
            if Settings.embed_model is None:
                Settings.embed_model = get_embed_model()

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

        # Show mode badge
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