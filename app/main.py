import sys
import os

# Add root directory to python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.repo_service import process_repository
from app.services.qa_service import handle_user_query

def main():
    print("Welcome to Codebase Copilot CLI")
    source = input("Enter GitHub URL or local path: ")
    
    print("Processing repository...")
    index_name = process_repository(source)
    if not index_name:
        print("Failed to process repository.")
        return
        
    print(f"Repository indexed successfully. Index: {index_name}")
    
    while True:
        query = input("\\nAsk a question (or 'quit' to exit): ")
        if query.lower() in ['quit', 'exit', 'q']:
            break
            
        print("Thinking...")
        response = handle_user_query(query, index_name)
        print("\\nAnswer:")
        print("-" * 40)
        print(response)
        print("-" * 40)

if __name__ == "__main__":
    main()
