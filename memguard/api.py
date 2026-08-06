#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
memguard/api.py — G009 仲裁记录 HTTP API（P1-C）

零依赖实现（标准库 http.server）：
- POST /api/v1/arbitration/record  创建仲裁记录
- GET  /api/v1/arbitration/records 查询全部记录
- GET  /health                     健康检查

启动: python -m memguard.api [--port 8601] [--file PATH]
"""
import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from common.logger import get_logger
from memguard import arbitration, g009_audit as audit

logger = get_logger("memguard.api")

# 运行时覆盖记录文件（CLI 指定时）
_record_file_override = None
_audit_file_override = None


class Handler(BaseHTTPRequestHandler):
    server_version = "MemGuardArbitration/1.0"

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/health":
            self._send(200, {"status": "ok", "service": "memguard-arbitration"})
        elif path == "/api/v1/arbitration/records":
            recs = arbitration.load_records(_record_file_override)
            self._send(200, {"count": len(recs), "records": recs})
        else:
            self._send(404, {"error": f"not found: {path}"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path != "/api/v1/arbitration/record":
            self._send(404, {"error": f"not found: {path}"})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            data = json.loads(raw.decode("utf-8") or "{}")
        except (ValueError, json.JSONDecodeError) as e:
            self._send(400, {"error": f"invalid JSON: {e}"})
            return

        required = [
            "node_id", "constraint_level", "deviation_score",
            "history_consistency", "response_level", "decision_rationale",
        ]
        missing = [k for k in required if k not in data]
        if missing:
            self._send(400, {"error": f"missing fields: {missing}"})
            return

        try:
            rec = arbitration.record_arbitration(
                node_id=data["node_id"],
                constraint_level=data["constraint_level"],
                deviation_score=data["deviation_score"],
                history_consistency=data["history_consistency"],
                response_level=data["response_level"],
                decision_rationale=data["decision_rationale"],
                approver_did=data.get("approver_did"),
                timestamp=data.get("timestamp"),
                record_file=_record_file_override,
            )
        except (ValueError, TypeError) as e:
            self._send(422, {"error": str(e)})
            return

        # 集成审计
        try:
            audit.record_arbitration_event(rec, audit_file=_audit_file_override)
        except OSError as e:
            logger.warning("审计写入失败: %s", e)

        self._send(201, {"ok": True, "record": rec})


def main(argv=None) -> int:
    global _record_file_override, _audit_file_override
    p = argparse.ArgumentParser(description="G009 仲裁记录 API")
    p.add_argument("--port", type=int, default=8601)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--file", default=None, help="仲裁记录文件路径")
    p.add_argument("--audit-file", default=None, help="审计日志文件路径")
    args = p.parse_args(argv)

    _record_file_override = args.file
    _audit_file_override = args.audit_file

    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    logger.info("MemGuard 仲裁 API 已启动: http://%s:%d", args.host, args.port)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
