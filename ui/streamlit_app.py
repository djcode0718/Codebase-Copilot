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

import sys
import os

# 🔥 Add project root to Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
from app.services.qa_service import handle_user_query
from app.memory.chat_memory import ChatMemory

# ------------------ PAGE CONFIG ------------------
st.set_page_config(
    page_title="Codebase Copilot",
    layout="wide",
    page_icon="💬"
)

# ------------------ CUSTOM STYLING ------------------
st.markdown("""
<style>
/* Main background */
.block-container {
    padding-top: 2rem;
}

/* Chat bubbles */
[data-testid="stChatMessage"] {
    border-radius: 12px;
    padding: 10px 14px;
    margin-bottom: 8px;
}

/* User message */
[data-testid="stChatMessage"]:has(div[data-testid="chatAvatarIcon-user"]) {
    background-color: #1e1e1e;
}

/* Assistant message */
[data-testid="stChatMessage"]:has(div[data-testid="chatAvatarIcon-assistant"]) {
    background-color: #111;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background-color: #0e1117;
}

/* Buttons */
.stButton>button {
    border-radius: 8px;
    width: 100%;
}

/* Input */
.stTextInput>div>div>input {
    border-radius: 8px;
}

/* Title */
h1 {
    font-size: 28px;
}
</style>
""", unsafe_allow_html=True)

# ------------------ STATE ------------------
if "memory" not in st.session_state:
    st.session_state.memory = ChatMemory(max_turns=6)

if "index_name" not in st.session_state:
    st.session_state.index_name = None

# ------------------ SIDEBAR ------------------
with st.sidebar:
    st.title("⚙️ Setup")

    repo_input = st.text_input(
        "Repository",
        placeholder="GitHub URL or local path"
    )

    if st.button("🚀 Process Repository"):
        if repo_input:
            from app.services.repo_service import process_repository

            with st.spinner("Processing repository..."):
                index_name = process_repository(repo_input)
                st.session_state.index_name = index_name

            st.success("Repository indexed successfully!")
        else:
            st.warning("Please enter a valid repo.")

    st.divider()

    if st.session_state.index_name:
        st.success("✅ Ready")
        st.caption(f"Index: `{st.session_state.index_name}`")

    if st.button("🧹 Clear Chat"):
        st.session_state.memory = ChatMemory(max_turns=6)
        st.rerun()

# ------------------ MAIN HEADER ------------------
st.title("💬 Codebase Copilot")
st.caption("Ask questions about your codebase intelligently")

# ------------------ EMPTY STATE ------------------
if not st.session_state.index_name:
    st.info("👈 Start by processing a repository from the sidebar.")
    st.stop()

# ------------------ CHAT DISPLAY ------------------
chat_container = st.container()

with chat_container:
    for msg in st.session_state.memory.get_history():
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# ------------------ INPUT ------------------
user_query = st.chat_input("Ask something about the codebase...")

if user_query:
    # Display user message
    with st.chat_message("user"):
        st.markdown(user_query)

    # Assistant response with loader
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = handle_user_query(
                user_query,
                st.session_state.index_name,
                memory=st.session_state.memory
            )
        st.markdown(response)