import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llama_index.core import Settings
from app.llm.llm_client import get_llm, get_embed_model
from app.services.repo_service import process_repository
from app.services.qa_service import handle_user_query


def main():
    # Configure LlamaIndex global settings before anything else
    Settings.llm = get_llm()
    Settings.embed_model = get_embed_model()

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  Codebase Copilot — CLI")
    print("  Hybrid BM25 + Dense · nomic-embed-text")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    source = input("\nEnter GitHub URL or local path: ").strip()

    print("\nIndexing repository (first run embeds all files — may take 1-2 min)...")
    index_name = process_repository(source)

    if not index_name:
        print("Failed to process repository. Check logs above.")
        return

    print(f"\nReady. Index: '{index_name}'")
    print("Type 'quit' to exit.\n")

    chat_engine = None
    memory = None

    while True:
        query = input("Ask: ").strip()
        if query.lower() in ("quit", "exit", "q"):
            break
        if not query:
            continue

        print("Thinking...\n")
        response, chat_engine, memory, _ = handle_user_query(
            query=query,
            index_name=index_name,
            chat_engine=chat_engine,
            memory=memory,
        )

        print("─" * 50)
        print(response)
        print("─" * 50 + "\n")


if __name__ == "__main__":
    main()