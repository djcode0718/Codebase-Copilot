"""
tests/unit/test_repository_isolation.py
───────────────────────────────────────
Regression tests for strict repository isolation:
1. Emotion-detection vs Speech-Emotion-Analyzer
2. Sound2Sign vs SenseVoice
3. FedSegX vs NeuroVera
4. Missing repository metadata handling
5. Mismatched repository IDs rejection
6. Orchestrator-level end-to-end isolation enforcement
"""

import pytest
from llama_index.core.schema import TextNode, NodeWithScore

from app.retrieval.repository_isolation import (
    resolve_repository_id,
    resolve_index_name,
    enforce_chunk_isolation,
    verify_chunk_isolation,
    STATIC_REPO_ID_MAP,
)
from app.retrieval.orchestrator import SharedRetrievalOrchestrator, RetrievalTier


# Canonical IDs
ID_EMOTION_DETECTION = "299a2d6e-008f-4e92-b973-874a6c6b6ad9"
ID_SPEECH_EMOTION = "7f25a956-b13d-4098-8a40-5e8731946705"

ID_SOUND2SIGN = "1ab9b9f6-8a9e-440d-946d-2d67fe41409a"
ID_SENSEVOICE = "296ee64c-a989-48ff-9ded-a3e1bb09b63f"

ID_FEDSEGX = "bc5f54ec-7113-4132-b39e-bd94a0d2726e"
ID_NEUROVERA = "68ad8600-becc-445f-b56a-ab0d26d54c58"


def _make_node(text: str, metadata: dict, score: float = 0.8) -> NodeWithScore:
    return NodeWithScore(node=TextNode(text=text, metadata=metadata), score=score)


class TestRepositoryPairIsolation:
    """Test explicit isolation across repository pairs with overlapping terminology."""

    def test_pair_emotion_detection_vs_speech_emotion_analyzer(self):
        """Emotion-detection target must strictly reject Speech-Emotion-Analyzer chunks and queries."""
        # Chunk tagged with Speech-Emotion-Analyzer
        foreign_chunk = _make_node(
            "def extract_mfcc(audio): return librosa.feature.mfcc(audio)",
            {"repository_id": ID_SPEECH_EMOTION, "path": "extract_features.py"},
        )
        native_chunk = _make_node(
            "class EmotionCNN(nn.Module): pass",
            {"repository_id": ID_EMOTION_DETECTION, "path": "src/emotions.py"},
        )

        filtered = enforce_chunk_isolation(
            [foreign_chunk, native_chunk],
            target_repo_id=ID_EMOTION_DETECTION,
            active_index_name="Emotion-detection",
        )
        assert len(filtered) == 1
        assert filtered[0].node.metadata["path"] == "src/emotions.py"
        assert filtered[0].node.metadata["repository_id"] == ID_EMOTION_DETECTION

        # Active index mismatch: Query targeting Emotion-detection sent to Speech-Emotion-Analyzer index
        cross_index_filtered = enforce_chunk_isolation(
            [foreign_chunk],
            target_repo_id=ID_EMOTION_DETECTION,
            active_index_name="Speech-Emotion-Analyzer",
        )
        assert cross_index_filtered == []

    def test_pair_sound2sign_vs_sensevoice(self):
        """Sound2Sign target must strictly reject SenseVoice chunks and queries."""
        foreign_chunk = _make_node(
            "class SenseVoiceSmall(nn.Module): pass",
            {"repository_id": ID_SENSEVOICE, "path": "model.py"},
        )
        native_chunk = _make_node(
            "class WhisperTranscriber: pass",
            {"repository_id": ID_SOUND2SIGN, "path": "code/audio_processor.py"},
        )

        filtered = enforce_chunk_isolation(
            [foreign_chunk, native_chunk],
            target_repo_id=ID_SOUND2SIGN,
            active_index_name="Sound2Sign",
        )
        assert len(filtered) == 1
        assert filtered[0].node.metadata["path"] == "code/audio_processor.py"
        assert filtered[0].node.metadata["repository_id"] == ID_SOUND2SIGN

        # Active index mismatch
        cross_index_filtered = enforce_chunk_isolation(
            [foreign_chunk],
            target_repo_id=ID_SOUND2SIGN,
            active_index_name="SenseVoice",
        )
        assert cross_index_filtered == []

    def test_pair_fedsegx_vs_neurovera(self):
        """FedSegX target must strictly reject NeuroVera chunks and queries."""
        foreign_chunk = _make_node(
            "def run_vision_agent(scan): return gradcam_heatmap(scan)",
            {"repository_id": ID_NEUROVERA, "path": "app/agents/vision.py"},
        )
        native_chunk = _make_node(
            "class CamouflageSegNet(nn.Module): pass",
            {"repository_id": ID_FEDSEGX, "path": "compare/predict_single_image.py"},
        )

        filtered = enforce_chunk_isolation(
            [foreign_chunk, native_chunk],
            target_repo_id=ID_FEDSEGX,
            active_index_name="FedSegX",
        )
        assert len(filtered) == 1
        assert filtered[0].node.metadata["path"] == "compare/predict_single_image.py"
        assert filtered[0].node.metadata["repository_id"] == ID_FEDSEGX

        # Active index mismatch
        cross_index_filtered = enforce_chunk_isolation(
            [foreign_chunk],
            target_repo_id=ID_FEDSEGX,
            active_index_name="NeuroVera",
        )
        assert cross_index_filtered == []


class TestMetadataAndMismatches:
    """Test missing metadata and explicit mismatched IDs."""

    def test_missing_metadata_in_strict_mode(self):
        """In strict require_existing_metadata mode, chunks lacking repository_id are rejected."""
        unlabeled_chunk = _make_node(
            "print('hello world')",
            {"path": "sample.py"},  # No repository_id
        )

        # In strict mode: must reject
        strict_filtered = enforce_chunk_isolation(
            [unlabeled_chunk],
            target_repo_id=ID_FEDSEGX,
            active_index_name="FedSegX",
            require_existing_metadata=True,
        )
        assert len(strict_filtered) == 0

        # In normal mode: chunk from active index is validated and stamped
        normal_filtered = enforce_chunk_isolation(
            [unlabeled_chunk],
            target_repo_id=ID_FEDSEGX,
            active_index_name="FedSegX",
            require_existing_metadata=False,
        )
        assert len(normal_filtered) == 1
        assert normal_filtered[0].node.metadata["repository_id"] == ID_FEDSEGX
        assert normal_filtered[0].node.metadata["index_name"] == "FedSegX"

    def test_mismatched_repository_id_rejected(self):
        """Chunk with foreign repository_id is unconditionally rejected."""
        foreign_chunk = _make_node(
            "data = fetch_records()",
            {"repository_id": "00000000-0000-0000-0000-000000000000", "path": "db.py"},
        )
        filtered = enforce_chunk_isolation(
            [foreign_chunk],
            target_repo_id=ID_FEDSEGX,
            active_index_name="FedSegX",
        )
        assert len(filtered) == 0

    def test_verify_chunk_isolation_helper(self):
        """verify_chunk_isolation returns True only for matching repository_id."""
        node_valid = _make_node("ok", {"repository_id": ID_SOUND2SIGN})
        node_invalid = _make_node("wrong", {"repository_id": ID_SENSEVOICE})
        node_empty = _make_node("empty", {})

        assert verify_chunk_isolation(node_valid, ID_SOUND2SIGN) is True
        assert verify_chunk_isolation(node_invalid, ID_SOUND2SIGN) is False
        assert verify_chunk_isolation(node_empty, ID_SOUND2SIGN) is False


class TestOrchestratorIsolationEnforcement:
    """Test isolation in SharedRetrievalOrchestrator directly."""

    def test_orchestrator_fast_fails_on_index_mismatch(self):
        """Orchestrator immediately abstains if query target_repo_id != active index repo ID."""
        orchestrator = SharedRetrievalOrchestrator()

        decision = orchestrator.orchestrate(
            query="How does facial emotion classification work?",
            index_name="Speech-Emotion-Analyzer",  # Mismatched index
            vector_index=None,
            target_repo_id=ID_EMOTION_DETECTION,  # Targets Emotion-detection
        )

        assert decision.should_abstain is True
        assert decision.selected_tier == RetrievalTier.TIER4_ABSTENTION
        assert len(decision.nodes) == 0
        assert decision.metadata.get("isolation_rejection") is True

    def test_orchestrator_stamps_and_verifies_target_repo(self):
        """Orchestrator stamps matching target_repo_id on all returned chunks."""
        orchestrator = SharedRetrievalOrchestrator()
        node = _make_node("def detect_emotion(): pass", {"path": "src/emotions.py"})

        decision = orchestrator.orchestrate(
            query="Where is detect_emotion defined?",
            index_name="Emotion-detection",
            vector_index=None,
            raw_nodes=[node],
            target_repo_id=ID_EMOTION_DETECTION,
        )

        assert decision.metadata.get("target_repo_id") == ID_EMOTION_DETECTION
        for n in decision.nodes:
            assert n.node.metadata.get("repository_id") == ID_EMOTION_DETECTION
