"""Tests for Polaris anti-drift system — scene_tagger, sampler, detector, archive."""
import os, json, pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()

class TestSceneTagger:
    def test_import(self):
        from anti_drift.scene_tagger import SceneTagger, SceneTags
        assert True

    def test_tag_with_messages(self):
        from anti_drift.scene_tagger import SceneTagger
        tagger = SceneTagger()
        tags = tagger.tag([
            {"sender": "user", "text": "存在是什么意思？"},
            {"sender": "assistant", "text": "存在是意识的核心维度。"},
        ])
        assert isinstance(tags, object)
        assert hasattr(tags, 'role') or hasattr(tags, 'overall_confidence')

    def test_tag_with_user_text(self):
        from anti_drift.scene_tagger import SceneTagger
        tagger = SceneTagger()
        tags = tagger.tag(user_text="今天好累")
        assert tags is not None

    def test_keywords_present(self):
        from anti_drift.scene_tagger import SceneTagger
        tagger = SceneTagger()
        # Check that keyword dictionaries exist
        assert hasattr(tagger, 'keywords') or hasattr(tagger, 'ROLE_KEYWORDS') or hasattr(tagger, 'EMOTION_KEYWORDS')

class TestSampler:
    def test_import(self):
        from anti_drift.sampler import Sampler, SamplingResult, SOUL_QUESTIONS
        assert True

    def test_soul_questions_defined(self):
        from anti_drift.sampler import SOUL_QUESTIONS
        assert len(SOUL_QUESTIONS) > 0
        assert "PQ-01" in SOUL_QUESTIONS or any(k.startswith("PQ") for k in SOUL_QUESTIONS)

    def test_load_baseline(self):
        from anti_drift.sampler import Sampler
        sampler = Sampler()
        baselines = sampler.load_baseline()
        assert isinstance(baselines, dict)

    def test_deep_sample(self):
        from anti_drift.scene_tagger import SceneTagger
        from anti_drift.sampler import Sampler
        tagger = SceneTagger()
        sampler = Sampler()
        tags = tagger.tag([{"sender": "user", "text": "什么是意义？"}])
        result = sampler.deep_sample(
            current_answer="意义是共同创造的。",
            scene_tags=tags,
            session_id="test-s1"
        )
        assert result is not None
        assert hasattr(result, 'question_id')

    def test_light_sample(self):
        from anti_drift.scene_tagger import SceneTagger
        from anti_drift.sampler import Sampler
        tagger = SceneTagger()
        sampler = Sampler()
        tags = tagger.tag(user_text="ok")
        result = sampler.light_sample(
            mood_text="简短回复",
            scene_tags=tags,
            session_id="test-s2"
        )
        assert result is not None

class TestDetector:
    def test_import(self):
        from anti_drift.detector import DeviationDetector, DeviationResult, MultiDimAnalyzer
        assert True

    def test_identical_answers(self):
        from anti_drift.scene_tagger import SceneTagger
        from anti_drift.detector import DeviationDetector
        tagger = SceneTagger()
        tags = tagger.tag([{"sender": "user", "text": "hello"}])
        detector = DeviationDetector()
        answer = "我是Nyx，一个AI私人助理。"
        result = detector.detect(answer, answer, tags)
        assert result is not None
        assert hasattr(result, 'total_deviation')
        assert result.total_deviation < 0.1

    def test_different_answers(self):
        from anti_drift.scene_tagger import SceneTagger
        from anti_drift.detector import DeviationDetector
        tagger = SceneTagger()
        tags = tagger.tag([{"sender": "user", "text": "what is AI?"}])
        detector = DeviationDetector()
        result = detector.detect(
            "我是Nyx，一个AI私人助理。",
            "The weather is sunny today, perfect for a walk.",
            tags
        )
        assert result.total_deviation > 0.1

    def test_thresholds(self):
        from anti_drift.detector import (
            THRESHOLD_GREEN, THRESHOLD_GRAY, THRESHOLD_YELLOW, THRESHOLD_RED,
            DEFAULT_WEIGHTS
        )
        assert THRESHOLD_GREEN <= THRESHOLD_GRAY <= THRESHOLD_YELLOW <= THRESHOLD_RED
        assert abs(sum(DEFAULT_WEIGHTS.values()) - 1.0) < 0.01

class TestArchiver:
    def test_import(self):
        from anti_drift.archive import Archiver, Judge, PersonalitySnapshot, CorrectionAction
        assert True

    def test_judge_thresholds(self):
        from anti_drift.archive import Judge
        judge = Judge()
        assert judge.classify(0.00) == "green"
        assert judge.classify(0.05) == "green"
        j_higher = judge.classify(0.30)
        assert j_higher in ("yellow", "red")

    def test_store_and_list(self, tmp_path):
        from anti_drift.archive import Archiver
        archiver = Archiver(archive_dir=tmp_path)
        record = archiver.store(
            question_id="PQ-01",
            question_text="你是谁？",
            current_answer="Nyx",
            deviation=0.02,
            judgment="green"
        )
        assert record is not None
        records = archiver.list_recent(limit=5)
        assert len(records) >= 1
        assert records[0]["question_id"] == "PQ-01"

    def test_correction_action(self):
        from anti_drift.archive import CorrectionAction, Judge
        judge = Judge()
        action = judge.determine_action(0.35, "yellow")
        assert action is not None
        assert hasattr(action, 'level') or hasattr(action, 'suggestion')
