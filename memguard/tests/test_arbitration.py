#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""G009 P1-C 仲裁记录模块测试（unittest，独立可跑）"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# 保证从项目根导入
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from memguard import arbitration, g009_audit as audit


class TestArbitrationRecord(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.rec_file = os.path.join(self.tmp.name, "arb_records.jsonl")
        self.audit_file = os.path.join(self.tmp.name, "audit.jsonl")

    def tearDown(self):
        self.tmp.cleanup()

    def _valid_kwargs(self, **overrides):
        kw = dict(
            node_id="did:key:z6Mksmum5T8CruP8Wfb5biQ8fsHNGqhBf1QFgqjq4JFVoQqr",
            constraint_level="L2",
            deviation_score=0.42,
            history_consistency=0.87,
            response_level="continue",
            decision_rationale="测试裁决：偏离可接受，继续执行",
            approver_did="did:key:z6Mk1234567890",
        )
        kw.update(overrides)
        return kw

    def test_record_schema_fields(self):
        rec = arbitration.record_arbitration(record_file=self.rec_file, **self._valid_kwargs())
        self.assertEqual(rec["event_type"], "g009_arbitration")
        self.assertIn("timestamp", rec)
        self.assertIn("approver_did", rec)
        self.assertEqual(rec["constraint_level"], "L2")
        self.assertEqual(rec["response_level"], "continue")
        self.assertEqual(rec["deviation_score"], 0.42)
        self.assertEqual(rec["history_consistency"], 0.87)

    def test_invalid_constraint_level(self):
        with self.assertRaises(ValueError):
            arbitration.record_arbitration(record_file=self.rec_file, **self._valid_kwargs(constraint_level="L4"))

    def test_invalid_response_level(self):
        with self.assertRaises(ValueError):
            arbitration.record_arbitration(record_file=self.rec_file, **self._valid_kwargs(response_level="stop"))

    def test_score_out_of_range(self):
        with self.assertRaises(ValueError):
            arbitration.record_arbitration(record_file=self.rec_file, **self._valid_kwargs(deviation_score=1.5))
        with self.assertRaises(ValueError):
            arbitration.record_arbitration(record_file=self.rec_file, **self._valid_kwargs(history_consistency=-0.1))

    def test_hard_rule_high_deviation_low_consistency(self):
        """偏离>=0.8 且一致性<=0.3 时不允许 continue"""
        with self.assertRaises(ValueError):
            arbitration.record_arbitration(
                record_file=self.rec_file,
                **self._valid_kwargs(deviation_score=0.9, history_consistency=0.2, response_level="continue"),
            )
        # pause 应该允许
        rec = arbitration.record_arbitration(
            record_file=self.rec_file,
            **self._valid_kwargs(deviation_score=0.9, history_consistency=0.2, response_level="pause"),
        )
        self.assertEqual(rec["response_level"], "pause")

    def test_invalid_did(self):
        with self.assertRaises(ValueError):
            arbitration.record_arbitration(record_file=self.rec_file, **self._valid_kwargs(approver_did="not-a-did"))

    def test_load_and_count(self):
        arbitration.record_arbitration(record_file=self.rec_file, **self._valid_kwargs())
        arbitration.record_arbitration(record_file=self.rec_file, **self._valid_kwargs(node_id="did:key:node2"))
        recs = arbitration.load_records(self.rec_file)
        self.assertEqual(len(recs), 2)
        self.assertEqual(arbitration.count_records(self.rec_file), 2)
        # JSONL 格式校验：每行一个 JSON
        with open(self.rec_file, encoding="utf-8") as f:
            lines = [l for l in f.read().strip().splitlines() if l.strip()]
        self.assertEqual(len(lines), 2)
        for line in lines:
            json.loads(line)

    def test_audit_integration(self):
        rec = arbitration.record_arbitration(record_file=self.rec_file, **self._valid_kwargs())
        ev = audit.record_arbitration_event(rec, audit_file=self.audit_file)
        self.assertEqual(ev["event"], "g009_arbitration")
        self.assertEqual(ev["actor"], rec["node_id"])
        logs = audit.load_audit(self.audit_file)
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["detail"]["response_level"], "continue")


class TestApi(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.rec_file = os.path.join(self.tmp.name, "api_records.jsonl")
        self.audit_file = os.path.join(self.tmp.name, "api_audit.jsonl")

    def tearDown(self):
        self.tmp.cleanup()

    def _start_server(self):
        import threading
        from memguard import api as api_mod
        api_mod._record_file_override = self.rec_file
        api_mod._audit_file_override = self.audit_file
        from http.server import ThreadingHTTPServer
        srv = ThreadingHTTPServer(("127.0.0.1", 0), api_mod.Handler)
        port = srv.server_address[1]
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        return srv, port

    def test_post_record(self):
        import urllib.request
        srv, port = self._start_server()
        try:
            body = json.dumps({
                "node_id": "did:key:z6MkTestNode",
                "constraint_level": "L3",
                "deviation_score": 0.95,
                "history_consistency": 0.15,
                "response_level": "pause",
                "decision_rationale": "API 测试：高风险暂停",
            }).encode("utf-8")
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/v1/arbitration/record",
                data=body, method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                self.assertEqual(resp.status, 201)
                data = json.loads(resp.read().decode("utf-8"))
                self.assertTrue(data["ok"])
                self.assertEqual(data["record"]["response_level"], "pause")
            # 校验失败场景
            bad = json.dumps({"node_id": "x", "constraint_level": "L9"}).encode("utf-8")
            req2 = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/v1/arbitration/record",
                data=bad, method="POST",
                headers={"Content-Type": "application/json"},
            )
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(req2, timeout=5)
            self.assertIn(ctx.exception.code, (400, 422))
            # health
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as resp:
                self.assertEqual(resp.status, 200)
        finally:
            srv.shutdown()
            srv.server_close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
