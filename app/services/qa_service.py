from app.indexing.vector_store import create_vector_store
from app.retrieval.retriever import retrieve_relevant_chunks
from app.retrieval.ranking import rerank_chunks
from app.llm.prompts import build_prompt
from app.llm.llm_client import generate_response
from app.utils.logger import get_logger
from tqdm import tqdm
import time

logger = get_logger(__name__)

def handle_user_query(query: str, index_name: str) -> str:
    """
    Orchestrates the QA pipeline:
    retrieve -> rerank -> build_prompt -> generate_response -> format output
    """
    logger.info(f"Handling query for index '{index_name}': {query}")
    
    # 1. Load vector store
    vector_store = create_vector_store(index_name)
    if not vector_store.load():
        return f"Error: Could not load index '{index_name}'. Have you processed the repository yet?"
        
    # 2. Retrieve relevant chunks
    # chunks = retrieve_relevant_chunks(query, vector_store, top_k=5)
    from app.retrieval.file_map_retriever import retrieve_relevant_files

    # Step 1: get relevant files
    relevant_files = retrieve_relevant_files(query, index_name)
    logger.info(f"Relevant files: {len(relevant_files)}")

    # Step 2: filter chunks based on files
    file_paths = [f["file"] for f in relevant_files]

    # filtered_chunks = [
    #     c for c in vector_store.metadata
    #     if c["metadata"]["path"] in file_paths
    # ]

    # chunks = filtered_chunks[:5]  # limit

    from app.retrieval.retriever import retrieve_relevant_chunks

    # Step 2: Hybrid retrieval
    chunks = retrieve_relevant_chunks(
        query,
        vector_store,
        file_paths,
        top_k=10
    )


    if not chunks:
        return "No relevant context found in the codebase to answer your question."

    logger.info(f"Chunks selected: {len(chunks)}")
        
    # 3. Rerank chunks (currently a pass-through)
    ranked_chunks = rerank_chunks(query, chunks)
    
    # 4. Build prompt
    prompt = build_prompt(query, ranked_chunks)
    
    # 5. Generate response
    start_time = time.time()

    response = generate_response(prompt)
    logger.info(f"LLM response time: {time.time() - start_time:.2f}s")
    
    # 6. Format output (already returning string)
    return response
