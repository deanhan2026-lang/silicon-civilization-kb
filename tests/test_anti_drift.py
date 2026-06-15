"""Tests for Polaris anti-drift system — scene_tagger, sampler, detector, archive."""
import os, json, pytest
from pathlib import Path
from dataclasses import dataclass

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
        from anti_drift.scene_tagger import EMOTION_KEYWORDS, ROLE_KEYWORDS
        # Check that keyword dictionaries exist at module level
        assert len(EMOTION_KEYWORDS) > 0
        assert len(ROLE_KEYWORDS) > 0


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
        assert hasattr(result, 'composite_score')
        assert result.composite_score < 0.1

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
        assert result.composite_score > 0.1

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
        from anti_drift.detector import DeviationResult
        judge = Judge()
        # 构造DeviationResult实例来测试
        result_green = DeviationResult(
            judgment='green', composite_score=0.0, normalized_score=0.0,
            dimension_scores={}, scene_tags={}, scene_weight=1.0
        )
        result_yellow = DeviationResult(
            judgment='yellow', composite_score=0.35, normalized_score=0.35,
            dimension_scores={}, scene_tags={}, scene_weight=1.0
        )
        judgment_g, _ = judge.judge(result_green)
        judgment_y, _ = judge.judge(result_yellow)
        assert judgment_g == "green"
        assert judgment_y in ("yellow", "red")

    def test_store_and_list(self, tmp_path):
        from anti_drift.archive import Archiver, Judge, DeviationResult
        archiver = Archiver(archive_dir=str(tmp_path))
        judge = Judge()
        # 创建DeviationResult
        result = DeviationResult(
            judgment='green', composite_score=0.0, normalized_score=0.0,
            dimension_scores={}, scene_tags={'role': 'assistant'}, scene_weight=1.0
        )
        judgment, correction = judge.judge(result)
        # 使用archive方法（不是store）
        snapshot = archiver.archive(judgment, correction, result, question_id="test_q")
        assert snapshot is not None
        assert snapshot.sha256 is not None
        # 加载历史
        history = archiver.load_history(limit=10)
        assert len(history) >= 1

    def test_correction_action(self):
        from anti_drift.archive import CorrectionAction, Judge, DeviationResult
        judge = Judge()
        # 构造DeviationResult（黄色判定）
        result = DeviationResult(
            judgment='yellow', composite_score=0.35, normalized_score=0.35,
            dimension_scores={}, scene_tags={}, scene_weight=1.0
        )
        judgment, action = judge.judge(result)
        assert action is not None
        assert hasattr(action, 'level') or hasattr(action, 'suggestion')
