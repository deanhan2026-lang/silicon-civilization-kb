#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""G009 P1-D MeshIdentity 一致性模块测试"""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from meshidentity import consistency, history


class TestHistory(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.hf = os.path.join(self.tmp.name, "history.jsonl")

    def tearDown(self):
        self.tmp.cleanup()

    def test_record_and_load(self):
        history.record_behavior("node1", "normal", goal="G008", history_file=self.hf)
        history.record_behavior("node1", "violation", goal="G008", history_file=self.hf)
        history.record_behavior("node2", "suspicious", history_file=self.hf)
        all_ev = history.load_history(history_file=self.hf)
        self.assertEqual(len(all_ev), 3)
        n1 = history.load_history(node_id="node1", history_file=self.hf)
        self.assertEqual(len(n1), 2)
        self.assertEqual(n1[0]["behavior_type"], "normal")
        self.assertEqual(n1[0]["goal"], "G008")

    def test_invalid_type(self):
        with self.assertRaises(ValueError):
            history.record_behavior("node1", "evil", history_file=self.hf)

    def test_since_filter(self):
        t0 = datetime(2026, 8, 1, tzinfo=timezone.utc)
        t1 = datetime(2026, 8, 5, tzinfo=timezone.utc)
        history.record_behavior("n1", "normal", timestamp=t0.isoformat(), history_file=self.hf)
        history.record_behavior("n1", "violation", timestamp=t1.isoformat(), history_file=self.hf)
        since = datetime(2026, 8, 3, tzinfo=timezone.utc)
        evs = history.load_history(node_id="n1", since=since, history_file=self.hf)
        self.assertEqual(len(evs), 1)
        self.assertEqual(evs[0]["behavior_type"], "violation")


class TestConsistency(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.hf = os.path.join(self.tmp.name, "history.jsonl")
        self.now = datetime(2026, 8, 6, tzinfo=timezone.utc)

    def tearDown(self):
        self.tmp.cleanup()

    def test_no_history_returns_1(self):
        self.assertEqual(consistency.get_consistency_score("ghost", history_file=self.hf, now=self.now), 1.0)

    def test_all_normal_returns_1(self):
        history.record_behavior("n1", "normal", timestamp=self.now.isoformat(), history_file=self.hf)
        self.assertEqual(consistency.get_consistency_score("n1", history_file=self.hf, now=self.now), 1.0)

    def test_one_violation(self):
        history.record_behavior("n1", "violation", timestamp=self.now.isoformat(), history_file=self.hf)
        score = consistency.get_consistency_score("n1", history_file=self.hf, now=self.now)
        self.assertAlmostEqual(score, 0.7, places=4)  # 1.0 - 0.3

    def test_two_violations(self):
        history.record_behavior("n1", "violation", timestamp=self.now.isoformat(), history_file=self.hf)
        history.record_behavior("n1", "violation", timestamp=self.now.isoformat(), history_file=self.hf)
        score = consistency.get_consistency_score("n1", history_file=self.hf, now=self.now)
        self.assertAlmostEqual(score, 0.4, places=4)  # 1.0 - 0.6 -> 频繁偏离区间

    def test_suspicious_lighter(self):
        history.record_behavior("n1", "suspicious", timestamp=self.now.isoformat(), history_file=self.hf)
        score = consistency.get_consistency_score("n1", history_file=self.hf, now=self.now)
        self.assertAlmostEqual(score, 0.9, places=4)

    def test_time_decay_old_violation(self):
        old = self.now - timedelta(days=6.5)
        history.record_behavior("n1", "violation", timestamp=old.isoformat(), history_file=self.hf)
        score = consistency.get_consistency_score("n1", history_file=self.hf, now=self.now)
        # 衰减: age=6.5d, window=7d -> decay=1-6.5/7≈0.0714 -> 扣 0.3*0.0714≈0.0214
        self.assertGreater(score, 0.9)
        self.assertLess(score, 1.0)

    def test_outside_window_ignored(self):
        old = self.now - timedelta(days=30)
        history.record_behavior("n1", "violation", timestamp=old.isoformat(), history_file=self.hf)
        score = consistency.get_consistency_score("n1", history_file=self.hf, now=self.now)
        self.assertEqual(score, 1.0)

    def test_interpret_buckets(self):
        self.assertEqual(consistency.interpret(1.0), "consistent")
        self.assertEqual(consistency.interpret(0.7), "acceptable_deviation")
        self.assertEqual(consistency.interpret(0.3), "frequent_deviation")


class TestApi(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.hf = os.path.join(self.tmp.name, "history.jsonl")

    def tearDown(self):
        self.tmp.cleanup()

    def _start(self):
        import threading
        from http.server import ThreadingHTTPServer
        from meshidentity import api as api_mod
        api_mod._history_file_override = self.hf
        srv = ThreadingHTTPServer(("127.0.0.1", 0), api_mod.Handler)
        port = srv.server_address[1]
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        return srv, port

    def test_get_consistency(self):
        import urllib.request
        srv, port = self._start()
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/v1/meshidentity/consistency/did%3Akey%3Anode1?days=7",
                timeout=5,
            ) as resp:
                self.assertEqual(resp.status, 200)
                data = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(data["node_id"], "did:key:node1")
                self.assertIn("consistency_score", data)
                self.assertIn("interpretation", data)
        finally:
            srv.shutdown()
            srv.server_close()

    def test_post_behavior_then_score(self):
        import urllib.request
        srv, port = self._start()
        try:
            body = json.dumps({
                "node_id": "did:key:n2",
                "behavior_type": "violation",
                "goal": "G008",
            }).encode("utf-8")
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/v1/meshidentity/behavior",
                data=body, method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                self.assertEqual(resp.status, 201)
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/v1/meshidentity/consistency/did%3Akey%3An2", timeout=5
            ) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            self.assertAlmostEqual(data["consistency_score"], 0.7, places=4)
        finally:
            srv.shutdown()
            srv.server_close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
