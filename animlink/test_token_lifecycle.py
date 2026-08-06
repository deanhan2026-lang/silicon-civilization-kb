#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TK-TOKEN-LIFECYCLE-001 单元测试：状态迁移 / 超时规则 / 汇总 / 迁移"""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from animlink import token_lifecycle as tl

NOW = datetime(2026, 8, 6, 12, 0, 0, tzinfo=timezone.utc)


def make_dir() -> str:
    d = tempfile.mkdtemp(prefix="tk_lc_")
    return d


def seed_token(d, tid="tk_test_001", status="issued", **overrides):
    tok = {
        "id": tid, "issued_by": "nyx-windows", "issued_to": "iris",
        "title": "测试令牌", "issued_at": "2026-08-05T10:00:00+00:00",
        "accepted_at": None, "delivered_at": None, "verified_at": None,
        "status": status, "priority": "P2", "summary": "test",
        "deliverables": [], "spec": None,
    }
    tok.update(overrides)
    tl.save_token(tok, d)
    return tok


class TestStateMachine(unittest.TestCase):
    def setUp(self):
        self.d = make_dir()
        seed_token(self.d, "tk_a")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.d, ignore_errors=True)

    def test_full_lifecycle(self):
        """issue -> accept -> in_progress -> submit -> verify -> archive 每步状态正确"""
        expected = [
            ("accepted", "accepted_at"),
            ("in_progress", None),
            ("submitted", "delivered_at"),
            ("verified", "verified_at"),
            ("archived", None),
        ]
        cur = tl.load_token(self.d, "tk_a")
        self.assertEqual(cur["status"], "issued")
        for status, ts_field in expected:
            cur = tl.transition("tk_a", status, tokens_dir=self.d, now=NOW)
            self.assertEqual(cur["status"], status)
            if ts_field:
                self.assertIsNotNone(cur[ts_field], f"{ts_field} 应被填充")
            else:
                self.assertIsNone(cur.get("delivered_at") if status == "in_progress" else None)

    def test_rejected_branch(self):
        """accepted -> rejected -> archived 分支"""
        tl.transition("tk_a", "accepted", tokens_dir=self.d, now=NOW)
        cur = tl.transition("tk_a", "rejected", tokens_dir=self.d, now=NOW)
        self.assertEqual(cur["status"], "rejected")
        cur = tl.transition("tk_a", "archived", tokens_dir=self.d, now=NOW)
        self.assertEqual(cur["status"], "archived")

    def test_invalid_transition_rejected(self):
        """非法迁移拒绝：issued->submitted / verified->in_progress / 未知状态"""
        for bad in ("submitted", "verified", "archived", "in_progress"):
            with self.assertRaises(ValueError, msg=f"issued->{bad} 应被拒绝"):
                tl.transition("tk_a", bad, tokens_dir=self.d, now=NOW)
        tl.transition("tk_a", "accepted", tokens_dir=self.d, now=NOW)
        with self.assertRaises(ValueError):
            tl.transition("tk_a", "verified", tokens_dir=self.d, now=NOW)  # accepted->verified 非法
        with self.assertRaises(ValueError):
            tl.transition("tk_a", "bogus", tokens_dir=self.d, now=NOW)

    def test_transition_missing_token(self):
        with self.assertRaises(FileNotFoundError):
            tl.transition("tk_nonexist", "accepted", tokens_dir=self.d, now=NOW)


class TestTimeoutScan(unittest.TestCase):
    def setUp(self):
        self.d = make_dir()
        self.reminders = []

    def tearDown(self):
        import shutil
        shutil.rmtree(self.d, ignore_errors=True)

    def _emit(self, level, source, summary, details=None, suggested_action="", checkpoint=False, checkpoint_note=""):
        self.reminders.append({"level": level, "summary": summary})
        return "pain_001"

    def test_issued_timeout_24h(self):
        """签发 25h 未接受 -> P3"""
        seed_token(self.d, "tk_old", issued_at="2026-08-05T10:00:00+00:00")
        now = NOW + timedelta(hours=25)
        rs = tl.scan_timeouts(self.d, now=now, pain_emit=self._emit)
        self.assertEqual(len(rs), 1)
        self.assertEqual(rs[0]["level"], "P3")
        self.assertEqual(rs[0]["token_id"], "tk_old")

    def test_issued_not_timeout(self):
        """签发 1h 未接受 -> 不提醒"""
        seed_token(self.d, "tk_fresh", issued_at=NOW.isoformat())
        rs = tl.scan_timeouts(self.d, now=NOW + timedelta(hours=1), pain_emit=self._emit)
        self.assertEqual(rs, [])

    def test_accepted_timeout_7d(self):
        """接受后 8 天未交付 -> P2"""
        seed_token(self.d, "tk_acc", status="accepted",
                   accepted_at="2026-07-28T10:00:00+00:00")
        now = NOW + timedelta(days=8)
        rs = tl.scan_timeouts(self.d, now=now, pain_emit=self._emit)
        self.assertEqual(len(rs), 1)
        self.assertEqual(rs[0]["level"], "P2")

    def test_submitted_timeout_48h(self):
        """交付后 49h 未验证 -> P3"""
        seed_token(self.d, "tk_sub", status="submitted",
                   delivered_at="2026-08-04T10:00:00+00:00")
        now = NOW + timedelta(hours=49)
        rs = tl.scan_timeouts(self.d, now=now, pain_emit=self._emit)
        self.assertEqual(len(rs), 1)
        self.assertEqual(rs[0]["status"], "submitted")

    def test_no_reminder_when_all_fresh(self):
        seed_token(self.d, "tk1", issued_at=NOW.isoformat())
        seed_token(self.d, "tk2", status="verified",
                   delivered_at=NOW.isoformat(), verified_at=NOW.isoformat())
        rs = tl.scan_timeouts(self.d, now=NOW, pain_emit=self._emit)
        self.assertEqual(rs, [])

    def test_pain_bus_fallback_no_crash(self):
        """未注入 emit 时降级为日志，不崩溃"""
        seed_token(self.d, "tk_old", issued_at="2026-08-01T10:00:00+00:00")
        rs = tl.scan_timeouts(self.d, now=NOW)  # 不注入 pain_emit
        self.assertEqual(len(rs), 1)  # 仍记录提醒


class TestAutoArchive(unittest.TestCase):
    def setUp(self):
        self.d = make_dir()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.d, ignore_errors=True)

    def test_verified_auto_archived(self):
        seed_token(self.d, "tk_v", status="verified", verified_at=NOW.isoformat())
        seed_token(self.d, "tk_i", status="in_progress")
        archived = tl.auto_archive_verified(self.d, now=NOW)
        self.assertEqual(archived, ["tk_v"])
        self.assertEqual(tl.load_token(self.d, "tk_v")["status"], "archived")
        self.assertEqual(tl.load_token(self.d, "tk_i")["status"], "in_progress")


class TestHistoryAndMigrate(unittest.TestCase):
    def setUp(self):
        self.d = make_dir()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.d, ignore_errors=True)

    def test_generate_history(self):
        seed_token(self.d, "tk_1")
        seed_token(self.d, "tk_2", status="verified", verified_at=NOW.isoformat())
        h = tl.generate_history(self.d, now=NOW)
        self.assertEqual(h["schema"], "anima-token-history-v2")
        self.assertEqual(len(h["tokens"]), 2)
        # 时间戳字段全保留
        t0 = h["tokens"][0]
        for f in ("issued_at", "accepted_at", "delivered_at", "verified_at"):
            self.assertIn(f, t0)
        self.assertIn("priority", t0)
        # 文件存在且可读
        hf = os.path.join(self.d, tl.DEFAULT_HISTORY_FILE)
        self.assertTrue(os.path.exists(hf))

    def test_legacy_migration(self):
        """旧字段 initiator/executor/date/completed -> 新 Schema"""
        legacy = {
            "id": "tk_legacy_001", "initiator": "nyx-windows", "executor": "iris",
            "title": "旧令牌", "date": "2026-07-20T14:41:00+08:00",
            "completed": "2026-07-21T10:00:00+08:00",
            "status": "completed", "summary": "旧格式",
        }
        with open(os.path.join(self.d, "tk_legacy_001.json"), "w", encoding="utf-8") as f:
            json.dump(legacy, f, ensure_ascii=False)
        norm = tl.normalize(legacy)
        self.assertEqual(norm["issued_by"], "nyx-windows")
        self.assertEqual(norm["issued_to"], "iris")
        self.assertIsNotNone(norm["issued_at"])
        self.assertIsNotNone(norm["verified_at"])  # completed -> verified_at
        self.assertEqual(norm["status"], "verified")  # completed -> verified
        self.assertIn("priority", norm)

    def test_migrate_dir(self):
        legacy = {"id": "tk_mig_001", "initiator": "nyx-windows", "executor": "iris",
                  "title": "迁移", "date": "2026-07-20T00:00:00+08:00", "status": "pending"}
        with open(os.path.join(self.d, "tk_mig_001.json"), "w", encoding="utf-8") as f:
            json.dump(legacy, f, ensure_ascii=False)
        r = tl.migrate_tokens_dir(self.d)
        self.assertEqual(r["migrated"], 1)
        self.assertEqual(r["skipped"], 0)
        # 备份存在
        self.assertTrue(os.path.exists(os.path.join(self.d, "tk_mig_001.json.bak")))
        # 迁移后字段正确
        tok = tl.load_token(self.d, "tk_mig_001")
        self.assertEqual(tok["issued_by"], "nyx-windows")
        self.assertEqual(tok["status"], "issued")  # pending -> issued
        # 汇总已生成
        self.assertTrue(os.path.exists(os.path.join(self.d, tl.DEFAULT_HISTORY_FILE)))


class TestIssue(unittest.TestCase):
    def setUp(self):
        self.d = make_dir()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.d, ignore_errors=True)

    def test_issue_creates_file(self):
        tok = tl.issue("tk_new_001", "nyx-windows", "iris", "新任务",
                       summary="s", priority="P1", deliverables=["a"], tokens_dir=self.d, now=NOW)
        self.assertEqual(tok["status"], "issued")
        self.assertEqual(tok["issued_at"], NOW.isoformat())
        loaded = tl.load_token(self.d, "tk_new_001")
        self.assertEqual(loaded["priority"], "P1")

    def test_issue_invalid_priority_fallback(self):
        tok = tl.issue("tk_new_002", "nyx-windows", "iris", "x", priority="P9",
                       tokens_dir=self.d, now=NOW)
        self.assertEqual(tok["priority"], "P2")


if __name__ == "__main__":
    unittest.main(verbosity=2)
