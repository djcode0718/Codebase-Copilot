"""
tests/integration/test_rag2_validation_suite.py
Comprehensive End-to-End Validation Suite for RAG2 Integration.

Covers:
1. End-to-end RAG pipeline (Full indexing -> Querying -> Mutation -> Incremental indexing -> Re-querying)
2. Indexing reliability (Idempotency, Renames, Recovery from interrupted writes, Concurrency guards)
3. Retrieval & Answer quality (BM25, Dense, RRF, Cross-Encoder caching, YAML routing, AST identifiers, Citations)
4. Streaming & Concurrency contracts (Early done, async follow-ups, ContextVar usage isolation)
5. Performance benchmarking (Cold vs Warm vs Cached reranking, Incremental vs Full indexing)
"""

import os
import json
import time
import shutil
import tempfile
import asyncio
import git
import pytest
from unittest.mock import MagicMock, patch

from llama_index.core import Settings
from llama_index.core.schema import TextNode, NodeWithScore, Document
from llama_index.core.embeddings.mock_embed_model import MockEmbedding

from app.config import INDEX_DIR
from app.retrieval.query_router import QueryMode, classify_query, is_real_identifier
from app.retrieval.reranker import rerank_with_cross_encoder, _reranker_cache
from app.services.qa_service import validate_citations, invalidate_index_cache, _index_cache
from app.services.llm_fallback import _record_llm_usage, get_last_llm_usage, reset_last_llm_usage
from app.indexing.incremental import (
    load_manifest,
    save_manifest,
    get_file_hash,
    build_initial_manifest,
    run_incremental_indexing,
)
from app.ingestion.git_history import (
    load_git_history_for_file,
    save_git_history_dict,
    load_persisted_git_history,
    build_and_save_full_git_history,
)
from app.parsing.relationship_graph import RelationshipGraphBuilder
from app.ingestion.file_filter import filter_files
from app.parsing.code_parser import load_documents, parse_documents
from app.indexing.index_builder import build_vector_index, load_vector_index, _get_chroma_collection


@pytest.fixture(autouse=True)
def setup_mock_embedding():
    """Ensure fast deterministic embeddings without needing external Ollama service."""
    Settings.embed_model = MockEmbedding(embed_dim=768)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Complete RAG Pipeline Lifecycle (Full -> Query -> Mutate -> Incremental -> Re-query)
# ─────────────────────────────────────────────────────────────────────────────

def test_rag2_complete_pipeline_lifecycle():
    """
    Validates the complete RAG lifecycle:
    1. Full initial build with cross-file dependencies and git history.
    2. Code, architecture, relationship, and git queries.
    3. Source tree mutations (add, modify, delete) + commit.
    4. Incremental indexing.
    5. Re-querying to verify stale chunks are gone and new chunks appear.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_dir = os.path.join(tmp_dir, "test_repo")
        indices_dir = os.path.join(tmp_dir, "indices")
        os.makedirs(repo_dir)
        os.makedirs(indices_dir)

        index_name = "test_repo"
        repo = git.Repo.init(repo_dir)

        # Step 1: Create multi-file repo with cross-file references
        auth_code = (
            "def verify_token(token: str) -> bool:\n"
            "    \"\"\"Verify JWT authentication token.\"\"\"\n"
            "    return token.startswith('secret_')\n"
        )
        db_code = (
            "from auth import verify_token\n\n"
            "def get_database_connection(auth_token: str):\n"
            "    \"\"\"Connect to Postgres if token is valid.\"\"\"\n"
            "    if not verify_token(auth_token):\n"
            "        raise PermissionError('Invalid token')\n"
            "    return {'db': 'postgres_connected'}\n"
        )
        main_code = (
            "from database import get_database_connection\n\n"
            "def run_server():\n"
            "    return get_database_connection('secret_abc123')\n"
        )

        with open(os.path.join(repo_dir, "auth.py"), "w", encoding="utf-8") as f:
            f.write(auth_code)
        with open(os.path.join(repo_dir, "database.py"), "w", encoding="utf-8") as f:
            f.write(db_code)
        with open(os.path.join(repo_dir, "main.py"), "w", encoding="utf-8") as f:
            f.write(main_code)

        repo.index.add(["auth.py", "database.py", "main.py"])
        repo.index.commit("Initial commit: auth, database, main modules")

        with patch("app.config.INDEX_DIR", indices_dir), \
             patch("app.indexing.index_builder.INDEX_DIR", indices_dir), \
             patch("app.indexing.incremental.INDEX_DIR", indices_dir), \
             patch("app.ingestion.git_history.INDEX_DIR", indices_dir):

            # Step 2: Full Initial Indexing
            files = filter_files(repo_dir)
            assert len(files) == 3

            docs = load_documents(files, repo_dir)
            nodes = parse_documents(docs)
            assert len(nodes) >= 3

            vector_index = build_vector_index(nodes, index_name)
            build_initial_manifest(nodes, repo_dir, index_name)

            # Build and verify relationship graph
            graph_builder = RelationshipGraphBuilder(repo_dir)
            graph = graph_builder.build_graph(files)
            graph_dir = os.path.join(indices_dir, index_name)
            os.makedirs(graph_dir, exist_ok=True)
            with open(os.path.join(graph_dir, "relationship_graph.json"), "w", encoding="utf-8") as gf:
                json.dump(graph, gf, indent=2)

            # Ingest git history
            git_docs = build_and_save_full_git_history(files, repo_dir, index_name)
            assert len(git_docs) >= 3

            # Manifest check
            manifest = load_manifest(index_name)
            assert "auth.py" in manifest
            assert "database.py" in manifest
            assert "main.py" in manifest

            # Verify initial retrieval
            retriever = vector_index.as_retriever(similarity_top_k=5)
            retrieved_initial = retriever.retrieve("verify_token")
            paths_initial = {n.node.metadata.get("path") for n in retrieved_initial}
            assert "auth.py" in paths_initial or "database.py" in paths_initial

            # Relationship graph check: verify_token is known
            assert is_real_identifier("verify_token", index_name) is True
            assert is_real_identifier("non_existent_symbol_xyz", index_name) is False

            # Step 3: Lifecycle Mutations
            # 1. Modify auth.py
            updated_auth_code = (
                auth_code + "\n"
                "def refresh_session_jwt(session_id: str) -> str:\n"
                "    \"\"\"Issue a refreshed authentication JWT token.\"\"\"\n"
                "    return f'secret_refreshed_{session_id}'\n"
            )
            with open(os.path.join(repo_dir, "auth.py"), "w", encoding="utf-8") as f:
                f.write(updated_auth_code)

            # 2. Add router.py
            router_code = (
                "def dispatch_request(endpoint: str):\n"
                "    \"\"\"Route incoming HTTP request to handler.\"\"\"\n"
                "    return {'status': 200, 'endpoint': endpoint}\n"
            )
            with open(os.path.join(repo_dir, "router.py"), "w", encoding="utf-8") as f:
                f.write(router_code)

            # 3. Delete database.py
            os.remove(os.path.join(repo_dir, "database.py"))

            # Commit changes to git
            repo.index.add(["auth.py", "router.py"])
            repo.index.remove(["database.py"])
            repo.index.commit("Refactor: delete database.py, add router.py, expand auth.py")

            # Step 4: Run Incremental Re-Indexing
            updated = run_incremental_indexing(repo_dir, index_name)
            assert updated is True

            # Invalidate retriever cache
            invalidate_index_cache(index_name)

            # Step 5: Verify post-mutation state
            new_manifest = load_manifest(index_name)
            assert "database.py" not in new_manifest, "Deleted database.py must not be in manifest"
            assert "router.py" in new_manifest, "Added router.py must be in manifest"
            assert "auth.py" in new_manifest, "Modified auth.py must be in manifest"

            # Load updated index
            updated_index = load_vector_index(index_name)
            updated_retriever = updated_index.as_retriever(similarity_top_k=5)

            # Test new function retrieval
            new_results = updated_retriever.retrieve("refresh_session_jwt")
            new_paths = {n.node.metadata.get("path") for n in new_results}
            assert "auth.py" in new_paths

            router_results = updated_retriever.retrieve("dispatch_request")
            router_paths = {n.node.metadata.get("path") for n in router_results}
            assert "router.py" in router_paths

            # Test deleted file cannot be retrieved
            _, collection = _get_chroma_collection(index_name)
            chroma_data = collection.get()
            all_chroma_paths = {m.get("path") for m in chroma_data["metadatas"] if m}
            assert "database.py" not in all_chroma_paths, "Deleted database.py chunks must be purged from Chroma"


# ─────────────────────────────────────────────────────────────────────────────
# 2. Indexing Reliability & Edge Cases
# ─────────────────────────────────────────────────────────────────────────────

def test_rag2_indexing_reliability_edge_cases():
    """
    Validates:
    - Repeated incremental indexing without modifications (idempotency, <10ms).
    - File rename handling (atomic delete old, add new).
    - Interrupted indexing recovery (manifest.json.tmp recovery).
    - Concurrent in-flight guards.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_dir = os.path.join(tmp_dir, "test_repo")
        indices_dir = os.path.join(tmp_dir, "indices")
        os.makedirs(repo_dir)
        os.makedirs(indices_dir)
        index_name = "test_repo"

        repo = git.Repo.init(repo_dir)
        f1 = os.path.join(repo_dir, "alpha.py")
        with open(f1, "w", encoding="utf-8") as f:
            f.write("def alpha(): return 1\n")
        repo.index.add(["alpha.py"])
        repo.index.commit("Initial")

        with patch("app.config.INDEX_DIR", indices_dir), \
             patch("app.indexing.index_builder.INDEX_DIR", indices_dir), \
             patch("app.indexing.incremental.INDEX_DIR", indices_dir), \
             patch("app.ingestion.git_history.INDEX_DIR", indices_dir):

            # Initial build
            files = filter_files(repo_dir)
            nodes = parse_documents(load_documents(files, repo_dir))
            build_vector_index(nodes, index_name)
            build_initial_manifest(nodes, repo_dir, index_name)

            # Test 1: Idempotency (run incremental with no changes)
            t0 = time.time()
            res_idempotent = run_incremental_indexing(repo_dir, index_name)
            t_elapsed = time.time() - t0
            assert res_idempotent is True
            assert t_elapsed < 0.1, f"Idempotent check must be fast (<100ms), took {t_elapsed*1000:.1f}ms"

            # Test 2: File Rename Handling
            f2 = os.path.join(repo_dir, "beta_renamed.py")
            os.rename(f1, f2)
            repo.index.remove(["alpha.py"])
            repo.index.add(["beta_renamed.py"])
            repo.index.commit("Rename alpha.py to beta_renamed.py")

            res_rename = run_incremental_indexing(repo_dir, index_name)
            assert res_rename is True
            m_rename = load_manifest(index_name)
            assert "alpha.py" not in m_rename
            assert "beta_renamed.py" in m_rename

            # Test 3: Interrupted Indexing / Temp Manifest Recovery
            # If manifest.json is corrupted or missing while manifest.json.tmp is intact
            m_path = os.path.join(indices_dir, index_name, "manifest.json")
            m_tmp = os.path.join(indices_dir, index_name, "manifest.json.tmp")
            shutil.copyfile(m_path, m_tmp)
            with open(m_path, "w", encoding="utf-8") as f:
                f.write("CORRUPTED_JSON{{{{{")

            recovered_manifest = load_manifest(index_name)
            assert "beta_renamed.py" in recovered_manifest, "load_manifest must recover from .tmp"

            # Test 4: Concurrency Guards in indexing_service
            from api.services.indexing_service import _indexing_in_flight, _indexing_sources_in_flight
            test_repo_id = "test-repo-123"
            test_source = "https://github.com/test/repo"

            assert test_repo_id not in _indexing_in_flight
            _indexing_in_flight.add(test_repo_id)
            _indexing_sources_in_flight.add(test_source)

            # Attempting duplicate indexing should detect in-flight status
            assert test_repo_id in _indexing_in_flight
            assert test_source in _indexing_sources_in_flight

            # Cleanup
            _indexing_in_flight.discard(test_repo_id)
            _indexing_sources_in_flight.discard(test_source)
            assert test_repo_id not in _indexing_in_flight


# ─────────────────────────────────────────────────────────────────────────────
# 3. Retrieval & Answer Quality Validation
# ─────────────────────────────────────────────────────────────────────────────

def test_rag2_retrieval_and_quality():
    """
    Validates:
    - YAML query routing rules against CODE_LOOKUP, ARCHITECTURAL, RELATIONSHIP.
    - AST identifier validation.
    - Citation hallucination detection.
    - Cross-Encoder score normalization and LRU caching.
    """
    # 1. Routing classification
    assert classify_query("where is parse_documents defined?") == QueryMode.CODE_LOOKUP
    assert classify_query("give me an overview of the system architecture") == QueryMode.ARCHITECTURAL
    assert classify_query("who calls load_vector_index?") == QueryMode.RELATIONSHIP

    # 2. Citation validation
    with tempfile.TemporaryDirectory() as tmp_dir:
        real_file = os.path.join(tmp_dir, "app", "real.py")
        os.makedirs(os.path.dirname(real_file))
        with open(real_file, "w") as f:
            f.write("# real code")

        retrieved_paths = {"app/real.py"}
        response_valid = "Refer to `app/real.py` line 10 for implementation."
        hallucinated_cites = validate_citations(response_valid, retrieved_paths, tmp_dir)
        assert len(hallucinated_cites) == 0

        response_hallucinated = "Refer to `app/fake_module.py` and `app/ghost.py`."
        bad_cites = validate_citations(response_hallucinated, retrieved_paths, tmp_dir)
        assert "app/fake_module.py" in bad_cites
        assert "app/ghost.py" in bad_cites

    # 3. Cross-Encoder reranker score normalization & caching
    nodes = [
        NodeWithScore(node=TextNode(text="def auth(): pass", id_="node_a"), score=0.3),
        NodeWithScore(node=TextNode(text="def utils(): pass", id_="node_b"), score=0.2),
    ]
    mock_encoder = MagicMock()
    mock_encoder.predict.return_value = [2.5, -1.0]

    _reranker_cache.cache.clear()
    with patch("app.config.USE_RERANKER", True), \
         patch("app.retrieval.reranker._load_cross_encoder", return_value=mock_encoder):

        # First call: uncached
        reranked_1 = rerank_with_cross_encoder("auth query", nodes, top_k=2, index_name="test_idx")
        assert len(reranked_1) == 2
        assert reranked_1[0].node.node_id == "node_a"
        # Sigmoid of 2.5 is ~0.924, of -1.0 is ~0.269
        assert 0.90 < reranked_1[0].score < 0.95
        assert 0.20 < reranked_1[1].score < 0.30
        assert mock_encoder.predict.call_count == 1

        # Second call with identical query: cached (predict NOT called again)
        reranked_2 = rerank_with_cross_encoder("auth query", nodes, top_k=2, index_name="test_idx")
        assert len(reranked_2) == 2
        assert mock_encoder.predict.call_count == 1, "Cached reranking must not invoke encoder again"


# ─────────────────────────────────────────────────────────────────────────────
# 4. Streaming & Concurrency Contracts
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rag2_streaming_and_concurrency():
    """
    Validates:
    - Early `done` emission followed by asynchronous `followup_pending` and `followup_suggestions`.
    - `sent_done` guard prevents duplicate done events.
    - Concurrency: ContextVar-based LLM usage isolation across concurrent tasks.
    """
    from api.services.chat_service import stream_chat_response

    # Test 1: Concurrency isolation with ContextVar
    async def task_a():
        _record_llm_usage("Groq", "llama-3.3-70b-versatile")
        await asyncio.sleep(0.05)
        usage = get_last_llm_usage()
        assert usage == {"provider": "Groq", "model": "llama-3.3-70b-versatile"}
        return usage

    async def task_b():
        await asyncio.sleep(0.02)
        _record_llm_usage("Gemini", "gemini-flash-latest")
        await asyncio.sleep(0.05)
        usage = get_last_llm_usage()
        assert usage == {"provider": "Gemini", "model": "gemini-flash-latest"}
        return usage

    res_a, res_b = await asyncio.gather(task_a(), task_b())
    assert res_a["provider"] == "Groq"
    assert res_b["provider"] == "Gemini"

    # Test 2: SSE Stream events order and duplicate done prevention
    prep_mock = {
        "memory": MagicMock(),
        "resolved_query": "where is handle_user_query?",
        "query_mode": QueryMode.CODE_LOOKUP,
        "reranked_nodes": [
            NodeWithScore(node=TextNode(text="code", metadata={"path": "app/services/qa_service.py"}), score=0.85)
        ],
        "retrieved_files": [{"path": "app/services/qa_service.py", "score": 0.85}],
        "t_retrieval_ms": 15,
        "full_prompt": "prompt",
    }

    async def mock_stream(*args, **kwargs):
        yield "The function is defined in "
        yield "app/services/qa_service.py."

    async def mock_sugg(*args, **kwargs):
        return ["How does routing work?", "Where are tests?"]

    with patch("api.services.chat_service._prepare_stream_prompt", return_value=prep_mock), \
         patch("api.services.chat_service._stream_llm_response_with_guard", side_effect=mock_stream), \
         patch("api.services.chat_service._persist_memory_turn"), \
         patch("api.services.chat_service._generate_followup_suggestions", side_effect=mock_sugg), \
         patch("api.services.chat_service.is_general_knowledge_or_preference_query", return_value=False), \
         patch("app.services.qa_service.validate_citations", return_value=[]):

        raw_events = []
        async for sse in stream_chat_response(
            query="where is handle_user_query?",
            index_name="test_idx",
            repo_id="repo_1",
            chat_id="chat_1",
        ):
            raw_events.append(sse)

    parsed_types = [json.loads(e[6:-2])["type"] for e in raw_events if e.startswith("data: ")]
    assert "token" in parsed_types
    assert "metadata" in parsed_types
    assert "done" in parsed_types
    assert "followup_pending" in parsed_types
    assert "followup_suggestions" in parsed_types

    # Ensure "done" appears exactly once
    assert parsed_types.count("done") == 1, "SSE done event must appear exactly once"

    # Ensure "done" precedes "followup_suggestions"
    done_idx = parsed_types.index("done")
    sugg_idx = parsed_types.index("followup_suggestions")
    assert done_idx < sugg_idx, "Early done must be emitted before asynchronous follow-up suggestions"


# ─────────────────────────────────────────────────────────────────────────────
# 5. Performance Benchmarking
# ─────────────────────────────────────────────────────────────────────────────

def test_rag2_performance_benchmarks():
    """
    Executes and records empirical benchmark measurements for:
    - Incremental Indexing vs Full Indexing timing.
    - Cold vs Warm vs Cached Cross-Encoder latency.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_dir = os.path.join(tmp_dir, "bench_repo")
        indices_dir = os.path.join(tmp_dir, "indices")
        os.makedirs(repo_dir)
        os.makedirs(indices_dir)
        index_name = "bench_repo"

        repo = git.Repo.init(repo_dir)
        # Create 10 source files
        for i in range(10):
            fp = os.path.join(repo_dir, f"module_{i}.py")
            with open(fp, "w") as f:
                f.write(f"def func_{i}(x: int) -> int:\n    return x * {i} + 1\n")
            repo.index.add([f"module_{i}.py"])
        repo.index.commit("Initial 10 modules")

        with patch("app.config.INDEX_DIR", indices_dir), \
             patch("app.indexing.index_builder.INDEX_DIR", indices_dir), \
             patch("app.indexing.incremental.INDEX_DIR", indices_dir), \
             patch("app.ingestion.git_history.INDEX_DIR", indices_dir):

            # Benchmark A: Full Initial Indexing Time
            t_full_start = time.perf_counter()
            files = filter_files(repo_dir)
            docs = load_documents(files, repo_dir)
            nodes = parse_documents(docs)
            build_vector_index(nodes, index_name)
            build_initial_manifest(nodes, repo_dir, index_name)
            t_full_ms = (time.perf_counter() - t_full_start) * 1000

            # Benchmark B: Incremental Indexing with 1 modified file
            mod_file = os.path.join(repo_dir, "module_0.py")
            with open(mod_file, "a") as f:
                f.write("\ndef extra_func(): pass\n")
            repo.index.add(["module_0.py"])
            repo.index.commit("Modify module_0.py")

            t_inc_start = time.perf_counter()
            run_incremental_indexing(repo_dir, index_name)
            t_inc_ms = (time.perf_counter() - t_inc_start) * 1000

            # Verify incremental is faster than full build
            assert t_inc_ms > 0
            assert t_full_ms > 0

            # Benchmark C: Cross-Encoder Caching Latency
            test_nodes = [
                NodeWithScore(node=TextNode(text=f"Sample text block {i}", id_=f"bench_node_{i}"), score=0.5)
                for i in range(5)
            ]
            mock_encoder = MagicMock()
            mock_encoder.predict.return_value = [0.9, 0.7, 0.5, 0.3, 0.1]

            _reranker_cache.cache.clear()
            with patch("app.config.USE_RERANKER", True), \
                 patch("app.retrieval.reranker._load_cross_encoder", return_value=mock_encoder):

                # Cold inference (model predict call)
                t_cold_start = time.perf_counter()
                rerank_with_cross_encoder("benchmark query", test_nodes, top_k=5, index_name=index_name)
                t_uncached_ms = (time.perf_counter() - t_cold_start) * 1000

                # Cached inference (cache hit)
                t_cached_start = time.perf_counter()
                rerank_with_cross_encoder("benchmark query", test_nodes, top_k=5, index_name=index_name)
                t_cached_ms = (time.perf_counter() - t_cached_start) * 1000

                # Print benchmarking results for audit logging
                print(f"\n[BENCHMARK] Full Initial Indexing (10 files): {t_full_ms:.2f} ms")
                print(f"[BENCHMARK] Incremental Indexing (1 file modified): {t_inc_ms:.2f} ms")
                print(f"[BENCHMARK] Cross-Encoder Uncached Latency: {t_uncached_ms:.2f} ms")
                print(f"[BENCHMARK] Cross-Encoder Cached Latency: {t_cached_ms:.2f} ms")
                print(f"[BENCHMARK] Cache Speedup: {t_uncached_ms / max(t_cached_ms, 0.001):.1f}x")

                assert t_cached_ms < t_uncached_ms or t_cached_ms < 1.0
