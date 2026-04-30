import os
import sys

# Add the root project directory to the python path so we can import 'app'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from app.services.repo_service import process_repository
from app.services.qa_service import handle_user_query

st.set_page_config(page_title="Codebase Copilot", page_icon="🤖", layout="wide")

st.title("🤖 Codebase Copilot")
st.markdown("Ask natural language questions about your GitHub repository or local codebase.")

# Sidebar for repo loading
with st.sidebar:
    st.header("1. Load Repository")
    source = st.text_input("GitHub URL or Local Path", placeholder="https://github.com/user/repo")
    
    if st.button("Process Repo"):
        if not source:
            st.warning("Please enter a repository source.")
        else:
            with st.spinner("Processing repository... This may take a few minutes depending on the size."):
                index_name = process_repository(source)
                if index_name:
                    st.session_state["index_name"] = index_name
                    st.success(f"Repository processed successfully! Index: {index_name}")
                else:
                    st.error("Failed to process repository. Check logs for details.")
                    
# Main area for QA
st.header("2. Ask Questions")
query = st.text_input("What would you like to know about the codebase?")

if st.button("Ask"):
    if "index_name" not in st.session_state:
        st.warning("Please process a repository first.")
    elif not query:
        st.warning("Please enter a question.")
    else:
        with st.spinner("Thinking..."):
            response = handle_user_query(query, st.session_state["index_name"])
            st.markdown("### Answer:")
            st.markdown(response)
