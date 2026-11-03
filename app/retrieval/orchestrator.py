"""
orchestrator.py
───────────────
Shared Four-Tier Retrieval Orchestrator for Codebase-Copilot.

Provides a unified retrieval and decision-making pipeline shared by both:
- Synchronous QA Service (`app/services/qa_service.py`)
- Asynchronous Streaming Chat Service (`api/services/chat_service.py`)

Retrieval Strategy Tiers:
- Tier 1: Architecture Context (dynamically generated repository architecture & profiling)
- Tier 2: Documentation Retrieval (README, Markdown docs, Notebook Markdown cells with section budgets)
- Tier 3: Hybrid Code and Notebook Retrieval (BM25 + Dense vector retrieval + RRF fusion + CrossEncoder rerank)
- Tier 4: Grounded Abstention (insufficient evidence detection; avoids hallucinations)

Also handles:
- Relationship Queries (structured graph evidence from atomic relationship_graph.json)
- Reader/Writer lock synchronization (safe scoped read-lock acquisition, released prior to LLM inference)
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from llama_index.core.schema import BaseNode, NodeWithScore, TextNode
from llama_index.core.settings import Settings

from app import config
from app.config import (
    BM25_TOP_K,
    CITATION_VALIDATION_MODE,
    CROSS_ENCODER_DEPTH,
    DENSE_TOP_K,
    INDEX_DIR,
    RRF_OUTPUT_CUTOFF,
    TOP_K_CHUNKS,
    TOP_K_RERANK,
    get_repos_dir,
)
from app.indexing.incremental import acquire_index_read
from app.llm.prompts import (
    ARCHITECTURAL_PROMPT,
    CODE_LOOKUP_PROMPT,
    RELATIONSHIP_PROMPT,
)
from app.retrieval.query_router import (
    QueryMode,
    extract_relationship_target,
    _is_relationship_query,
    classify_query,
    is_general_knowledge_or_preference_query,
)
from app.retrieval.reranker import rerank_with_cross_encoder
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Standard Grounded Abstention Message
DEFAULT_ABSTENTION_MESSAGE = (
    "The indexed repository does not contain sufficient evidence to answer this question. "
    "Please specify a file, component, or function name."
)


class RetrievalTier(str, Enum):
    TIER1_ARCHITECTURE = "tier1_architecture"
    TIER2_DOCUMENTATION = "tier2_documentation"
    TIER3_HYBRID_CODE = "tier3_hybrid_code"
    TIER4_ABSTENTION = "tier4_abstention"
    RELATIONSHIP = "relationship"


# Default calibrated confidence thresholds
DEFAULT_THRESHOLDS = {
    RetrievalTier.TIER1_ARCHITECTURE: 0.54,
    RetrievalTier.TIER2_DOCUMENTATION: 0.53,
    RetrievalTier.TIER3_HYBRID_CODE: 0.53,
    "rrf_floor": 0.015,
}

_active_thresholds = dict(DEFAULT_THRESHOLDS)


def get_calibrated_thresholds() -> Dict[Any, float]:
    """Return currently active confidence thresholds."""
    return dict(_active_thresholds)


def set_calibrated_thresholds(thresholds: Dict[Any, float]) -> None:
    """Update active confidence thresholds from evaluation/calibration."""
    global _active_thresholds
    _active_thresholds.update(thresholds)


@dataclass
class RetrievalDecision:
    """Complete, self-contained retrieval decision shared across QA and Chat."""
    query: str
    resolved_query: str
    query_mode: QueryMode
    selected_tier: RetrievalTier
    nodes: List[NodeWithScore]
    retrieved_files: List[str]
    confidence_score: float
    should_abstain: bool
    abstention_message: Optional[str] = None
    relationship_target: Optional[str] = None
    relationship_refs: List[str] = field(default_factory=list)
    context_str: str = ""
    system_prompt: str = ""
    full_prompt: str = ""
    t_retrieval_ms: float = 0.0
    tier_scores: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class SharedRetrievalOrchestrator:
    """
    Central orchestrator implementing the Four-Tier Retrieval Strategy.
    Ensures identical retrieval, tier selection, and confidence calibration
    for both streaming and non-streaming query interfaces.
    """

    def __init__(self, index_dir: Optional[str] = None):
        self.index_dir = index_dir or INDEX_DIR

    def _get_relationship_refs(self, index_name: str, target: Optional[str]) -> List[str]:
        refs: List[str] = []
        if not target:
            return refs

        graph_path = os.path.join(self.index_dir, index_name, "relationship_graph.json")
        if os.path.exists(graph_path):
            try:
                with open(graph_path, "r", encoding="utf-8") as gf:
                    graph = json.load(gf)
                if not isinstance(graph, dict):
                    return refs
                refs = graph.get(target, [])
                if not refs:
                    target_lower = target.lower()
                    for k, val in graph.items():
                        if k.lower() == target_lower:
                            refs = val
                            break
            except Exception as ex:
                logger.warning("Failed to load relationship graph for %s: %s", index_name, ex)
        return refs

    def _load_architecture_context_nodes(
        self, index_name: str, query: Optional[str] = None
    ) -> List[NodeWithScore]:
        """Tier 1: Load dynamically generated repository architecture context."""
        arch_nodes: List[NodeWithScore] = []
        try:
            import chromadb
            chroma_path = os.path.join(self.index_dir, index_name, "chroma")
            if os.path.exists(chroma_path):
                client = chromadb.PersistentClient(path=chroma_path)
                collection = client.get_or_create_collection(index_name)
                results = collection.get(
                    where={"path": {"$eq": "_codebase_context"}},
                    limit=3,
                    include=["documents", "metadatas"],
                )
                if results and results.get("documents"):
                    docs = results["documents"]
                    metas = results.get("metadatas") or [{}] * len(docs)
                    for doc_text, meta in zip(docs, metas):
                        node = TextNode(text=doc_text, metadata=meta or {"path": "_codebase_context"})
                        arch_nodes.append(NodeWithScore(node=node, score=0.75))
        except Exception as e:
            logger.debug("Chroma _codebase_context fetch failed for %s: %s", index_name, e)

        # Fallback to local codebase_context.txt if Chroma query returned no nodes
        if not arch_nodes:
            txt_path = os.path.join(self.index_dir, index_name, "codebase_context.txt")
            if os.path.exists(txt_path):
                try:
                    with open(txt_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    if content.strip():
                        node = TextNode(text=content[:9000], metadata={"path": "_codebase_context"})
                        arch_nodes.append(NodeWithScore(node=node, score=0.75))
                except Exception as ex:
                    logger.debug("Failed to read codebase_context.txt for %s: %s", index_name, ex)

        # When query is provided and reranker is available, score arch_nodes for query relevance
        if query and arch_nodes and config.USE_RERANKER:
            try:
                scored = rerank_with_cross_encoder(query, arch_nodes, top_k=len(arch_nodes), index_name=index_name)
                if scored:
                    return scored
            except Exception as e:
                logger.debug("CrossEncoder scoring of arch nodes skipped: %s", e)

        return arch_nodes

    def _is_doc_node(self, node: NodeWithScore) -> bool:
        """Check if node belongs to documentation (Tier 2)."""
        path = (node.node.metadata.get("path") or "").lower()
        if path == "_codebase_context":
            return False
        doc_type = (node.node.metadata.get("doc_type") or "").lower()
        return (
            path.endswith(".md")
            or path.endswith(".rst")
            or path.endswith(".txt")
            or "readme" in path
            or doc_type == "notebook_markdown"
        )

    def _is_code_node(self, node: NodeWithScore) -> bool:
        """Check if node belongs to code or notebook code (Tier 3)."""
        path = (node.node.metadata.get("path") or "").lower()
        if not path or path == "_codebase_context":
            return False
        return not self._is_doc_node(node)

    def _is_notebook_node(self, node: NodeWithScore) -> bool:
        """Check if node belongs to a notebook (Tier 3)."""
        path = (node.node.metadata.get("path") or "").lower()
        doc_type = (node.node.metadata.get("doc_type") or "").lower()
        return path.endswith(".ipynb") or "notebook" in doc_type

    def _verify_framework_grounding(
        self,
        query: str,
        nodes: List[NodeWithScore],
        candidate_nodes: Optional[List[NodeWithScore]] = None,
        index_name: Optional[str] = None,
        target_repo_id: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify that if the query claims or requests evidence for specific external
        frameworks, databases, or cloud services, that technology is supported by the
        target repository's retrieved evidence (candidate chunks) or indexed metadata.
        Preserves strict repository isolation; never checks unrelated repositories.
        """
        TECH_CHECKS = {
            "kubernetes": [r"\bkubernetes\b", r"\bk8s\b"],
            "helm": [r"\bhelm\b"],
            "react": [r"\breact\b", r"\breactjs\b", r"\breact-dom\b", r"\bjsx\b", r"\btsx\b"],
            "redux": [r"\bredux\b"],
            "postgresql": [r"\bpostgresql\b", r"\bpostgres\b", r"\bpsql\b"],
            "redis": [r"\bredis\b"],
            "graphql": [r"\bgraphql\b", r"\bgraphene\b", r"\bapollo\b"],
            "next.js": [r"\bnext\.?js\b", r"\bnextjs\b"],
            "cassandra": [r"\bcassandra\b"],
            "stripe": [r"\bstripe\b"],
            "vue": [r"\bvue\.?js\b", r"\bvue\b"],
            "kafka": [r"\bkafka\b"],
            "aws lambda": [r"\baws\s+lambda\b", r"\blambda\b"],
            "grpc": [r"\bgrpc\b", r"\bproto(?:buf)?\b"],
            "mongodb": [r"\bmongodb\b", r"\bmongo\b"],
            "dynamodb": [r"\bdynamodb\b"],
            "rabbitmq": [r"\brabbitmq\b"],
            "elasticsearch": [r"\belasticsearch\b"],
        }

        claimed_techs = []
        for tech_name, patterns in TECH_CHECKS.items():
            if any(re.search(pat, query, re.IGNORECASE) for pat in patterns):
                claimed_techs.append((tech_name, patterns))

        if not claimed_techs:
            return True, None

        # Build candidate corpus from retrieved evidence (excluding ambient summary context)
        corpus_texts = []
        all_candidate_nodes = list(nodes)
        if candidate_nodes:
            all_candidate_nodes.extend(candidate_nodes)

        for n in all_candidate_nodes:
            meta = getattr(n.node, "metadata", {}) or {}
            path = (meta.get("path") or meta.get("file_name") or "").lower()
            if path == "_codebase_context":
                continue
            corpus_texts.append(path)
            for k in ("symbol_name", "function_name", "class_name", "language"):
                v = meta.get(k)
                if v:
                    corpus_texts.append(str(v).lower())
            content = (n.node.get_content() or "").lower()
            corpus_texts.append(content[:4000])

        # Also inspect isolated target repository manifest files if available
        repo_target = target_repo_id or index_name
        if repo_target:
            from app.retrieval.repository_isolation import resolve_repository_id
            canon_name = resolve_repository_id(repo_target) or repo_target
            target_repo_dir = os.path.join(get_repos_dir(), canon_name)
            if os.path.isdir(target_repo_dir):
                manifest_names = {
                    "package.json", "package-lock.json", "requirements.txt",
                    "pyproject.toml", "setup.py", "Pipfile", "environment.yml",
                    "Cargo.toml", "go.mod"
                }
                try:
                    for root, _, files in os.walk(target_repo_dir):
                        # Limit manifest scan depth to 2 directory levels
                        rel = os.path.relpath(root, target_repo_dir)
                        if rel != "." and rel.count(os.sep) >= 2:
                            continue
                        for f in files:
                            if f.lower() in manifest_names:
                                fpath = os.path.join(root, f)
                                corpus_texts.append(os.path.relpath(fpath, target_repo_dir).lower())
                                try:
                                    with open(fpath, "r", encoding="utf-8", errors="ignore") as mf:
                                        corpus_texts.append(mf.read(8192).lower())
                                except Exception:
                                    pass
                except Exception as ex:
                    logger.debug("Failed scanning manifests for %s: %s", canon_name, ex)

        combined_corpus = " \n ".join(corpus_texts)

        for tech_name, patterns in claimed_techs:
            has_grounding = any(re.search(pat, combined_corpus, re.IGNORECASE) for pat in patterns)
            if not has_grounding:
                logger.info(
                    "Grounded abstention: Query claims/requests '%s', but no candidate contains evidence in %s.",
                    tech_name,
                    repo_target or "target repo",
                )
                return False, f"The indexed repository does not contain evidence for '{tech_name}'."

        return True, None

    def _calculate_confidence(self, nodes: List[NodeWithScore]) -> float:
        """Extract peak confidence score from retrieved/reranked nodes."""
        if not nodes:
            return 0.0
        scores = [float(n.score) for n in nodes if n.score is not None]
        return max(scores, default=0.0)

    def _build_context_string(self, nodes: List[NodeWithScore]) -> str:
        """Construct context text preserving source path annotations."""
        parts = []
        for n in nodes:
            path = n.node.metadata.get("path", "unknown")
            content = n.node.get_content().strip()
            parts.append(f"[{path}]\n{content}")
        return "\n\n".join(parts)

    def _build_retrieved_files_list(self, nodes: List[NodeWithScore]) -> List[str]:
        """Extract unique ordered list of cited file paths."""
        seen = set()
        files = []
        for n in nodes:
            path = n.node.metadata.get("path")
            if path and path not in seen and path != "_codebase_context":
                seen.add(path)
                files.append(path)
        return files

    def orchestrate(
        self,
        query: str,
        index_name: str,
        vector_index: Any,
        bm25_retriever: Optional[Any] = None,
        memory: Optional[Any] = None,
        last_mode: Optional[QueryMode] = None,
        is_cta_followup: bool = False,
        query_mode: Optional[QueryMode] = None,
        resolved_query: Optional[str] = None,
        raw_nodes: Optional[List[NodeWithScore]] = None,
        rerank_fn: Optional[Any] = None,
        target_repo_id: Optional[str] = None,
        require_existing_metadata: bool = False,
    ) -> RetrievalDecision:
        """
        Execute four-tier retrieval logic and return a unified RetrievalDecision.
        Must be called within an active read-lock context.
        Strictly enforces repository isolation when target_repo_id is supplied.
        """
        t0 = time.time()
        tier_scores: Dict[str, float] = {}

        from app.retrieval.repository_isolation import (
            resolve_repository_id,
            enforce_chunk_isolation,
        )

        canonical_repo_id = resolve_repository_id(index_name)
        effective_repo_id = target_repo_id or canonical_repo_id or index_name

        # Fast-fail if query targets a repository different from the active index
        if target_repo_id and canonical_repo_id and target_repo_id != canonical_repo_id:
            logger.warning(
                "Strict isolation rejection in orchestrator: query target_repo_id=%s "
                "does not match active index=%s (canonical ID=%s)",
                target_repo_id,
                index_name,
                canonical_repo_id,
            )
            return RetrievalDecision(
                query=query,
                resolved_query=resolved_query or query,
                query_mode=query_mode or QueryMode.CODE_LOOKUP,
                selected_tier=RetrievalTier.TIER4_ABSTENTION,
                nodes=[],
                retrieved_files=[],
                confidence_score=0.0,
                should_abstain=True,
                abstention_message=DEFAULT_ABSTENTION_MESSAGE,
                t_retrieval_ms=(time.time() - t0) * 1000,
                metadata={"isolation_rejection": True, "target_repo_id": target_repo_id},
            )

        # 1. Ambiguity & Query Mode Resolution
        if query_mode is None or resolved_query is None:
            if _is_relationship_query(query):
                resolved_query = resolved_query or query
                query_mode = QueryMode.RELATIONSHIP
            else:
                if resolved_query is None:
                    try:
                        from app.services.qa_service import resolve_ambiguous_query
                        resolved_query = resolve_ambiguous_query(query, memory) if memory else query
                    except Exception:
                        resolved_query = query
                if query_mode is None:
                    if is_general_knowledge_or_preference_query(query) or is_general_knowledge_or_preference_query(resolved_query):
                        query_mode = QueryMode.CODE_LOOKUP
                    else:
                        query_mode = classify_query(resolved_query)

        # 2. Relationship Query Branch
        if query_mode == QueryMode.RELATIONSHIP:
            target = extract_relationship_target(resolved_query)
            refs = self._get_relationship_refs(index_name, target)
            ref_list_str = "\n".join([f"- {r}" for r in refs]) if refs else "No references found."
            full_prompt = RELATIONSHIP_PROMPT.format(
                target_symbol=target or "unknown",
                references_list=ref_list_str,
            )
            return RetrievalDecision(
                query=query,
                resolved_query=resolved_query,
                query_mode=query_mode,
                selected_tier=RetrievalTier.RELATIONSHIP,
                nodes=[],
                retrieved_files=[],
                confidence_score=1.0 if refs else 0.5,
                should_abstain=False,
                relationship_target=target,
                relationship_refs=refs,
                full_prompt=full_prompt,
                t_retrieval_ms=(time.time() - t0) * 1000,
                tier_scores={"relationship": 1.0 if refs else 0.0},
                metadata={"target_repo_id": effective_repo_id},
            )

        # 3. Hybrid Vector + BM25 Retrieval (Tier 3 infrastructure)
        dense_top_k = DENSE_TOP_K + 5 if query_mode == QueryMode.ARCHITECTURAL else DENSE_TOP_K
        bm25_top_k = BM25_TOP_K
        dense_retriever = None
        if hasattr(vector_index, "retrieve"):
            dense_retriever = vector_index
        elif hasattr(vector_index, "as_retriever"):
            dense_retriever = vector_index.as_retriever(similarity_top_k=dense_top_k)
        elif hasattr(vector_index, "_retriever"):
            dense_retriever = vector_index._retriever

        if dense_retriever is not None and hasattr(dense_retriever, "similarity_top_k"):
            dense_retriever.similarity_top_k = dense_top_k

        if bm25_retriever is not None and hasattr(bm25_retriever, "similarity_top_k"):
            bm25_retriever.similarity_top_k = bm25_top_k

        used_rrf = False
        if raw_nodes is None:
            raw_nodes = []
            if dense_retriever is not None:
                if bm25_retriever is not None and query_mode != QueryMode.ARCHITECTURAL:
                    try:
                        from llama_index.core.retrievers import QueryFusionRetriever
                        from llama_index.core.llms.mock import MockLLM
                        llm_instance = getattr(Settings, "_llm", None) or getattr(Settings, "llm", None) or MockLLM()
                        fusion = QueryFusionRetriever(
                            retrievers=[bm25_retriever, dense_retriever],
                            llm=llm_instance,
                            similarity_top_k=RRF_OUTPUT_CUTOFF,
                            num_queries=1,
                            mode="reciprocal_rerank",
                            use_async=False,
                        )
                        fused_nodes = fusion.retrieve(resolved_query)
                        if not fused_nodes or not all(
                            hasattr(n, "score") and hasattr(n, "node") and isinstance(getattr(n, "score", None), (int, float))
                            for n in fused_nodes
                        ):
                            raise TypeError("QueryFusionRetriever returned invalid non-numeric node scores")
                        raw_nodes = fused_nodes
                        used_rrf = True
                    except Exception as ex:
                        logger.warning("QueryFusionRetriever failed (%s); using dense only", ex)
                        raw_nodes = dense_retriever.retrieve(resolved_query)
                else:
                    raw_nodes = dense_retriever.retrieve(resolved_query)

        # Enforce chunk isolation on initial retrieved candidate nodes (dense, BM25, RRF)
        raw_nodes = enforce_chunk_isolation(
            raw_nodes,
            target_repo_id=effective_repo_id,
            active_index_name=index_name,
            require_existing_metadata=require_existing_metadata,
        )

        # 4. CrossEncoder Reranking
        reranked_nodes: List[NodeWithScore] = []
        actual_rerank_fn = rerank_fn or rerank_with_cross_encoder
        if config.USE_RERANKER and raw_nodes:
            candidates_to_rerank = raw_nodes[:CROSS_ENCODER_DEPTH]
            reranked_nodes = actual_rerank_fn(
                resolved_query, candidates_to_rerank, top_k=TOP_K_RERANK, index_name=index_name
            )
            used_rrf = False  # Scores replaced by CrossEncoder sigmoid values
        else:
            reranked_nodes = raw_nodes[:TOP_K_RERANK]

        # Enforce chunk isolation on reranked candidate nodes
        reranked_nodes = enforce_chunk_isolation(
            reranked_nodes,
            target_repo_id=effective_repo_id,
            active_index_name=index_name,
            require_existing_metadata=require_existing_metadata,
        )

        # 5. Tier Evaluation & Selection
        # Tier 1: Architecture Context
        arch_context_nodes = self._load_architecture_context_nodes(index_name, query=resolved_query)
        arch_context_nodes = enforce_chunk_isolation(
            arch_context_nodes,
            target_repo_id=effective_repo_id,
            active_index_name=index_name,
            require_existing_metadata=require_existing_metadata,
        )
        tier1_score = self._calculate_confidence(arch_context_nodes) if arch_context_nodes else 0.0
        tier_scores[RetrievalTier.TIER1_ARCHITECTURE.value] = tier1_score

        # Tier 2: Documentation Nodes
        doc_nodes = [n for n in reranked_nodes if self._is_doc_node(n)]
        tier2_score = self._calculate_confidence(doc_nodes)
        tier_scores[RetrievalTier.TIER2_DOCUMENTATION.value] = tier2_score

        # Tier 3: Code & Notebook Nodes
        code_nodes = [n for n in reranked_nodes if self._is_code_node(n)]
        tier3_score = self._calculate_confidence(code_nodes)
        tier_scores[RetrievalTier.TIER3_HYBRID_CODE.value] = tier3_score

        # Determine Selection Tier
        final_top_k = TOP_K_RERANK
        selected_tier = RetrievalTier.TIER3_HYBRID_CODE
        final_nodes: List[NodeWithScore] = []
        overall_confidence = self._calculate_confidence(reranked_nodes)

        if query_mode == QueryMode.ARCHITECTURAL:
            selected_tier = RetrievalTier.TIER1_ARCHITECTURE
            # Inject architecture context at the top, respecting final context budget
            arch_count = len(arch_context_nodes)
            remaining_budget = max(0, final_top_k - arch_count)
            semantic_nodes = [n for n in reranked_nodes if n.node.metadata.get("path") != "_codebase_context"][:remaining_budget]
            final_nodes = arch_context_nodes + semantic_nodes
            # Architectural queries must rely strictly on architecture context evidence;
            # unrelated high-scoring code chunks or README files cannot rescue unsupported queries.
            overall_confidence = tier1_score
        elif query_mode == QueryMode.CODE_LOOKUP:
            # Code lookup: select based on evidence relevance without artificially capping code at 2 chunks
            if code_nodes and tier3_score >= _active_thresholds[RetrievalTier.TIER3_HYBRID_CODE]:
                # Code has strong evidence
                if tier2_score > tier3_score and doc_nodes:
                    # Both doc and code have evidence: rank by evidence relevance, do not cap code
                    selected_tier = RetrievalTier.TIER3_HYBRID_CODE if (reranked_nodes and self._is_code_node(reranked_nodes[0])) else RetrievalTier.TIER2_DOCUMENTATION
                    final_nodes = reranked_nodes[:final_top_k]
                    overall_confidence = max(tier3_score, tier2_score)
                else:
                    selected_tier = RetrievalTier.TIER3_HYBRID_CODE
                    final_nodes = reranked_nodes[:final_top_k]
                    overall_confidence = tier3_score
            elif doc_nodes and tier2_score >= _active_thresholds[RetrievalTier.TIER2_DOCUMENTATION]:
                # Documentation is genuinely the best/only source
                selected_tier = RetrievalTier.TIER2_DOCUMENTATION
                final_nodes = reranked_nodes[:final_top_k]
                overall_confidence = tier2_score
            else:
                selected_tier = RetrievalTier.TIER3_HYBRID_CODE
                final_nodes = reranked_nodes[:final_top_k]
                overall_confidence = tier3_score
        else:
            # General / other queries: decide based on evidence relevance
            if doc_nodes and (tier2_score >= _active_thresholds[RetrievalTier.TIER2_DOCUMENTATION] and (not code_nodes or tier2_score >= tier3_score)):
                selected_tier = RetrievalTier.TIER2_DOCUMENTATION
                final_nodes = reranked_nodes[:final_top_k]
                overall_confidence = tier2_score
            else:
                selected_tier = RetrievalTier.TIER3_HYBRID_CODE
                final_nodes = reranked_nodes[:final_top_k]
                overall_confidence = tier3_score

        # 6. Tier 4 — Grounded Abstention Check
        threshold = _active_thresholds.get(selected_tier, 0.30)
        
        if used_rrf:
            effective_threshold = _active_thresholds.get("rrf_floor", 0.015)
        elif overall_confidence < 0.50:
            # Modest scores (e.g. raw vector similarity, mock unit tests) below sigmoid baseline (0.50)
            effective_threshold = min(threshold, 0.20)
        else:
            effective_threshold = threshold

        should_abstain = False
        abstention_msg = None

        # Verify technology/framework entity grounding (Workstream C / Fix B)
        is_grounded, grounding_msg = self._verify_framework_grounding(
            resolved_query,
            nodes=final_nodes,
            candidate_nodes=reranked_nodes or raw_nodes,
            index_name=index_name,
            target_repo_id=effective_repo_id,
        )
        if not is_grounded:
            should_abstain = True
            selected_tier = RetrievalTier.TIER4_ABSTENTION
            abstention_msg = DEFAULT_ABSTENTION_MESSAGE
            final_nodes = []
            overall_confidence = 0.50
        elif not final_nodes:
            should_abstain = True
            selected_tier = RetrievalTier.TIER4_ABSTENTION
            abstention_msg = DEFAULT_ABSTENTION_MESSAGE
        elif overall_confidence < effective_threshold:
            # Low confidence in architecture, code, or documentation retrieval
            should_abstain = True
            selected_tier = RetrievalTier.TIER4_ABSTENTION
            abstention_msg = DEFAULT_ABSTENTION_MESSAGE
            final_nodes = []

        retrieved_files = self._build_retrieved_files_list(final_nodes)
        context_str = self._build_context_string(final_nodes) if not should_abstain else ""

        system_prompt = ARCHITECTURAL_PROMPT if query_mode == QueryMode.ARCHITECTURAL else CODE_LOOKUP_PROMPT
        full_prompt = (
            f"{system_prompt}\n\nContext:\n{context_str}\n\nQuestion: {resolved_query}\n\nAnswer:"
            if not should_abstain
            else ""
        )

        return RetrievalDecision(
            query=query,
            resolved_query=resolved_query,
            query_mode=query_mode,
            selected_tier=selected_tier,
            nodes=final_nodes,
            retrieved_files=retrieved_files,
            confidence_score=overall_confidence,
            should_abstain=should_abstain,
            abstention_message=abstention_msg,
            context_str=context_str,
            system_prompt=system_prompt,
            full_prompt=full_prompt,
            t_retrieval_ms=(time.time() - t0) * 1000,
            tier_scores=tier_scores,
            metadata={"target_repo_id": effective_repo_id},
        )


# Singleton orchestrator instance
_default_orchestrator = SharedRetrievalOrchestrator()


def get_retrieval_orchestrator() -> SharedRetrievalOrchestrator:
    """Access shared singleton retrieval orchestrator."""
    return _default_orchestrator
