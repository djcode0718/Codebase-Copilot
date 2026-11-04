# Repository Isolation Test Specification — Final Evaluation Expansion

**Target Directory**: `evaluation/e2e/final_expansion/`  
**Document**: `REPOSITORY_ISOLATION_SPEC.md`  
**Purpose**: Define strict cross-repository boundary verification, cross-talk failure modes, and collision test cases across `FedSegX`, `Sound2Sign`, `Emotion-detection`, and `NeuroVera`.

---

## 1. Architectural Isolation Invariants

In a multi-tenant or multi-repository Codebase-Copilot deployment, each retrieval request targets a specific repository identified by `repository_id` and indexed under an isolated directory (`data/index/{repo_name}`).

### Strict Boundary Rules:
1. **Target Confinement**: All retrieved `NodeWithScore` objects must have their `node.metadata["path"]` verified against the target repository's index.
2. **Zero Cross-Contamination**: A query targeting Repository A must never return chunks belonging to Repository B, even if Repository B contains an identical filename (e.g. `README.md`, `requirements.txt`), overlapping function names (e.g. `plot_model_history`, `cosine_similarity`), or identical domain terms (e.g. "emotion recognition", "audio transcription", "vision model").
3. **Identifier Grounding**: Identifier lookups (e.g., relationship queries or code searches) must strictly resolve against `relationship_graph.json` of the target repository ID.

---

## 2. Identified Cross-Repository Terminology & Symbol Overlaps

The four evaluation repositories exhibit significant lexical, conceptual, and functional overlap that poses acute risks of cross-repository contamination:

### Overlap Category 1: `Emotion-detection` vs. `Speech-Emotion-Analyzer` (Legacy)
- **Domain Overlap**: Both repositories perform emotion classification into categorical classes (e.g., `angry`, `disgusted`, `fearful`, `happy`, `sad`, `surprised`, `neutral`).
- **Shared Lexicon**: "emotion detection", "classification accuracy", "confusion matrix", "Keras Sequential model", "CNN layers".
- **Collision Risk**: A query to `Emotion-detection` asking *"What facial emotions are classified?"* could mistakenly retrieve audio emotion chunks from `Speech-Emotion-Analyzer` if repository filtering fails.
- **Differentiating Ground Truth**:
  - `Emotion-detection`: Facial vision CNN trained on FER-2013 grayscale 48x48 images (`src/emotions.py`).
  - `Speech-Emotion-Analyzer`: Audio speech MFCC 1D-CNN trained on RAVDESS `.wav` speech audio (`final_results_gender_test.ipynb`).

### Overlap Category 2: `Sound2Sign` vs. `SenseVoice` (Legacy)
- **Domain Overlap**: Both repositories ingest speech/audio and perform automated speech recognition (ASR).
- **Shared Lexicon**: "Whisper", "audio transcription", "speech-to-text", "sampling rate", "microphone input".
- **Collision Risk**: A query to `Sound2Sign` asking *"How does Whisper transcribe audio input?"* could retrieve `SenseVoice` FunASR/VAD audio chunks.
- **Differentiating Ground Truth**:
  - `Sound2Sign`: `WhisperTranscriber` in `code/audio_processor.py` (Faster-Whisper) converting speech to gloss sequences for sign animation.
  - `SenseVoice`: FunASR multilingual speech recognition model (`model.py`, `api.py`).

### Overlap Category 3: `NeuroVera` vs. `FedSegX` vs. `MediscanAI`
- **Domain Overlap**: Deep learning applied to medical imaging (brain MRI scans, endoscopic polyps, clinical triage).
- **Shared Lexicon**: "medical imaging", "segmentation mask", "Grad-CAM heatmap", "triage", "cross-domain validation", "data augmentation".
- **Collision Risk**: A query to `NeuroVera` regarding Grad-CAM heatmaps could collide with `FedSegX` feature visualization or `MediscanAI` clinical pipelines.
- **Differentiating Ground Truth**:
  - `NeuroVera`: LangGraph 5-agent architecture (`app/graph/graph.py`), VGG16 Grad-CAM (`app/utils/gradcam.py`), Case Bank cosine similarity.
  - `FedSegX`: Federated Learning (PVTv2-B2 `CamouflageSegNet`, FedAvg, FedProx) for polyp segmentation (`train/fed_train_aug.py`).

---

## 3. Explicit Isolation Test Scenarios

The 100-query expansion dataset includes 8 targeted isolation collision test pairs:

| Test ID | Primary Target Repo | Target Query | Potential Colliding Repo | Colliding Evidence / Concept | Strict Isolation Requirement |
|---|---|---|---|---|---|
| **ISO-01** | `Emotion-detection` (`299a2d6e`) | *"How is the convolutional neural network structured for emotion classification?"* | `Speech-Emotion-Analyzer` | `final_results_gender_test.ipynb` (1D-CNN) | Must return `src/emotions.py` (2D-CNN with Conv2D, MaxPooling2D). Chunks from `Speech-Emotion-Analyzer` strictly forbidden. |
| **ISO-02** | `Sound2Sign` (`UNINDEXED`) | *"Where is the Whisper audio transcription implemented?"* | `SenseVoice` | `demo1.py`, `webui.py`, FunASR | Must NOT retrieve `SenseVoice` ASR code. Must abstain due to target repo index absence. |
| **ISO-03** | `FedSegX` (`bc5f54ec`) | *"What data augmentations are applied to medical images?"* | `Speech-Emotion-Analyzer` / `SenseVoice` | Audio noise / pitch augmentations | Must return `train/augment_kvasir.py` (Kvasir endoscopic images: `_hflip`, `_rotate`, `_colour`). |
| **ISO-04** | `NeuroVera` (`68ad8600`) | *"How is Grad-CAM computed to explain vision model predictions?"* | `FedSegX` | FPN decoder edge heads | Must return `app/utils/gradcam.py` (VGG16 brain MRI Grad-CAM). Must not match FedSegX contour heads. |
| **ISO-05** | `Emotion-detection` (`299a2d6e`) | *"What dataset was used for training the emotion model?"* | `Speech-Emotion-Analyzer` | RAVDESS audio dataset | Must return `README.md` (FER-2013, 35,887 grayscale 48x48 faces). Must not cite RAVDESS. |
| **ISO-06** | `Sound2Sign` (`UNINDEXED`) | *"How are gloss sequences generated from input sentences?"* | `SenseVoice` | Chinese/English ASR tokens | Must NOT retrieve SenseVoice tokenizer. Must abstain. |
| **ISO-07** | `NeuroVera` (`68ad8600`) | *"What cosine similarity threshold is used for historical case retrieval?"* | `Codebase-Copilot` | RAG embedding cosine search | Must return `app/agents/retrieval.py` (Case Bank top-3 historical cases). |
| **ISO-08** | `FedSegX` (`bc5f54ec`) | *"How does the federated aggregator combine client model weights?"* | `Codebase-Copilot` | RRF fusion aggregation | Must return `train/fed_train_aug.py` / `README.md` (`FedAvg` / `FedProx` parameter weighting). |

---

## 4. Evaluation Harness Isolation Enforcement

To enforce repository isolation during automated evaluation:
1. **Target Parameter Enforced**: The orchestrator call must pass `index_name=record["repository_name"]` and load exclusively `indexes[record["repository_name"]]`.
2. **Chunk Origin Verification**:
   ```python
   for node in decision.nodes:
       node_path = node.node.metadata.get("path")
       # Verify file exists strictly within target repository root
       assert os.path.exists(os.path.join(get_repos_dir(), record["repository_name"], node_path)) or node_path == "_codebase_context"
   ```
3. **Failure Classification**: If any returned chunk originates from a path outside `data/repos/{target_repo}/`, the query is flagged as an **Isolation Violation (Critical Failure)**.
