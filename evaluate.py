"""
evaluate.py
───────────
Evaluation suite for Codebase Copilot.

Measures:
  RETRIEVAL QUALITY
    - Hit Rate      : is the relevant chunk in top-k?
    - MRR           : mean reciprocal rank of first relevant chunk

  ANSWER QUALITY  (LLM-as-judge, fully local via Ollama)
    - Faithfulness  : is the answer grounded in retrieved context?
    - Relevancy     : does the answer address the question?

  SYSTEM PERFORMANCE
    - End-to-end latency
    - Retrieval latency
    - Reranking latency (ColBERT overhead)
    - LLM latency
    - Query routing accuracy

HOW TO RUN:
  1. Make sure your repo is already indexed (run the app and process a repo first)
  2. Edit EVAL_CONFIG at the bottom of this file:
       - Set INDEX_NAME to your indexed repo name
       - Set REPO_PATH to the local path of that repo
  3. Run:
       python evaluate.py
  4. Results are printed to console AND saved to data/eval_results.json

WHAT TO DO WITH RESULTS:
  - Hit Rate > 0.7  → retrieval is working well
  - MRR > 0.5       → relevant chunks are ranking near the top
  - Faithfulness > 0.7 → LLM is staying grounded, not hallucinating
  - Relevancy > 0.7    → answers are on-topic
  - If any metric is low, see the "Diagnosis" section printed at the end

ADDING YOUR OWN TEST QUESTIONS:
  Edit the EVAL_DATASET list below. Each entry needs:
    - question: the query to test
    - expected_files: list of file paths that SHOULD appear in retrieved chunks
    - expected_keywords: words that should appear in the answer
    - mode: "code_lookup" or "architectural" (what the router should classify it as)
"""

import os
import sys
import json
import time
from dataclasses import dataclass, field, asdict
from typing import List, Optional
from statistics import mean

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from llama_index.core import Settings
from llama_index.core.evaluation import (
    FaithfulnessEvaluator,
    RelevancyEvaluator,
)

from app.llm.llm_client import get_llm, get_embed_model
from app.services.qa_service import handle_user_query, _get_indexes
from app.retrieval.query_router import classify_query, QueryMode
from app.utils.logger import get_logger

logger = get_logger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# EVAL DATASET
# Edit this for your specific repo. Examples below are for codebase-copilot itself.
# ══════════════════════════════════════════════════════════════════════════════

EVAL_DATASET = [
    # ── CODE LOOKUP queries ───────────────────────────────────────────────
    {
        "question": "How does the retrieve_relevant_chunks function work?",
        "expected_files": ["app/retrieval/retriever.py"],
        "expected_keywords": ["retriev", "chunk", "vector", "query"],
        "mode": "code_lookup",
    },
    {
        "question": "What does the chunk_text function do and what parameters does it take?",
        "expected_files": ["app/parsing/chunk_utils.py"],
        "expected_keywords": ["chunk", "overlap", "max_chunk_size"],
        "mode": "code_lookup",
    },
    {
        "question": "How is the vector store saved to disk?",
        "expected_files": ["app/indexing/vector_store.py", "app/indexing/index_builder.py"],
        "expected_keywords": ["save", "pickle", "embeddings", "json"],
        "mode": "code_lookup",
    },
    {
        "question": "What LLM providers are supported?",
        "expected_files": ["app/llm/llm_client.py", "app/config.py"],
        "expected_keywords": ["gemini", "ollama", "groq", "fallback"],
        "mode": "code_lookup",
    },
    {
        "question": "How does the file filter decide which files to include?",
        "expected_files": ["app/ingestion/file_filter.py"],
        "expected_keywords": ["extension", "ignore", "valid"],
        "mode": "code_lookup",
    },

    # ── ARCHITECTURAL queries ─────────────────────────────────────────────
    {
        "question": "What are the main limitations of this project?",
        "expected_files": ["_codebase_context"],
        "expected_keywords": ["limitation", "improvement", "issue"],
        "mode": "architectural",
    },
    {
        "question": "How could the retrieval quality be improved?",
        "expected_files": ["_codebase_context"],
        "expected_keywords": ["retriev", "embed", "chunk", "improve"],
        "mode": "architectural",
    },
    {
        "question": "What design patterns are used in this codebase?",
        "expected_files": ["_codebase_context"],
        "expected_keywords": ["pattern", "service", "pipeline"],
        "mode": "architectural",
    },
    {
        "question": "Give me an overview of how the indexing pipeline works",
        "expected_files": ["_codebase_context", "app/services/repo_service.py", "app/indexing/index_builder.py"],
        "expected_keywords": ["index", "embed", "chunk", "store"],
        "mode": "architectural",
    },
    {
        "question": "What would you add to make this production ready?",
        "expected_files": ["_codebase_context"],
        "expected_keywords": [],   # open-ended — no keyword check
        "mode": "architectural",
    },
]


# ══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class QueryResult:
    question:           str
    expected_mode:      str
    actual_mode:        str
    mode_correct:       bool

    retrieved_files:    List[str]
    expected_files:     List[str]
    hit:                bool          # any expected file in top-k?
    reciprocal_rank:    float         # 1/rank of first hit, 0 if miss

    answer:             str
    faithfulness_score: Optional[float]
    relevancy_score:    Optional[float]
    keywords_found:     List[str]
    keyword_hit_rate:   float

    latency_total:      float
    latency_retrieval:  float
    latency_rerank:     float
    latency_llm:        float


@dataclass
class EvalSummary:
    total_queries:      int
    hit_rate:           float
    mrr:                float
    avg_faithfulness:   float
    avg_relevancy:      float
    avg_keyword_hit:    float
    mode_accuracy:      float
    avg_latency_total:  float
    avg_latency_retrieval: float
    avg_latency_rerank: float
    avg_latency_llm:    float
    colbert_enabled:    bool
    results:            List[dict] = field(default_factory=list)


# ══════════════════════════════════════════════════════════════════════════════
# LATENCY-INSTRUMENTED RETRIEVAL
# ══════════════════════════════════════════════════════════════════════════════

def retrieve_with_timing(query: str, index_name: str):
    """
    Run retrieval and reranking separately from the LLM call
    so we can measure each component's latency independently.
    Returns (nodes, retrieved_files, latency_retrieval, latency_rerank)
    """
    from app.config import USE_RERANKER, TOP_K_CHUNKS, TOP_K_RERANK
    from app.retrieval.reranker import rerank_with_cross_encoder

    vector_index, bm25_retriever = _get_indexes(index_name)

    # ── Retrieval timing ──────────────────────────────────────────────────
    t0 = time.time()

    if bm25_retriever is not None:
        from llama_index.core.retrievers import QueryFusionRetriever
        retriever = QueryFusionRetriever(
            retrievers=[
                bm25_retriever,
                vector_index.as_retriever(similarity_top_k=TOP_K_CHUNKS),
            ],
            similarity_top_k=TOP_K_CHUNKS,
            num_queries=1,
            mode="reciprocal_rerank",
            use_async=False,
        )
    else:
        retriever = vector_index.as_retriever(similarity_top_k=TOP_K_CHUNKS)

    raw_nodes = retriever.retrieve(query)
    latency_retrieval = time.time() - t0

    # ── Reranking timing ──────────────────────────────────────────────────
    t1 = time.time()
    if USE_RERANKER:
        final_nodes = rerank_with_cross_encoder(query, raw_nodes, top_k=TOP_K_RERANK, index_name=index_name)
    else:
        final_nodes = sorted(raw_nodes, key=lambda n: n.score or 0, reverse=True)[:TOP_K_RERANK]
    latency_rerank = time.time() - t1

    retrieved_files = list({
        n.node.metadata.get("path", "unknown")
        for n in final_nodes
    })

    return final_nodes, retrieved_files, latency_retrieval, latency_rerank


# ══════════════════════════════════════════════════════════════════════════════
# SINGLE QUERY EVALUATION
# ══════════════════════════════════════════════════════════════════════════════

def evaluate_single(
    item: dict,
    index_name: str,
    faithfulness_evaluator: FaithfulnessEvaluator,
    relevancy_evaluator: RelevancyEvaluator,
) -> QueryResult:

    question        = item["question"]
    expected_files  = item["expected_files"]
    expected_mode   = item["mode"]
    expected_kws    = item.get("expected_keywords", [])

    print(f"\n  Q: {question[:70]}...")

    # ── Route classification ──────────────────────────────────────────────
    actual_mode_enum = classify_query(question)
    actual_mode      = actual_mode_enum.value
    mode_correct     = actual_mode == expected_mode
    print(f"  Mode: {actual_mode} ({'✓' if mode_correct else '✗ expected ' + expected_mode})")

    # ── Retrieval + rerank (timed) ────────────────────────────────────────
    nodes, retrieved_files, lat_retrieval, lat_rerank = retrieve_with_timing(
        question, index_name
    )
    print(f"  Retrieved: {retrieved_files}")
    print(f"  Retrieval: {lat_retrieval:.2f}s | Rerank: {lat_rerank:.2f}s")

    # ── Hit rate & MRR ────────────────────────────────────────────────────
    hit = False
    reciprocal_rank = 0.0

    for rank, node in enumerate(nodes, 1):
        node_path = node.node.metadata.get("path", "")
        for ef in expected_files:
            if ef in node_path or node_path in ef:
                hit = True
                if reciprocal_rank == 0.0:
                    reciprocal_rank = 1.0 / rank
                break

    print(f"  Hit: {'✓' if hit else '✗'} | RR: {reciprocal_rank:.2f}")

    # ── LLM answer (timed) ───────────────────────────────────────────────
    t_llm = time.time()
    response, _, _, _ = handle_user_query(
        query=question,
        index_name=index_name,
    )
    lat_llm = time.time() - t_llm
    lat_total = lat_retrieval + lat_rerank + lat_llm

    print(f"  LLM: {lat_llm:.2f}s | Total: {lat_total:.2f}s")

    # ── Keyword check ─────────────────────────────────────────────────────
    answer_lower   = response.lower()
    keywords_found = [kw for kw in expected_kws if kw.lower() in answer_lower]
    kw_hit_rate    = len(keywords_found) / len(expected_kws) if expected_kws else 1.0

    # ── LLM-as-judge: Faithfulness ────────────────────────────────────────
    context_str = "\n".join([n.node.get_content()[:500] for n in nodes])
    faithfulness_score = None
    relevancy_score    = None

    try:
        from llama_index.core import QueryBundle
        faith_result = faithfulness_evaluator.evaluate(
            query=question,
            response=response,
            contexts=[context_str],
        )
        faithfulness_score = float(faith_result.score) if faith_result.score is not None else None
        print(f"  Faithfulness: {faithfulness_score}")
    except Exception as e:
        print(f"  Faithfulness eval failed: {e}")

    try:
        rel_result = relevancy_evaluator.evaluate(
            query=question,
            response=response,
            contexts=[context_str],
        )
        relevancy_score = float(rel_result.score) if rel_result.score is not None else None
        print(f"  Relevancy: {relevancy_score}")
    except Exception as e:
        print(f"  Relevancy eval failed: {e}")

    return QueryResult(
        question           = question,
        expected_mode      = expected_mode,
        actual_mode        = actual_mode,
        mode_correct       = mode_correct,
        retrieved_files    = retrieved_files,
        expected_files     = expected_files,
        hit                = hit,
        reciprocal_rank    = reciprocal_rank,
        answer             = response,
        faithfulness_score = faithfulness_score,
        relevancy_score    = relevancy_score,
        keywords_found     = keywords_found,
        keyword_hit_rate   = kw_hit_rate,
        latency_total      = lat_total,
        latency_retrieval  = lat_retrieval,
        latency_rerank     = lat_rerank,
        latency_llm        = lat_llm,
    )


# ══════════════════════════════════════════════════════════════════════════════
# FULL EVAL RUN
# ══════════════════════════════════════════════════════════════════════════════

def run_evaluation(index_name: str) -> EvalSummary:
    from app.config import USE_RERANKER

    index_name = (index_name or "").strip()
    if not index_name:
        raise ValueError("index_name cannot be empty. Re-index the repository and retry evaluation.")

    print("\n" + "━" * 60)
    print("  CODEBASE COPILOT — EVALUATION SUITE")
    print("━" * 60)
    print(f"  Index:   {index_name}")
    print(f"  Queries: {len(EVAL_DATASET)}")
    print(f"  Reranker: {'ON' if USE_RERANKER else 'OFF'}")
    print("━" * 60)

    # ── LLM-as-judge evaluators ───────────────────────────────────────────
    faithfulness_evaluator = FaithfulnessEvaluator(llm=Settings.llm)
    relevancy_evaluator    = RelevancyEvaluator(llm=Settings.llm)

    results = []
    for i, item in enumerate(EVAL_DATASET, 1):
        print(f"\n[{i}/{len(EVAL_DATASET)}]")
        try:
            result = evaluate_single(
                item, index_name,
                faithfulness_evaluator,
                relevancy_evaluator,
            )
            results.append(result)
        except Exception as e:
            print(f"  ERROR: {e}")
            logger.error(f"Eval failed for '{item['question']}': {e}", exc_info=True)

    if not results:
        print("No results collected.")
        return None

    # ── Aggregate metrics ─────────────────────────────────────────────────
    hit_rate       = mean([r.hit for r in results])
    mrr            = mean([r.reciprocal_rank for r in results])
    mode_accuracy  = mean([r.mode_correct for r in results])
    avg_kw         = mean([r.keyword_hit_rate for r in results])

    faith_scores = [r.faithfulness_score for r in results if r.faithfulness_score is not None]
    rel_scores   = [r.relevancy_score    for r in results if r.relevancy_score    is not None]

    avg_faith = mean(faith_scores) if faith_scores else 0.0
    avg_rel   = mean(rel_scores)   if rel_scores   else 0.0

    avg_total     = mean([r.latency_total     for r in results])
    avg_retrieval = mean([r.latency_retrieval for r in results])
    avg_rerank    = mean([r.latency_rerank    for r in results])
    avg_llm       = mean([r.latency_llm       for r in results])

    summary = EvalSummary(
        total_queries         = len(results),
        hit_rate              = hit_rate,
        mrr                   = mrr,
        avg_faithfulness      = avg_faith,
        avg_relevancy         = avg_rel,
        avg_keyword_hit       = avg_kw,
        mode_accuracy         = mode_accuracy,
        avg_latency_total     = avg_total,
        avg_latency_retrieval = avg_retrieval,
        avg_latency_rerank    = avg_rerank,
        avg_latency_llm       = avg_llm,
        colbert_enabled       = USE_RERANKER,
        results               = [asdict(r) for r in results],
    )

    return summary


# ══════════════════════════════════════════════════════════════════════════════
# REPORTING
# ══════════════════════════════════════════════════════════════════════════════

def print_report(summary: EvalSummary):
    print("\n" + "━" * 60)
    print("  RESULTS")
    print("━" * 60)

    def bar(score, width=20):
        filled = int(score * width)
        return "█" * filled + "░" * (width - filled)

    def grade(score):
        if score >= 0.8: return "✅ GOOD"
        if score >= 0.6: return "⚠️  OK"
        return "❌ NEEDS WORK"

    print(f"\n  RETRIEVAL QUALITY")
    print(f"  Hit Rate   {bar(summary.hit_rate)} {summary.hit_rate:.2f}  {grade(summary.hit_rate)}")
    print(f"  MRR        {bar(summary.mrr)}      {summary.mrr:.2f}  {grade(summary.mrr)}")

    print(f"\n  ANSWER QUALITY  (LLM-as-judge)")
    print(f"  Faithfulness {bar(summary.avg_faithfulness)} {summary.avg_faithfulness:.2f}  {grade(summary.avg_faithfulness)}")
    print(f"  Relevancy    {bar(summary.avg_relevancy)}    {summary.avg_relevancy:.2f}  {grade(summary.avg_relevancy)}")
    print(f"  Keywords     {bar(summary.avg_keyword_hit)}  {summary.avg_keyword_hit:.2f}  {grade(summary.avg_keyword_hit)}")

    print(f"\n  ROUTING ACCURACY")
    print(f"  Mode correct {bar(summary.mode_accuracy)} {summary.mode_accuracy:.2f}  {grade(summary.mode_accuracy)}")

    print(f"\n  LATENCY BREAKDOWN  (avg over {summary.total_queries} queries)")
    print(f"  Total      {summary.avg_latency_total:.2f}s")
    print(f"  Retrieval  {summary.avg_latency_retrieval:.2f}s  ({100*summary.avg_latency_retrieval/summary.avg_latency_total:.0f}%)")
    print(f"  Reranking  {summary.avg_latency_rerank:.2f}s  ({100*summary.avg_latency_rerank/summary.avg_latency_total:.0f}%)")
    print(f"  LLM        {summary.avg_latency_llm:.2f}s  ({100*summary.avg_latency_llm/summary.avg_latency_total:.0f}%)")
    print(f"  Reranker:  {'ON' if summary.colbert_enabled else 'OFF'}")

    print(f"\n  DIAGNOSIS")
    if summary.hit_rate < 0.6:
        print("  ❌ Hit rate low → chunks not being retrieved.")
        print("     Try: increase TOP_K_CHUNKS in config.py")
        print("     Try: check that expected_files paths match actual paths")
    if summary.mrr < 0.4:
        print("  ❌ MRR low → right chunks retrieved but ranked poorly.")
        print("     Try: enable CrossEncoder reranking (USE_RERANKER=True)")
    if summary.avg_faithfulness < 0.6:
        print("  ❌ Faithfulness low → LLM may be hallucinating.")
        print("     Try: tighten CODE_LOOKUP_PROMPT in prompts.py")
        print("     Try: reduce TOP_K_RERANK so only strongest chunks reach LLM")
    if summary.avg_relevancy < 0.6:
        print("  ❌ Relevancy low → answers not addressing the question.")
        print("     Try: improve query routing (check mode_accuracy first)")
    if summary.mode_accuracy < 0.8:
        print("  ❌ Routing accuracy low → wrong mode being selected.")
        print("     Try: add more keywords to _ARCHITECTURAL_KEYWORDS / _CODE_KEYWORDS")
        print("     in query_router.py for the query types that are misrouted")
    if summary.avg_latency_rerank > 5.0:
        print("  ⚠️  CrossEncoder reranking slow (>5s avg).")
        print("     Consider: USE_RERANKER=False for faster responses")

    if all([
        summary.hit_rate >= 0.7,
        summary.mrr >= 0.5,
        summary.avg_faithfulness >= 0.7,
        summary.avg_relevancy >= 0.7,
        summary.mode_accuracy >= 0.8,
    ]):
        print("  ✅ All metrics healthy — system is working well.")

    print("━" * 60)


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

# ── EDIT THESE ────────────────────────────────────────────────────────────────
EVAL_CONFIG = {
    "index_name": "Codebase-Copilot",   # folder name of the indexed repo
}
# ─────────────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    # Configure LlamaIndex
    Settings.llm         = get_llm()
    Settings.embed_model = get_embed_model()

    index_name = EVAL_CONFIG["index_name"]

    summary = run_evaluation(index_name)

    if summary:
        print_report(summary)

        # Save full results to disk
        out_path = os.path.join("data", "eval_results-online-llama8b.json")
        os.makedirs("data", exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(asdict(summary), f, indent=2)
        print(f"\n  Full results saved to: {out_path}")