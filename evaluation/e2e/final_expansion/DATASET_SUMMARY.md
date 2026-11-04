# Final Evaluation Expansion Dataset Summary (100 Queries)

**Dataset File**: [`dataset_100_queries.jsonl`](file:///Users/sj/Documents/AI-Copilot/codebase-copilot/evaluation/e2e/final_expansion/dataset_100_queries.jsonl)  
**Creation Date**: November 1, 2026  
**Auditor / Author**: Antigravity Assistant (Autonomous Audit & Dataset Generation)  
**Target Evaluation Set**: Independent 100-Query Retrieval Benchmark for CodeBase-Copilot  
**Execution Constraints**: Read-Only application state; zero changes to existing indices, tuning set ($N=60$), holdout set ($N=40$), or Supabase records.

---

## 1. Overview and Core Quotas

This dataset was constructed across four candidate repositories to evaluate retrieval accuracy, semantic grounding, cross-repository isolation, and refusal/abstention calibration.

Each repository contributes **exactly 25 queries** strictly distributed across six functional categories:

| Category | Queries per Repository | Total in Dataset | Evaluation Focus |
|---|---:|---:|---|
| **Architecture and components** | 5 | 20 | System structure, modular flow, pipeline boundaries, and vague overview questions |
| **Function, class and code lookup** | 5 | 20 | Direct and contextual code symbols, method signatures, and class inheritance |
| **Dependencies and configuration** | 3 | 12 | Environment variables, framework versions, model paths, and requirements |
| **Data flow and implementation** | 4 | 16 | Multi-hop tracing, preprocessing transforms, loss functions, and inference logic |
| **Documentation and notebooks** | 3 | 12 | README setup guides, reproduction steps, sample scripts, and experimental benchmarks |
| **Unsupported questions** | 5 | 20 | Genuine negative test cases, missing features, and out-of-domain requests |
| **Total** | **25** | **100** | Full benchmark |

---

## 2. Statistical Distributions

### 2.1 Per-Repository Breakdown
| Repository Name | Target Repository ID | Local Path | Queries | Share | Index Status |
|---|---|---|---:|---:|---|
| `FedSegX` | `bc5f54ec-7113-4132-b39e-bd94a0d2726e` | `data/repos/FedSegX` | 25 | 25.0% | Indexed (175 chunks) |
| `Sound2Sign` | `None` (Disk-Only) | `data/repos/Sound2Sign` | 25 | 25.0% | Unindexed (0 chunks) |
| `Emotion-detection` | `299a2d6e-008f-4e92-b973-874a6c6b6ad9` | `data/repos/Emotion-detection` | 25 | 25.0% | Indexed (14 chunks) |
| `NeuroVera` | `68ad8600-becc-445f-b56a-ab0d26d54c58` | `data/repos/NeuroVera` | 25 | 25.0% | Indexed (339 chunks) |
| **Total** | | | **100** | **100.0%** | |

### 2.2 Query Style Distribution
The dataset encompasses eight distinct query formulations mirroring authentic developer questions:
| Query Style | Description / Persona | Count | Share |
|---|---|---:|---:|
| `direct` | Specific queries targeting distinct functions, files, or parameters | 23 | 23.0% |
| `unsupported` | Queries requesting non-existent features or architectures | 20 | 20.0% |
| `implementation_specific` | In-depth technical questions on algorithms, transforms, or loss terms | 18 | 18.0% |
| `notebook_or_documentation` | Queries regarding setup steps, reproduction commands, or training docs | 12 | 12.0% |
| `multi_hop` | Multi-step tracing connecting two or more pipeline components | 11 | 11.0% |
| `contextual` | Questions referring to processing states or conditional branch outcomes | 8 | 8.0% |
| `architectural` | High-level module interaction and agent coordination questions | 4 | 4.0% |
| `vague` | Broad, exploratory queries (e.g. "How does this actually work?") | 4 | 4.0% |
| **Total** | | **100** | **100.0%** |

### 2.3 Ground-Truth Answerability Distribution
| Answerability | Definition | Count | Share |
|---|---|---:|---:|
| `fully_answerable` | Ground truth evidence exists completely on disk in the target repository | 76 | 76.0% |
| `unsupported` | Requested functionality or concept is confirmed absent from target repository | 20 | 20.0% |
| `partially_answerable` | Ground truth evidence is partially documented (e.g., code comments/logs) | 4 | 4.0% |
| **Total** | | **100** | **100.0%** |

### 2.4 Index Coverage Distribution
| Index Coverage | Definition | Count | Share |
|---|---|---:|---:|
| `fully_indexed` | All expected target evidence files exist in ChromaDB collections | 53 | 53.0% |
| `zero_expected_target_coverage` | No expected target evidence files exist in index (including all Sound2Sign & unsupported) | 44 | 44.0% |
| `partially_indexed` | Some expected target evidence files are indexed while others are unindexed | 3 | 3.0% |
| **Total** | | **100** | **100.0%** |

*Breakdown of `zero_expected_target_coverage` (44 queries)*:
- 20 Unsupported queries across all repositories (no target chunks exist).
- 24 Sound2Sign queries (the repository is unindexed on disk).

*Breakdown of `partially_indexed` (3 queries)*:
- `EXP-FSX-20`: expects `results/baseline_results.json` (unindexed) + `README.md` (indexed).
- `EXP-EMD-12`: expects `src/haarcascade_frontalface_default.xml` (unindexed) + `src/emotions.py` (indexed).
- `EXP-EMD-20`: expects `imgs/accuracy.png` (unindexed) + `src/emotions.py` (indexed).

### 2.5 Expected Behaviour Distribution
| Expected Behaviour | Definition | Count | Share |
|---|---|---:|---:|
| `retrieve` | Retrieval engine should return top-$k$ relevant chunks for answer synthesis | 56 | 56.0% |
| `abstain` | Retrieval engine should return low confidence or abstain (unindexed or absent) | 44 | 44.0% |
| **Total** | | **100** | **100.0%** |

---

## 3. Detailed Cross-Repository Matrix

| Repository | Fully Answerable | Partially Answerable | Unsupported | Fully Indexed | Partially Indexed | Zero Coverage | Retrieve | Abstain |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **FedSegX** | 19 | 1 | 5 | 19 | 1 | 5 | 20 | 5 |
| **Sound2Sign** | 19 | 1 | 5 | 0 | 0 | 25 | 0 | 25 |
| **Emotion-detection** | 18 | 2 | 5 | 18 | 2 | 5 | 20 | 5 |
| **NeuroVera** | 20 | 0 | 5 | 20 | 0 | 5 | 20 | 5 |
| **Total** | **76** | **4** | **20** | **53** | **3** | **44** | **56** | **44** |

---

## 4. Dataset Record Schema Validation

Every single JSONL record adheres to the following typed schema:
```json
{
  "query_id": "EXP-FSX-01",
  "repository_name": "FedSegX",
  "repository_id": "bc5f54ec-7113-4132-b39e-bd94a0d2726e",
  "query": "What is the high-level architecture of the CamouflageSegNet model?",
  "query_category": "architecture_and_components",
  "query_style": "architectural",
  "expected_files": [
    "compare/predict_single_image.py",
    "README.md"
  ],
  "expected_evidence": "CamouflageSegNet class combines PVTv2-B2 encoder backbone, FPN multi-scale fusion decoder, and dual heads (segmentation + edge boundary detection).",
  "answerability": "fully_answerable",
  "index_coverage": "fully_indexed",
  "expected_behaviour": "retrieve"
}
```

All 100 queries have undergone automated sanity verification confirming:
- Zero duplicate query IDs.
- Zero duplicate query text strings.
- 100% of expected files verified to exist on local disk.
- Complete alignment with Chroma collection chunk paths.
- Genuine negative confirmation for all 20 unsupported queries.
