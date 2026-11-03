"""
evaluation/e2e/final_expansion/run_stabilization_evaluation.py
─────────────────────────────────────────────────────────────
Final stabilization evaluation runner for Codebase-Copilot.
Runs one final evaluation pass over:
1. Original 40-query holdout dataset (SenseVoice & Speech-Emotion-Analyzer)
2. Frozen 100-query expansion dataset (FedSegX, Sound2Sign, Emotion-detection, NeuroVera)

Measures:
- Recall@1, Recall@3, Recall@5
- MRR and nDCG@5
- FAR (with explicit denominator)
- FRR (with explicit denominator)
- Breakdown by query answerability: fully answerable, partially answerable, zero index coverage, unsupported
- Per-repository and per-category breakdowns
- Latency (retrieval + reranking)
- Relevant chunk promotions and demotions relative to frozen baseline
- Documentation vs Implementation evidence distribution
"""

from __future__ import annotations

import os
import sys
import json
import math
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.llm.llm_client import configure_llamaindex_settings
from app.indexing.incremental import acquire_index_read
from app.retrieval.orchestrator import (
    SharedRetrievalOrchestrator,
    RetrievalDecision,
    get_retrieval_orchestrator,
)
from app.retrieval.repository_isolation import verify_chunk_isolation
from app.services.qa_service import _get_indexes
from evaluation.e2e.evaluate_pass2_calibration import HOLDOUT_DATASET


REPO_ID_MAP = {
    "SenseVoice": "296ee64c-a989-48ff-9ded-a3e1bb09b63f",
    "Speech-Emotion-Analyzer": "7f25a956-b13d-4098-8a40-5e8731946705",
    "FedSegX": "bc5f54ec-7113-4132-b39e-bd94a0d2726e",
    "Sound2Sign": "1ab9b9f6-8a9e-440d-946d-2d67fe41409a",
    "Emotion-detection": "299a2d6e-008f-4e92-b973-874a6c6b6ad9",
    "NeuroVera": "68ad8600-becc-445f-b56a-ab0d26d54c58",
}


def load_expansion_dataset() -> List[Dict[str, Any]]:
    path = PROJECT_ROOT / "evaluation" / "e2e" / "final_expansion" / "dataset_100_queries.jsonl"
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def compute_ndcg_at_5(relevance_list: List[int]) -> float:
    """Compute nDCG@5 for binary relevance list of length up to 5."""
    dcg = sum((rel / math.log2(idx + 1)) for idx, rel in enumerate(relevance_list[:5], start=1))
    ideal_relevance = sorted(relevance_list[:5], reverse=True)
    if not ideal_relevance or max(ideal_relevance) == 0:
        # If there were relevant items possible, IDCG=1.0 for at least 1 relevant hit
        ideal_relevance = [1]
    idcg = sum((rel / math.log2(idx + 1)) for idx, rel in enumerate(ideal_relevance[:5], start=1))
    return dcg / idcg if idcg > 0 else 0.0


def evaluate_dataset(
    dataset_name: str,
    query_items: List[Dict[str, Any]],
    orchestrator: SharedRetrievalOrchestrator,
    indexes_cache: Dict[str, Any],
) -> Dict[str, Any]:
    results = []
    isolation_violations = 0
    t_start = time.time()

    total_doc_chunks = 0
    total_code_chunks = 0
    total_arch_chunks = 0

    for item in query_items:
        qid = item.get("query_id") or f"H-{item['repo'][:3].upper()}-{len(results)+1:02d}"
        repo_name = item.get("repository_name") or item.get("repo")
        repo_id = item.get("repository_id") or REPO_ID_MAP.get(repo_name)
        query = item["query"]
        category = item.get("query_category") or item.get("type", "unknown")
        style = item.get("query_style", "direct")
        expected_files = item.get("expected_files", [])

        ans = item.get("answerability")
        if ans is None:
            ans = "fully_answerable" if item.get("supported", True) else "unsupported"
        cov = item.get("index_coverage")
        if cov is None:
            cov = "fully_indexed" if item.get("supported", True) else "zero_expected_target_coverage"
        expected_behaviour = item.get("expected_behaviour")
        if expected_behaviour is None:
            expected_behaviour = "retrieve" if item.get("supported", True) else "abstain"

        # Check index availability
        if repo_name not in indexes_cache:
            v_idx, bm25 = _get_indexes(repo_name)
            indexes_cache[repo_name] = (v_idx, bm25)
        v_idx, bm25 = indexes_cache[repo_name]

        t0_q = time.time()
        with acquire_index_read(repo_name):
            decision: RetrievalDecision = orchestrator.orchestrate(
                query=query,
                index_name=repo_name,
                vector_index=v_idx,
                bm25_retriever=bm25,
                target_repo_id=repo_id,
            )
        q_latency_ms = (time.time() - t0_q) * 1000

        # Verify chunk isolation
        chunk_isolation_ok = True
        for node in decision.nodes:
            if not verify_chunk_isolation(node, repo_id):
                chunk_isolation_ok = False
                isolation_violations += 1

        # Tally chunk types in final context
        doc_count = sum(1 for n in decision.nodes if orchestrator._is_doc_node(n))
        code_count = sum(1 for n in decision.nodes if orchestrator._is_code_node(n))
        arch_count = sum(1 for n in decision.nodes if n.node.metadata.get("path") == "_codebase_context")
        total_doc_chunks += doc_count
        total_code_chunks += code_count
        total_arch_chunks += arch_count

        # Hit ranking check and binary relevance at rank 1..5
        relevance_at_rank = []
        hit_rank = None
        first_hit_file = None

        if ans != "unsupported" and expected_files:
            for rank_idx, node in enumerate(decision.nodes, start=1):
                p = node.node.metadata.get("path")
                is_node_hit = bool(p and any(ef in p or p in ef for ef in expected_files))
                relevance_at_rank.append(1 if is_node_hit else 0)
                if is_node_hit and hit_rank is None:
                    hit_rank = rank_idx
                    first_hit_file = p
        else:
            relevance_at_rank = [0] * len(decision.nodes)

        # Pad relevance list to 5
        while len(relevance_at_rank) < 5:
            relevance_at_rank.append(0)

        hit = hit_rank is not None
        reciprocal_rank = 1.0 / hit_rank if hit_rank is not None else 0.0
        recall_at_1 = 1 if hit_rank == 1 else 0
        recall_at_3 = 1 if (hit_rank is not None and hit_rank <= 3) else 0
        recall_at_5 = 1 if (hit_rank is not None and hit_rank <= 5) else 0
        ndcg_at_5 = compute_ndcg_at_5(relevance_at_rank)

        # False acceptance / False rejection
        is_unsupported_or_zero = (ans == "unsupported") or (cov == "zero_expected_target_coverage")
        is_false_acceptance = is_unsupported_or_zero and (not decision.should_abstain)

        is_fully_supported = (ans == "fully_answerable") and (cov == "fully_indexed")
        is_false_rejection = is_fully_supported and decision.should_abstain
        correct_abstention = is_unsupported_or_zero and decision.should_abstain

        results.append({
            "query_id": qid,
            "repository_name": repo_name,
            "repository_id": repo_id,
            "query": query,
            "category": category,
            "style": style,
            "answerability": ans,
            "index_coverage": cov,
            "expected_behaviour": expected_behaviour,
            "selected_tier": decision.selected_tier.value,
            "confidence_score": decision.confidence_score,
            "should_abstain": decision.should_abstain,
            "retrieved_files": decision.retrieved_files,
            "hit": hit,
            "hit_rank": hit_rank,
            "reciprocal_rank": reciprocal_rank,
            "recall_at_1": recall_at_1,
            "recall_at_3": recall_at_3,
            "recall_at_5": recall_at_5,
            "ndcg_at_5": ndcg_at_5,
            "first_hit_file": first_hit_file,
            "is_false_acceptance": is_false_acceptance,
            "is_false_rejection": is_false_rejection,
            "correct_abstention": correct_abstention,
            "chunk_isolation_ok": chunk_isolation_ok,
            "doc_chunks": doc_count,
            "code_chunks": code_count,
            "arch_chunks": arch_count,
            "latency_ms": q_latency_ms,
        })

    total_queries = len(results)
    latencies = [r["latency_ms"] for r in results]
    avg_latency = sum(latencies) / total_queries if total_queries else 0.0

    # 1. Fully answerable & fully indexed subset
    fully_indexed_subset = [r for r in results if r["answerability"] != "unsupported" and r["index_coverage"] == "fully_indexed"]
    n_fi = len(fully_indexed_subset)
    hit_count = sum(1 for r in fully_indexed_subset if r["hit"])
    hit_rate = (hit_count / n_fi) * 100 if n_fi else 0.0
    rec_1 = (sum(r["recall_at_1"] for r in fully_indexed_subset) / n_fi) * 100 if n_fi else 0.0
    rec_3 = (sum(r["recall_at_3"] for r in fully_indexed_subset) / n_fi) * 100 if n_fi else 0.0
    rec_5 = (sum(r["recall_at_5"] for r in fully_indexed_subset) / n_fi) * 100 if n_fi else 0.0
    mrr = (sum(r["reciprocal_rank"] for r in fully_indexed_subset) / n_fi) if n_fi else 0.0
    ndcg5 = (sum(r["ndcg_at_5"] for r in fully_indexed_subset) / n_fi) if n_fi else 0.0

    frr_count = sum(1 for r in fully_indexed_subset if r["is_false_rejection"])
    frr = (frr_count / n_fi) * 100 if n_fi else 0.0

    # 2. Unsupported subset
    unsupported_subset = [r for r in results if r["answerability"] == "unsupported"]
    n_unsup = len(unsupported_subset)
    far_count = sum(1 for r in unsupported_subset if r["is_false_acceptance"])
    far = (far_count / n_unsup) * 100 if n_unsup else 0.0
    abstention_accuracy = ((n_unsup - far_count) / n_unsup) * 100 if n_unsup else 0.0

    # 3. Partially answerable subset
    partially_indexed_subset = [r for r in results if r["index_coverage"] == "partially_indexed"]
    partially_hits = sum(1 for r in partially_indexed_subset if r["hit"])

    # 4. Zero index coverage subset
    zero_cov_subset = [r for r in results if r["index_coverage"] == "zero_expected_target_coverage" and r["answerability"] != "unsupported"]
    zero_cov_abstained = sum(1 for r in zero_cov_subset if r["should_abstain"])

    # Per-repository breakdown
    repo_breakdown = {}
    for r_name in sorted(list(set(r["repository_name"] for r in results))):
        r_results = [r for r in results if r["repository_name"] == r_name]
        r_fi = [r for r in r_results if r["answerability"] != "unsupported" and r["index_coverage"] == "fully_indexed"]
        r_fi_n = len(r_fi)
        r_hits = sum(1 for r in r_fi if r["hit"])
        r_unsup = [r for r in r_results if r["answerability"] == "unsupported"]
        r_far = sum(1 for r in r_unsup if r["is_false_acceptance"])
        r_mrr = sum(r["reciprocal_rank"] for r in r_fi) / r_fi_n if r_fi_n else 0.0
        r_ndcg = sum(r["ndcg_at_5"] for r in r_fi) / r_fi_n if r_fi_n else 0.0
        r_rec1 = sum(r["recall_at_1"] for r in r_fi) / r_fi_n if r_fi_n else 0.0
        r_rec3 = sum(r["recall_at_3"] for r in r_fi) / r_fi_n if r_fi_n else 0.0
        r_rec5 = sum(r["recall_at_5"] for r in r_fi) / r_fi_n if r_fi_n else 0.0

        repo_breakdown[r_name] = {
            "total_queries": len(r_results),
            "fully_indexed_queries": r_fi_n,
            "hits": r_hits,
            "hit_rate": (r_hits / r_fi_n) * 100 if r_fi_n else 0.0,
            "recall_at_1": r_rec1 * 100,
            "recall_at_3": r_rec3 * 100,
            "recall_at_5": r_rec5 * 100,
            "mrr": r_mrr,
            "ndcg_at_5": r_ndcg,
            "unsupported_queries": len(r_unsup),
            "false_acceptances": r_far,
            "far": (r_far / len(r_unsup)) * 100 if r_unsup else 0.0,
            "false_rejections": sum(1 for r in r_fi if r["is_false_rejection"]),
            "frr": (sum(1 for r in r_fi if r["is_false_rejection"]) / r_fi_n) * 100 if r_fi_n else 0.0,
            "isolation_violations": sum(1 for r in r_results if not r["chunk_isolation_ok"]),
            "avg_latency_ms": sum(r["latency_ms"] for r in r_results) / len(r_results) if r_results else 0.0,
        }

    # Per-category breakdown
    cat_breakdown = {}
    for c_name in sorted(list(set(r["category"] for r in results))):
        c_results = [r for r in results if r["category"] == c_name]
        c_fi = [r for r in c_results if r["answerability"] != "unsupported" and r["index_coverage"] == "fully_indexed"]
        c_fi_n = len(c_fi)
        c_hits = sum(1 for r in c_fi if r["hit"])
        cat_breakdown[c_name] = {
            "total_queries": len(c_results),
            "fully_indexed_queries": c_fi_n,
            "hits": c_hits,
            "hit_rate": (c_hits / c_fi_n) * 100 if c_fi_n else 0.0,
            "mrr": sum(r["reciprocal_rank"] for r in c_fi) / c_fi_n if c_fi_n else 0.0,
            "ndcg_at_5": sum(r["ndcg_at_5"] for r in c_fi) / c_fi_n if c_fi_n else 0.0,
        }

    return {
        "dataset_name": dataset_name,
        "total_queries": total_queries,
        "fully_indexed_count": n_fi,
        "unsupported_count": n_unsup,
        "zero_coverage_answerable_count": len(zero_cov_subset),
        "partially_indexed_count": len(partially_indexed_subset),
        "hit_count": hit_count,
        "hit_rate": hit_rate,
        "recall_at_1": rec_1,
        "recall_at_3": rec_3,
        "recall_at_5": rec_5,
        "mrr": mrr,
        "ndcg_at_5": ndcg5,
        "far_count": far_count,
        "far": far,
        "far_denominator": f"{far_count}/{n_unsup}",
        "frr_count": frr_count,
        "frr": frr,
        "frr_denominator": f"{frr_count}/{n_fi}",
        "abstention_accuracy": abstention_accuracy,
        "partially_indexed_hits": f"{partially_hits}/{len(partially_indexed_subset)}",
        "zero_coverage_abstentions": f"{zero_cov_abstained}/{len(zero_cov_subset)}",
        "evidence_distribution": {
            "doc_chunks": total_doc_chunks,
            "code_chunks": total_code_chunks,
            "arch_chunks": total_arch_chunks,
            "total_context_chunks": total_doc_chunks + total_code_chunks + total_arch_chunks,
            "doc_percentage": (total_doc_chunks / max(1, total_doc_chunks + total_code_chunks + total_arch_chunks)) * 100,
            "code_percentage": (total_code_chunks / max(1, total_doc_chunks + total_code_chunks + total_arch_chunks)) * 100,
        },
        "isolation_violations": isolation_violations,
        "avg_latency_ms": avg_latency,
        "repo_breakdown": repo_breakdown,
        "category_breakdown": cat_breakdown,
        "results": results,
    }


def compute_promotions_and_demotions(baseline_results: List[Dict[str, Any]], final_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    b_map = {r["query_id"]: r for r in baseline_results}
    promoted = []
    demoted = []
    unchanged = []

    for f in final_results:
        qid = f["query_id"]
        b = b_map.get(qid)
        if not b:
            continue
        b_hit = b.get("hit", False)
        f_hit = f.get("hit", False)
        b_rr = b.get("reciprocal_rank", 0.0)
        f_rr = f.get("reciprocal_rank", 0.0)

        if not b_hit and f_hit:
            promoted.append({"query_id": qid, "query": f["query"], "prev_rank": None, "new_rank": f.get("hit_rank"), "reason": "Miss -> Hit"})
        elif b_hit and not f_hit:
            demoted.append({"query_id": qid, "query": f["query"], "prev_rank": b.get("hit_rank"), "new_rank": None, "reason": "Hit -> Miss"})
        elif f_rr > b_rr:
            promoted.append({"query_id": qid, "query": f["query"], "prev_rank": b.get("hit_rank"), "new_rank": f.get("hit_rank"), "reason": f"Rank {b_rr:.2f} -> {f_rr:.2f}"})
        elif f_rr < b_rr:
            demoted.append({"query_id": qid, "query": f["query"], "prev_rank": b.get("hit_rank"), "new_rank": f.get("hit_rank"), "reason": f"Rank {b_rr:.2f} -> {f_rr:.2f}"})
        else:
            unchanged.append(qid)

    return {
        "promoted_count": len(promoted),
        "demoted_count": len(demoted),
        "unchanged_count": len(unchanged),
        "promoted": promoted,
        "demoted": demoted,
    }


def main():
    print("Initializing environment...")
    configure_llamaindex_settings()
    orchestrator = get_retrieval_orchestrator()
    indexes_cache = {}

    # Load baseline results for comparison
    baseline_path = PROJECT_ROOT / "evaluation" / "e2e" / "final_expansion" / "baseline_evaluation_results.json"
    baseline_data = {}
    if os.path.exists(baseline_path):
        with open(baseline_path, "r", encoding="utf-8") as f:
            baseline_data = json.load(f)

    print("\n=======================================================")
    print("RUNNING FINAL EVALUATION: 40-QUERY HOLDOUT DATASET")
    print("=======================================================")
    holdout_res = evaluate_dataset(
        dataset_name="original_40_query_holdout",
        query_items=HOLDOUT_DATASET,
        orchestrator=orchestrator,
        indexes_cache=indexes_cache,
    )

    print("\n=======================================================")
    print("RUNNING FINAL EVALUATION: 100-QUERY EXPANSION DATASET")
    print("=======================================================")
    exp_dataset = load_expansion_dataset()
    expansion_res = evaluate_dataset(
        dataset_name="new_100_query_expansion",
        query_items=exp_dataset,
        orchestrator=orchestrator,
        indexes_cache=indexes_cache,
    )

    # Compute promotions and demotions relative to baseline
    holdout_diff = compute_promotions_and_demotions(
        baseline_data.get("holdout", {}).get("results", []),
        holdout_res["results"],
    )
    expansion_diff = compute_promotions_and_demotions(
        baseline_data.get("expansion", {}).get("results", []),
        expansion_res["results"],
    )

    final_payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "configuration": {
            "dense_top_k": 30,
            "bm25_top_k": 30,
            "rrf_output_cutoff": 20,
            "cross_encoder_depth": 15,
            "top_k_rerank": 5,
        },
        "holdout": holdout_res,
        "holdout_promotions_demotions": holdout_diff,
        "expansion": expansion_res,
        "expansion_promotions_demotions": expansion_diff,
    }

    out_path = PROJECT_ROOT / "evaluation" / "e2e" / "final_expansion" / "final_stabilization_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(final_payload, f, indent=2)

    print(f"\nFinal stabilization evaluation complete! Saved to {out_path}")
    print("\n--- SUMMARY OF RESULTS ---")
    print(f"Holdout:   Recall@1={holdout_res['recall_at_1']:.1f}%, Recall@3={holdout_res['recall_at_3']:.1f}%, Recall@5={holdout_res['recall_at_5']:.1f}%")
    print(f"           MRR={holdout_res['mrr']:.4f}, nDCG@5={holdout_res['ndcg_at_5']:.4f}")
    print(f"           FAR={holdout_res['far']:.2f}% ({holdout_res['far_denominator']}), FRR={holdout_res['frr']:.2f}% ({holdout_res['frr_denominator']})")
    print(f"           Promoted={holdout_diff['promoted_count']}, Demoted={holdout_diff['demoted_count']}")
    print(f"Expansion: Recall@1={expansion_res['recall_at_1']:.1f}%, Recall@3={expansion_res['recall_at_3']:.1f}%, Recall@5={expansion_res['recall_at_5']:.1f}%")
    print(f"           MRR={expansion_res['mrr']:.4f}, nDCG@5={expansion_res['ndcg_at_5']:.4f}")
    print(f"           FAR={expansion_res['far']:.2f}% ({expansion_res['far_denominator']}), FRR={expansion_res['frr']:.2f}% ({expansion_res['frr_denominator']})")
    print(f"           Promoted={expansion_diff['promoted_count']}, Demoted={expansion_diff['demoted_count']}")


if __name__ == "__main__":
    main()
