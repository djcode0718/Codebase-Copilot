import pytest
import os
import json
from unittest.mock import MagicMock, patch
from llama_index.core.schema import NodeWithScore, TextNode

from app.retrieval.orchestrator import (
    SharedRetrievalOrchestrator,
    RetrievalTier,
    RetrievalDecision,
    get_retrieval_orchestrator,
    get_calibrated_thresholds,
    set_calibrated_thresholds,
    DEFAULT_ABSTENTION_MESSAGE,
)
from app.retrieval.query_router import QueryMode


@pytest.fixture(autouse=True)
def isolate_unit_test_reranker():
    with patch("app.config.USE_RERANKER", False):
        yield


def test_orchestrator_singleton():
    orch1 = get_retrieval_orchestrator()
    orch2 = get_retrieval_orchestrator()
    assert orch1 is orch2
    assert isinstance(orch1, SharedRetrievalOrchestrator)


def test_tier1_architecture_context_selection(tmp_path):
    """Tier 1: Architectural query retrieves and injects repository architecture context."""
    index_name = "test_arch_repo"
    idx_dir = tmp_path / index_name
    idx_dir.mkdir(parents=True)
    (idx_dir / "codebase_context.txt").write_text("# Project Architecture\nOverview of test repo structure.")

    orch = SharedRetrievalOrchestrator(index_dir=str(tmp_path))

    mock_vector = MagicMock()
    mock_vector.as_retriever.return_value.retrieve.return_value = [
        NodeWithScore(node=TextNode(text="class CoreApp: pass", metadata={"path": "core.py"}), score=0.75)
    ]

    decision = orch.orchestrate(
        query="Explain the high-level architecture of this system",
        index_name=index_name,
        vector_index=mock_vector,
        query_mode=QueryMode.ARCHITECTURAL,
    )

    assert decision.selected_tier == RetrievalTier.TIER1_ARCHITECTURE
    assert decision.should_abstain is False
    assert len(decision.nodes) >= 1
    # Check that codebase context was loaded into nodes
    paths = [n.node.metadata.get("path") for n in decision.nodes]
    assert "_codebase_context" in paths
    assert decision.confidence_score >= 0.70


def test_tier2_documentation_retrieval_selection(tmp_path):
    """Tier 2: Documentation queries prioritize markdown and README evidence."""
    orch = SharedRetrievalOrchestrator(index_dir=str(tmp_path))

    doc_node = NodeWithScore(
        node=TextNode(text="# Installation Guide\npip install package", metadata={"path": "README.md"}),
        score=0.88,
    )
    code_node = NodeWithScore(
        node=TextNode(text="def setup(): pass", metadata={"path": "setup.py"}),
        score=0.40,
    )

    mock_vector = MagicMock()
    mock_vector.as_retriever.return_value.retrieve.return_value = [doc_node, code_node]

    decision = orch.orchestrate(
        query="How do I install and configure the project?",
        index_name="test_doc_repo",
        vector_index=mock_vector,
        query_mode=QueryMode.CODE_LOOKUP,
        raw_nodes=[doc_node, code_node],
    )

    assert decision.selected_tier == RetrievalTier.TIER2_DOCUMENTATION
    assert decision.should_abstain is False
    assert "README.md" in decision.retrieved_files
    assert decision.confidence_score == 0.88


def test_tier3_hybrid_code_and_notebook_selection(tmp_path):
    """Tier 3: Function/code implementation queries retrieve code and notebook chunks."""
    orch = SharedRetrievalOrchestrator(index_dir=str(tmp_path))

    code_node = NodeWithScore(
        node=TextNode(text="def parse_tokens(stream): return []", metadata={"path": "tokenizer.py"}),
        score=0.72,
    )
    notebook_node = NodeWithScore(
        node=TextNode(text="trainer.fit(model, dataloader)", metadata={"path": "train.ipynb", "doc_type": "notebook_code"}),
        score=0.68,
    )

    mock_vector = MagicMock()
    mock_vector.as_retriever.return_value.retrieve.return_value = [code_node, notebook_node]

    decision = orch.orchestrate(
        query="Where is parse_tokens implemented?",
        index_name="test_code_repo",
        vector_index=mock_vector,
        query_mode=QueryMode.CODE_LOOKUP,
        raw_nodes=[code_node, notebook_node],
    )

    assert decision.selected_tier == RetrievalTier.TIER3_HYBRID_CODE
    assert decision.should_abstain is False
    assert "tokenizer.py" in decision.retrieved_files
    assert decision.confidence_score == 0.72


def test_tier4_grounded_abstention_on_empty_evidence(tmp_path):
    """Tier 4: Abstention when no nodes are retrieved."""
    orch = SharedRetrievalOrchestrator(index_dir=str(tmp_path))

    mock_vector = MagicMock()
    mock_vector.as_retriever.return_value.retrieve.return_value = []

    decision = orch.orchestrate(
        query="What is the internal API of secret_subsystem_xyz?",
        index_name="test_empty_repo",
        vector_index=mock_vector,
        query_mode=QueryMode.CODE_LOOKUP,
        raw_nodes=[],
    )

    assert decision.selected_tier == RetrievalTier.TIER4_ABSTENTION
    assert decision.should_abstain is True
    assert decision.abstention_message == DEFAULT_ABSTENTION_MESSAGE
    assert decision.confidence_score == 0.0
    assert decision.nodes == []
    assert decision.full_prompt == ""


def test_tier4_grounded_abstention_on_negligible_confidence(tmp_path):
    """Tier 4: Abstention when retrieved nodes have negligible confidence."""
    orch = SharedRetrievalOrchestrator(index_dir=str(tmp_path))

    low_conf_node = NodeWithScore(
        node=TextNode(text="unrelated string", metadata={"path": "misc.py"}),
        score=0.08,  # Below TIER3_THRESHOLD (0.32)
    )

    mock_vector = MagicMock()
    mock_vector.as_retriever.return_value.retrieve.return_value = [low_conf_node]

    decision = orch.orchestrate(
        query="What is quantum_computing_algorithm?",
        index_name="test_low_conf_repo",
        vector_index=mock_vector,
        query_mode=QueryMode.CODE_LOOKUP,
        raw_nodes=[low_conf_node],
    )

    assert decision.selected_tier == RetrievalTier.TIER4_ABSTENTION
    assert decision.should_abstain is True
    assert decision.abstention_message == DEFAULT_ABSTENTION_MESSAGE


def test_relationship_query_uses_atomic_graph(tmp_path):
    """Relationship queries retrieve grounded edges from relationship_graph.json."""
    index_name = "test_rel_repo"
    idx_dir = tmp_path / index_name
    idx_dir.mkdir(parents=True)
    graph_data = {
        "load_vector_index": [
            "qa_service.py:handle_user_query",
            "chat_service.py:_load_indexes",
        ]
    }
    (idx_dir / "relationship_graph.json").write_text(json.dumps(graph_data))

    orch = SharedRetrievalOrchestrator(index_dir=str(tmp_path))
    mock_vector = MagicMock()

    decision = orch.orchestrate(
        query="Where is load_vector_index called?",
        index_name=index_name,
        vector_index=mock_vector,
        query_mode=QueryMode.RELATIONSHIP,
    )

    assert decision.selected_tier == RetrievalTier.RELATIONSHIP
    assert decision.should_abstain is False
    assert decision.relationship_target == "load_vector_index"
    assert len(decision.relationship_refs) == 2
    assert "qa_service.py:handle_user_query" in decision.relationship_refs
    assert "chat_service.py:_load_indexes" in decision.relationship_refs


def test_streaming_and_non_streaming_retrieval_consistency(tmp_path):
    """Verify that streaming and non-streaming receive identical retrieval decisions."""
    index_name = "test_consistency_repo"
    idx_dir = tmp_path / index_name
    idx_dir.mkdir(parents=True)
    (idx_dir / "codebase_context.txt").write_text("Architecture overview")

    orch = SharedRetrievalOrchestrator(index_dir=str(tmp_path))

    shared_node = NodeWithScore(
        node=TextNode(text="def process(): pass", metadata={"path": "worker.py"}),
        score=0.82,
    )
    mock_vector = MagicMock()
    mock_vector.as_retriever.return_value.retrieve.return_value = [shared_node]

    # Non-streaming path call
    decision_qa = orch.orchestrate(
        query="Show process implementation",
        index_name=index_name,
        vector_index=mock_vector,
        raw_nodes=[shared_node],
        query_mode=QueryMode.CODE_LOOKUP,
    )

    # Streaming path call
    decision_stream = orch.orchestrate(
        query="Show process implementation",
        index_name=index_name,
        vector_index=mock_vector,
        raw_nodes=[shared_node],
        query_mode=QueryMode.CODE_LOOKUP,
    )

    # Both must select the exact same tier, nodes, and confidence
    assert decision_qa.selected_tier == decision_stream.selected_tier == RetrievalTier.TIER3_HYBRID_CODE
    assert decision_qa.confidence_score == decision_stream.confidence_score == 0.82
    assert decision_qa.should_abstain == decision_stream.should_abstain is False
    assert decision_qa.retrieved_files == decision_stream.retrieved_files == ["worker.py"]
    assert decision_qa.context_str == decision_stream.context_str


def test_confidence_calibration_threshold_updates():
    """Verify separate tier threshold inspection and update."""
    orig = get_calibrated_thresholds()
    assert RetrievalTier.TIER1_ARCHITECTURE in orig
    assert RetrievalTier.TIER2_DOCUMENTATION in orig
    assert RetrievalTier.TIER3_HYBRID_CODE in orig

    # Update threshold
    set_calibrated_thresholds({RetrievalTier.TIER3_HYBRID_CODE: 0.40})
    updated = get_calibrated_thresholds()
    assert updated[RetrievalTier.TIER3_HYBRID_CODE] == 0.40

    # Restore default
    set_calibrated_thresholds(orig)


def test_architectural_query_abstains_when_architecture_context_score_below_threshold(tmp_path):
    """Unsupported architectural query with low architecture-context confidence must abstain."""
    index_name = "test_arch_unsupported"
    orch = SharedRetrievalOrchestrator(index_dir=str(tmp_path))

    # Low-scoring architecture node (e.g. 0.50 below 0.54 threshold)
    low_arch_node = NodeWithScore(
        node=TextNode(text="Generic repo info", metadata={"path": "_codebase_context"}),
        score=0.50,
    )

    mock_vector = MagicMock()
    mock_vector.as_retriever.return_value.retrieve.return_value = []

    with patch.object(orch, "_load_architecture_context_nodes", return_value=[low_arch_node]):
        decision = orch.orchestrate(
            query="How does the Cassandra cluster store audio transcription histories?",
            index_name=index_name,
            vector_index=mock_vector,
            query_mode=QueryMode.ARCHITECTURAL,
        )

    assert decision.selected_tier == RetrievalTier.TIER4_ABSTENTION
    assert decision.should_abstain is True
    assert decision.abstention_message == DEFAULT_ABSTENTION_MESSAGE


def test_architectural_query_abstains_when_architecture_context_missing(tmp_path):
    """Architectural query when architecture context is missing must trigger Tier 4 abstention."""
    index_name = "test_arch_missing"
    orch = SharedRetrievalOrchestrator(index_dir=str(tmp_path))

    mock_vector = MagicMock()
    mock_vector.as_retriever.return_value.retrieve.return_value = []

    with patch.object(orch, "_load_architecture_context_nodes", return_value=[]):
        decision = orch.orchestrate(
            query="What is the overall system architecture?",
            index_name=index_name,
            vector_index=mock_vector,
            query_mode=QueryMode.ARCHITECTURAL,
        )

    assert decision.selected_tier == RetrievalTier.TIER4_ABSTENTION
    assert decision.should_abstain is True


def test_architectural_query_unrelated_high_scoring_chunk_cannot_rescue(tmp_path):
    """An unrelated high-scoring code chunk cannot rescue an unsupported architecture query."""
    index_name = "test_arch_rescue_prevention"
    orch = SharedRetrievalOrchestrator(index_dir=str(tmp_path))

    low_arch_node = NodeWithScore(
        node=TextNode(text="Overview of ML pipeline", metadata={"path": "_codebase_context"}),
        score=0.50,  # Below 0.54
    )
    # High-scoring code chunk (e.g. matching some keyword like "cluster" or "events")
    high_code_node = NodeWithScore(
        node=TextNode(text="def cluster_events(): pass", metadata={"path": "cluster_utils.py"}),
        score=0.88,
    )

    mock_vector = MagicMock()
    mock_vector.as_retriever.return_value.retrieve.return_value = [high_code_node]

    with patch.object(orch, "_load_architecture_context_nodes", return_value=[low_arch_node]):
        decision = orch.orchestrate(
            query="How does the Apache Kafka producer publish speech emotion events?",
            index_name=index_name,
            vector_index=mock_vector,
            query_mode=QueryMode.ARCHITECTURAL,
            raw_nodes=[high_code_node],
        )

    # Must abstain because architecture evidence is 0.50 < 0.54, regardless of code chunk score (0.88)
    assert decision.selected_tier == RetrievalTier.TIER4_ABSTENTION
    assert decision.should_abstain is True


def test_architectural_query_valid_architecture_evidence_passes(tmp_path):
    """Valid architectural query with relevant architecture context (>= 0.54) succeeds."""
    index_name = "test_arch_valid"
    orch = SharedRetrievalOrchestrator(index_dir=str(tmp_path))

    valid_arch_node = NodeWithScore(
        node=TextNode(text="# Architecture\nDetailed system overview and component layout.", metadata={"path": "_codebase_context"}),
        score=0.68,  # Well above 0.54
    )

    mock_vector = MagicMock()
    mock_vector.as_retriever.return_value.retrieve.return_value = []

    with patch.object(orch, "_load_architecture_context_nodes", return_value=[valid_arch_node]):
        decision = orch.orchestrate(
            query="What is the high-level architecture of this repository?",
            index_name=index_name,
            vector_index=mock_vector,
            query_mode=QueryMode.ARCHITECTURAL,
        )

    assert decision.selected_tier == RetrievalTier.TIER1_ARCHITECTURE
    assert decision.should_abstain is False
    assert decision.confidence_score == 0.68


# ─────────────────────────────────────────────────────────────────────────────
# Fix B: Dynamic Candidate-Grounded Entity Verification Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_grounding_react_in_repo_with_react(tmp_path):
    """React in a repository that actually contains React is verified and accepted."""
    orch = SharedRetrievalOrchestrator(index_dir=str(tmp_path))
    react_node = NodeWithScore(
        node=TextNode(
            text="import React from 'react'; export const App = () => <div>Hello</div>;",
            metadata={"path": "frontend/src/App.tsx", "symbol_name": "App"},
        ),
        score=0.85,
    )
    is_grounded, msg = orch._verify_framework_grounding(
        "How is React component state managed in App.tsx?",
        nodes=[react_node],
        candidate_nodes=[react_node],
        index_name="test_react_repo",
    )
    assert is_grounded is True
    assert msg is None


def test_grounding_redis_in_repo_without_redis(tmp_path):
    """Redis in a repository without Redis triggers grounded abstention."""
    orch = SharedRetrievalOrchestrator(index_dir=str(tmp_path))
    py_node = NodeWithScore(
        node=TextNode(
            text="def fetch_user(db, uid): return db.query(uid)",
            metadata={"path": "services/user.py", "symbol_name": "fetch_user"},
        ),
        score=0.75,
    )
    is_grounded, msg = orch._verify_framework_grounding(
        "How does Redis cache the user session data?",
        nodes=[py_node],
        candidate_nodes=[py_node],
        index_name="test_no_redis_repo",
    )
    assert is_grounded is False
    assert "redis" in msg.lower()


def test_grounding_kafka_in_repo_without_kafka(tmp_path):
    """Kafka in a repository without Kafka triggers grounded abstention."""
    orch = SharedRetrievalOrchestrator(index_dir=str(tmp_path))
    ml_node = NodeWithScore(
        node=TextNode(
            text="def train_epoch(model, loader): pass",
            metadata={"path": "train.py", "symbol_name": "train_epoch"},
        ),
        score=0.70,
    )
    is_grounded, msg = orch._verify_framework_grounding(
        "How does Kafka consumer ingest training batches?",
        nodes=[ml_node],
        candidate_nodes=[ml_node],
        index_name="test_no_kafka_repo",
    )
    assert is_grounded is False
    assert "kafka" in msg.lower()


def test_grounding_technology_in_unrelated_repo_context(tmp_path):
    """A technology present in an unrelated repo cannot ground queries for a repo that lacks it."""
    # Create repo B dir without React
    repo_b_dir = tmp_path / "repos" / "repo_b"
    repo_b_dir.mkdir(parents=True)
    (repo_b_dir / "main.py").write_text("print('pure python')")

    orch = SharedRetrievalOrchestrator(index_dir=str(tmp_path))
    b_node = NodeWithScore(
        node=TextNode(text="print('pure python')", metadata={"path": "main.py"}),
        score=0.60,
    )

    with patch("app.retrieval.orchestrator.get_repos_dir", return_value=str(tmp_path / "repos")):
        is_grounded, msg = orch._verify_framework_grounding(
            "Where is the React frontend entrypoint?",
            nodes=[b_node],
            candidate_nodes=[b_node],
            index_name="repo_b",
            target_repo_id="repo_b",
        )
    assert is_grounded is False
    assert "react" in msg.lower()


def test_grounding_similar_technology_names_across_different_repositories(tmp_path):
    """Similar technology names across different repositories remain strictly isolated."""
    # Repo A has Postgres in requirements
    repos_dir = tmp_path / "repos"
    repo_a = repos_dir / "repo_a"
    repo_b = repos_dir / "repo_b"
    repo_a.mkdir(parents=True)
    repo_b.mkdir(parents=True)

    (repo_a / "requirements.txt").write_text("psycopg2-binary==2.9.9\n")
    (repo_b / "requirements.txt").write_text("sqlite3\n")

    orch = SharedRetrievalOrchestrator(index_dir=str(tmp_path))
    node_b = NodeWithScore(
        node=TextNode(text="import sqlite3", metadata={"path": "db.py"}),
        score=0.70,
    )

    with patch("app.retrieval.orchestrator.get_repos_dir", return_value=str(repos_dir)):
        # Querying repo_b about postgres must fail, even though repo_a has it
        is_grounded, msg = orch._verify_framework_grounding(
            "How does Postgres connect to the database?",
            nodes=[node_b],
            candidate_nodes=[node_b],
            index_name="repo_b",
            target_repo_id="repo_b",
        )
    assert is_grounded is False
    assert "postgres" in msg.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Fix C: Documentation Priority Inversion Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_doc_priority_inversion_direct_code_lookup(tmp_path):
    """Direct code lookup must not cap implementation code chunks at two even when doc score is high."""
    index_name = "test_code_lookup_uncapped"
    orch = SharedRetrievalOrchestrator(index_dir=str(tmp_path))

    doc_node = NodeWithScore(
        node=TextNode(text="# Documentation\nOverview of parsing system.", metadata={"path": "README.md"}),
        score=0.88,
    )
    code_node1 = NodeWithScore(
        node=TextNode(text="def parse_ast(): pass", metadata={"path": "parser/ast.py"}),
        score=0.85,
    )
    code_node2 = NodeWithScore(
        node=TextNode(text="def parse_tokens(): pass", metadata={"path": "parser/tokens.py"}),
        score=0.83,
    )
    code_node3 = NodeWithScore(
        node=TextNode(text="def parse_grammar(): pass", metadata={"path": "parser/grammar.py"}),
        score=0.80,
    )
    code_node4 = NodeWithScore(
        node=TextNode(text="def parse_schema(): pass", metadata={"path": "parser/schema.py"}),
        score=0.78,
    )

    reranked = [doc_node, code_node1, code_node2, code_node3, code_node4]
    mock_vector = MagicMock()

    decision = orch.orchestrate(
        query="Show me the parser implementation functions",
        index_name=index_name,
        vector_index=mock_vector,
        query_mode=QueryMode.CODE_LOOKUP,
        raw_nodes=reranked,
        rerank_fn=lambda q, n, top_k, index_name=None: reranked[:top_k],
    )

    # In CODE_LOOKUP, code chunks must NOT be capped at 2!
    code_in_final = [n for n in decision.nodes if orch._is_code_node(n)]
    assert len(code_in_final) >= 4
    assert len(decision.nodes) <= 5


def test_doc_priority_inversion_architecture_questions(tmp_path):
    """Architecture questions preserve architecture context while strictly respecting the Top-5 budget."""
    index_name = "test_arch_budget"
    orch = SharedRetrievalOrchestrator(index_dir=str(tmp_path))

    arch_node = NodeWithScore(
        node=TextNode(text="# Architecture\nSystem design layout.", metadata={"path": "_codebase_context"}),
        score=0.75,
    )
    reranked_nodes = [
        NodeWithScore(node=TextNode(text=f"def fn_{i}(): pass", metadata={"path": f"src/mod_{i}.py"}), score=0.70 - i * 0.05)
        for i in range(10)
    ]

    mock_vector = MagicMock()
    with patch.object(orch, "_load_architecture_context_nodes", return_value=[arch_node]):
        decision = orch.orchestrate(
            query="What is the high-level system architecture?",
            index_name=index_name,
            vector_index=mock_vector,
            query_mode=QueryMode.ARCHITECTURAL,
            raw_nodes=reranked_nodes,
            rerank_fn=lambda q, n, top_k, index_name=None: reranked_nodes[:top_k],
        )

    assert decision.selected_tier == RetrievalTier.TIER1_ARCHITECTURE
    assert len(decision.nodes) == 5
    assert decision.nodes[0].node.metadata.get("path") == "_codebase_context"


def test_doc_priority_inversion_readme_only_questions(tmp_path):
    """README-only questions correctly select documentation tier and deliver documentation."""
    index_name = "test_readme_only"
    orch = SharedRetrievalOrchestrator(index_dir=str(tmp_path))

    readme_node = NodeWithScore(
        node=TextNode(text="# Installation\npip install -r requirements.txt", metadata={"path": "README.md"}),
        score=0.92,
    )
    code_node = NodeWithScore(
        node=TextNode(text="def setup(): pass", metadata={"path": "setup.py"}),
        score=0.45,
    )

    mock_vector = MagicMock()
    decision = orch.orchestrate(
        query="What are the installation instructions in the README?",
        index_name=index_name,
        vector_index=mock_vector,
        query_mode=QueryMode.CODE_LOOKUP,
        raw_nodes=[readme_node, code_node],
        rerank_fn=lambda q, n, top_k, index_name=None: [readme_node, code_node],
    )

    assert decision.selected_tier == RetrievalTier.TIER2_DOCUMENTATION
    assert decision.nodes[0].node.metadata.get("path") == "README.md"
    assert decision.should_abstain is False


def test_doc_priority_inversion_mixed_doc_and_implementation(tmp_path):
    """Mixed documentation and implementation evidence preserves both according to relevance."""
    index_name = "test_mixed_evidence"
    orch = SharedRetrievalOrchestrator(index_dir=str(tmp_path))

    doc_node = NodeWithScore(
        node=TextNode(text="# Pipeline Guide\nDescribes the processing pipeline steps.", metadata={"path": "docs/pipeline.md"}),
        score=0.86,
    )
    code_1 = NodeWithScore(
        node=TextNode(text="class Pipeline: pass", metadata={"path": "pipeline/core.py"}),
        score=0.84,
    )
    code_2 = NodeWithScore(
        node=TextNode(text="def run_pipeline(): pass", metadata={"path": "pipeline/runner.py"}),
        score=0.82,
    )
    code_3 = NodeWithScore(
        node=TextNode(text="def export_results(): pass", metadata={"path": "pipeline/export.py"}),
        score=0.79,
    )

    all_nodes = [doc_node, code_1, code_2, code_3]
    mock_vector = MagicMock()
    decision = orch.orchestrate(
        query="How does the pipeline execute and where is it documented?",
        index_name=index_name,
        vector_index=mock_vector,
        query_mode=QueryMode.CODE_LOOKUP,
        raw_nodes=all_nodes,
        rerank_fn=lambda q, n, top_k, index_name=None: all_nodes[:top_k],
    )

    paths = [n.node.metadata.get("path") for n in decision.nodes]
    assert "docs/pipeline.md" in paths
    assert "pipeline/core.py" in paths
    assert "pipeline/runner.py" in paths
    assert "pipeline/export.py" in paths
    assert len([p for p in paths if p.endswith(".py")]) == 3


def test_doc_priority_inversion_doc_is_genuinely_best_source(tmp_path):
    """When documentation is genuinely the best source (no code matches), Tier 2 is selected."""
    index_name = "test_doc_best_source"
    orch = SharedRetrievalOrchestrator(index_dir=str(tmp_path))

    doc_node = NodeWithScore(
        node=TextNode(text="# Project Roadmap\nFuture features and changelog.", metadata={"path": "CHANGELOG.md"}),
        score=0.89,
    )

    mock_vector = MagicMock()
    decision = orch.orchestrate(
        query="What is on the project roadmap and recent changelog?",
        index_name=index_name,
        vector_index=mock_vector,
        query_mode=QueryMode.CODE_LOOKUP,
        raw_nodes=[doc_node],
        rerank_fn=lambda q, n, top_k, index_name=None: [doc_node],
    )

    assert decision.selected_tier == RetrievalTier.TIER2_DOCUMENTATION
    assert decision.nodes[0].node.metadata.get("path") == "CHANGELOG.md"
    assert decision.should_abstain is False

