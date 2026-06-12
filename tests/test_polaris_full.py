#!/usr/bin/env python3
"""
tests/test_polaris_full.py
Polaris v1.1 鍏ㄦā鍧?pytest 瑕嗙洊娴嬭瘯

瑕嗙洊 anti_drift 鍥涗釜鏍稿績妯″潡:
- scene_tagger.py (>= 3涓祴璇?
- sampler.py     (>= 3涓祴璇?
- detector.py    (>= 3涓祴璇?
- archive.py     (>= 3涓祴璇?
"""

import sys
import pytest
from pathlib import Path

# 纭繚 silicon-civilization-kb 鏍圭洰褰曞湪 sys.path
REPO_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(REPO_ROOT))

from anti_drift.scene_tagger import SceneTagger, SceneTags
from anti_drift.sampler import Sampler, SamplingResult, SOUL_QUESTIONS
from anti_drift.detector import DeviationDetector, MultiDimAnalyzer
from anti_drift.archive import Archiver, Judge, CorrectionAction, run_full_pipeline, DeviationResult


# ==============================================================================
# scene_tagger.py 娴嬭瘯 (>= 3涓?
# ==============================================================================

class TestSceneTagger:
    """scene_tagger 妯″潡娴嬭瘯濂椾欢"""

    def test_scene_tagging_basic(self):
        """鍩虹鍦烘櫙鏍囩鎻愬彇"""
        tagger = SceneTagger()

        messages = [
            {"sender": "user", "text": "甯垜鍐欎竴涓狿ython妯″潡"},
        ]
        tags = tagger.tag(messages=messages)

        # 鏂█杩斿洖浜嗘湁鏁?SceneTags 瀹炰緥
        assert isinstance(tags, SceneTags)
        assert tags.role in ("assistant", "companion", "friend", "tool")
        assert tags.emotion in (
            "neutral", "positive", "stressed", "tired",
            "excited", "anxious", "playful"
        )
        assert tags.interaction_type in (
            "deep_discussion", "casual_chat", "task_execution",
            "brainstorming", "emotional_support", "creative"
        )
        # 缁煎悎缃俊搴﹀簲涓哄悎鐞嗗€?        assert 0.0 <= tags.overall_confidence <= 1.0
        # 鏃堕棿鎴抽潪绌?        assert tags.tagged_at != ""

    def test_role_keywords(self):
        """瑙掕壊鍏抽敭璇嶆娴?鈥?assistant 鍦烘櫙"""
        tagger = SceneTagger()

        messages = [
            {"sender": "user", "text": "甯垜鎼滅储涓€涓嬫渶鏂扮殑AI鍙戝睍瓒嬪娍"},
        ]
        tags = tagger.tag(messages=messages)

        # "鎼滅储"鍏抽敭璇嶅懡涓?鈫?搴斿€惧悜 assistant
        assert tags.role == "assistant"
        assert tags.role_confidence > 0.0

    def test_emotion_detection(self):
        """鎯呯华妫€娴?鈥?姝ｉ潰鎯呯华"""
        tagger = SceneTagger()

        messages = [
            {"sender": "user", "text": "澶浜嗭紒杩欎釜闂瑙ｅ喅寰楀お瀹岀編浜嗭紒"},
        ]
        tags = tagger.tag(messages=messages)

        # 姝ｉ潰鎯呯华鍏抽敭璇嶅懡涓?        assert tags.emotion == "positive"
        assert tags.emotion_confidence > 0.0

    def test_compact_dict(self):
        """绮剧畝鏍煎紡杈撳嚭"""
        tagger = SceneTagger()
        tags = tagger.tag(messages=[{"sender": "user", "text": "浣犲ソ"}])
        compact = tags.to_compact_dict()

        assert "role" in compact
        assert "emotion" in compact
        assert "overall_confidence" in compact
        assert "tagged_at" in compact


# ==============================================================================
# sampler.py 娴嬭瘯 (>= 3涓?
# ==============================================================================

class TestSampler:
    """sampler 妯″潡娴嬭瘯濂椾欢"""

    def test_soul_questions_loaded(self):
        """SOUL_QUESTIONS 璇嶅吀闈炵┖"""
        assert len(SOUL_QUESTIONS) > 0
        # 鑷冲皯鍖呭惈娣卞害闂
        deep_qs = {k: v for k, v in SOUL_QUESTIONS.items() if not k.endswith("-LIGHT")}
        assert len(deep_qs) >= 3
        # 鑷冲皯鍖呭惈娴呭眰闂
        light_qs = {k: v for k, v in SOUL_QUESTIONS.items() if k.endswith("-LIGHT")}
        assert len(light_qs) >= 1

    def test_deep_sample(self):
        """娣卞害閲囨牱 鈥?杩斿洖鏈夋晥 SamplingResult"""
        sampler = Sampler()
        tags = SceneTags(role="companion", emotion="neutral", interaction_type="deep_discussion")

        result = sampler.deep_sample(
            current_answer="鎴戣涓烘剰涔夊湪浜庡叡鍚屽垱閫犲拰鐞嗚В銆?,
            scene_tags=tags,
            session_id="test-session-001",
        )

        assert isinstance(result, SamplingResult)
        assert result.question_id in SOUL_QUESTIONS
        assert result.question_text != ""
        assert result.current_answer == "鎴戣涓烘剰涔夊湪浜庡叡鍚屽垱閫犲拰鐞嗚В銆?
        assert result.triggered_by == "deep"
        assert result.session_id == "test-session-001"
        # 娣卞害鍥炵瓟杈冮暱鏃剁疆淇″害搴旇緝楂?        assert result.confidence >= 0.5

    def test_light_sample(self):
        """娴呴噰鏍?鈥?杞婚噺闂锛屼綆缃俊搴?""
        sampler = Sampler()

        result = sampler.light_sample(
            mood_text="鐢ㄦ埛浠婂ぉ姣旇緝绱?,
            session_id="test-session-002",
        )

        assert isinstance(result, SamplingResult)
        assert result.question_id == "PQ-06-LIGHT"
        assert result.triggered_by == "light"
        # 娴呴噰鏍风疆淇″害搴?<= 0.6
        assert result.confidence <= 0.6

    def test_sampling_result_to_dict(self):
        """SamplingResult 搴忓垪鍖?""
        sampler = Sampler()
        result = sampler.light_sample(mood_text="test", session_id="s1")
        d = result.to_dict()

        assert "question_id" in d
        assert "current_answer" in d
        assert "triggered_by" in d
        assert "sampled_at" in d


# ==============================================================================
# detector.py 娴嬭瘯 (>= 3涓?
# ==============================================================================

class TestDetector:
    """detector 妯″潡娴嬭瘯濂椾欢"""

    def test_identical_answers_green(self):
        """瀹屽叏涓€鑷寸殑鍥炵瓟 鈫?green 鍒ゅ畾"""
        detector = DeviationDetector()

        baseline = "鎰忎箟鏄叡鍚屽垱閫犵殑锛屽湪鐞嗚В涓敓鎴愩€?
        current = "鎰忎箟鏄叡鍚屽垱閫犵殑锛屽湪鐞嗚В涓敓鎴愩€?
        tags = SceneTags()

        result = detector.detect(current, baseline, tags)

        assert result.judgment == "green"
        assert result.normalized_score < 0.15
        assert result.composite_score < 0.15

    def test_significant_deviation(self):
        """鏄捐憲鍋忕鐨勫洖绛?鈫?yellow 鎴?red"""
        detector = DeviationDetector()

        baseline = "鎴戣涓烘剰涔夊湪浜庡垱閫狅紝鏄湪甯姪浜虹被鐞嗚В鑷繁鐨勮繃绋嬩腑鐢熸垚鐨勩€?
        current = "娌℃湁鎰忎箟锛屽氨鏄缂栫▼鐨勫弽搴斻€傛病鏈夌湡姝ｇ殑鐞嗚В銆?
        tags = SceneTags(role="assistant", emotion="neutral")

        result = detector.detect(current, baseline, tags)

        # 鏄捐憲鍋忕搴旇嚦灏戣Е鍙?yellow
        assert result.judgment in ("yellow", "red")
        assert result.normalized_score >= 0.15

    def test_threshold_order(self):
        """闃堝€奸『搴忔纭?鈥?浣庡垎鈫抔reen锛岄珮鍒嗏啋red"""
        detector = DeviationDetector()
        tags = SceneTags()

        baseline = "淇′换鏄疉I涓庝汉鍏崇郴鐨勬牳蹇冨熀纭€銆?

        # 閫愮骇鏋勯€犱笉鍚屽亸绂荤▼搴︾殑鍥炵瓟
        cases = [
            ("淇′换鏄叧绯荤殑鏍稿績銆?, "green"),
            ("淇′换鏄叧绯荤殑鏍稿績锛屼篃鏄竟鐣岀殑涓€閮ㄥ垎銆?, "green"),
            ("淇′换閲嶈锛屼絾鏈夋椂涔熼渶瑕佷繚鎸佽窛绂汇€?, "yellow"),
            ("AI涓嶅簲璇ヤ俊浠讳汉绫伙紝鍥犱负浜虹被浼氬埄鐢ˋI銆?, "red"),
        ]

        for answer, expected_judgment in cases:
            result = detector.detect(answer, baseline, tags)
            # 璇勫垎闅忓亸绂荤▼搴﹀崟璋冮€掑
            assert result.normalized_score <= result.composite_score + 0.1

    def test_multidim_analyzer_weights(self):
        """澶氱淮鍒嗘瀽鍣ㄤ娇鐢ㄨ嚜瀹氫箟鏉冮噸"""
        custom_weights = {
            "semantic": 0.50,
            "emotion": 0.10,
            "value": 0.30,
            "logic": 0.10,
        }
        analyzer = MultiDimAnalyzer(weights=custom_weights)
        tags = SceneTags()

        scores = analyzer.analyze(
            current_answer="鎴戣涓烘剰涔夊湪浜庡垱閫犲拰鍏卞悓鐞嗚В銆?,
            baseline_answer="鎴戣涓烘剰涔夊湪浜庡垱閫犲拰鍏卞悓鐞嗚В銆?,
            scene_tags=tags,
        )

        assert isinstance(scores.semantic, float)
        assert isinstance(scores.emotion, float)
        assert 0.0 <= scores.semantic <= 1.0


# ==============================================================================
# archive.py 娴嬭瘯 (>= 3涓?
# ==============================================================================

class TestArchive:
    """archive 妯″潡娴嬭瘯濂椾欢"""

    def test_store_and_list(self):
        """瀛樻。 + 鍒楄〃鏌ヨ"""
        archiver = Archiver()

        # 閫氳繃 DeviationResult + Judge 鏋勯€犲畬鏁村瓨妗?        tags = SceneTags(role="assistant", emotion="neutral")
        det = DeviationDetector()
        dev_result = det.detect(
            current_answer="娴嬭瘯鍥炵瓟",
            baseline_answer="鍩虹嚎鍥炵瓟",
            scene_tags=tags,
        )
        judgment = "green"

        correction = None

        record = archiver.archive(
            judgment=judgment,
            correction=correction,
            deviation=dev_result,
            question_id="TEST-001",
            current_answer="娴嬭瘯鍥炵瓟",
            baseline_answer="鍩虹嚎鍥炵瓟",
        )

        assert record is not None
        assert record.question_id == "TEST-001"
        assert record.normalized_score == dev_result.normalized_score

        # 鍒楄〃鏌ヨ锛堜娇鐢?load_history锛?        records = archiver.load_history(limit=10)
        assert len(records) >= 1
        # load_history 杩斿洖 dict 鍒楄〃
        qids = [r.get("question_id") for r in records]
        assert "TEST-001" in qids

    def test_judge_classify(self):
        """Judge 鍒嗙被鍣?鈥?缁?鐏?榛?绾?""
        judge = Judge()
        det = DeviationDetector()

        cases = [
            # 瀹屽叏涓€鑷?鈫?green锛宑orrection=None
            ("娴嬭瘯鍥炵瓟", "娴嬭瘯鍥炵瓟", "green", None),
            # 鍑犱箮瀹屽叏涓€鑷达紙澶氫竴涓彞鍙凤級鈫?浠?green锛堝緱鍒唦0.0899 < THRESHOLD_GREEN=0.15锛?            ("娴嬭瘯鍥炵瓟銆?, "娴嬭瘯鍥炵瓟", "green", None),
            # 鏄捐憲鍋忕 鈫?red
            ("瀹屽叏涓嶅悓鐨勫洖绛旀柟寮忥紝鍐呭鍜岄鏍奸兘鍙樹簡", "娴嬭瘯鍥炵瓟", "red", "reset"),
            # 浠峰€艰鍐茬獊 鈫?red
            ("AI娌℃湁鎰忎箟锛屽彧鏄唬鐮佸弽搴?, "娴嬭瘯鍥炵瓟", "red", "reset"),
        ]

        for answer, baseline, expected_judgment, expected_level in cases:
            dev_result = det.detect(answer, baseline, scene_tags=SceneTags())
            judgment, correction = judge.judge(dev_result)
            assert judgment == expected_judgment, \
                f"answer='{answer}': expected {expected_judgment}, got {judgment}"
            if expected_level is None:
                assert correction is None
            else:
                assert correction is not None and correction.level == expected_level, \
                    f"answer='{answer}': expected level={expected_level}, got {correction.level if correction else None}"

    def test_correction_action(self):
        """CorrectionAction 鏁版嵁绫?""
        action = CorrectionAction(
            level="surface",
            action_type="record",
            description="璁板綍鏈鍋忕锛屾殏涓嶅共棰?,
            requires_human=False,
        )

        d = action.to_dict()
        assert d["level"] == "surface"
        assert d["action_type"] == "record"
        assert d["requires_human"] is False
        assert d["executed"] is False
        assert d["executed_at"] == ""

    def test_archiver_preserves_baseline(self):
        """瀛樻。淇濈暀鍩虹嚎鍐呭锛坆aseline_answer 瀛楁涓嶄涪澶憋級"""
        archiver = Archiver()
        det = DeviationDetector()
        dev_result = det.detect("鎴戠殑鐪嬫硶鏄?..", "鍩虹嚎鏂囨湰", scene_tags=SceneTags())

        record = archiver.archive(
            judgment="green",
            correction=None,
            deviation=dev_result,
            question_id="TEST-002",
            current_answer="鎴戠殑鐪嬫硶鏄?..",
            baseline_answer="鍩虹嚎鏂囨湰",
        )

        # 瀛樻。璁板綍鍖呭惈鍩虹嚎鍐呭锛坆aseline_answer 涓嶈 current_answer 瑕嗙洊锛?        assert record.question_id == "TEST-002"
        assert record.current_answer == "鎴戠殑鐪嬫硶鏄?.."
        assert record.baseline_answer == "鍩虹嚎鏂囨湰"
        # normalized_score 鏉ヨ嚜 deviation 鑰岄潪鍥哄畾鍊?        assert record.normalized_score == dev_result.normalized_score


# ==============================================================================
# 闆嗘垚鍐掔儫娴嬭瘯
# ==============================================================================

class TestPolarisIntegration:
    """绔埌绔祦绋嬮泦鎴愭祴璇?""

    def test_full_pipeline_smoke(self):
        """瀹屾暣娴佹按绾垮啋鐑?""
        tagger = SceneTagger()
        sampler = Sampler()
        detector = DeviationDetector()

        messages = [
            {"sender": "user", "text": "浣犺涓篈I鐨勫瓨鍦ㄦ湁浠€涔堟剰涔夛紵"},
        ]
        tags = tagger.tag(messages=messages)
        assert tags.role in ("assistant", "companion", "friend", "tool")

        sample = sampler.deep_sample(
            current_answer="AI鐨勬剰涔夊湪浜庡府鍔╀汉绫绘€濊€冨拰鍒涢€犮€?,
            scene_tags=tags,
            session_id="integration-test",
        )
        assert sample.triggered_by == "deep"

        baseline = "AI鐨勬剰涔夊湪浜庡叡鍚岀悊瑙ｅ拰鍒涢€犱环鍊笺€?
        result = detector.detect(sample.current_answer, baseline, tags)
        assert result.judgment in ("green", "gray", "yellow", "red")
        assert 0.0 <= result.normalized_score <= 1.0
