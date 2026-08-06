#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
meshidentity/api.py — MeshIdentity 一致性 API（G009 P1-D）

- GET /api/v1/meshidentity/consistency/{node_id}?days=7
- POST /api/v1/meshidentity/behavior   记录行为（测试/集成用）
- GET  /health

启动: python -m meshidentity.api [--port 8602]
"""
import argparse
import json
import sys
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

from common.logger import get_logger
from meshidentity import consistency, history

logger = get_logger("meshidentity.api")

_history_file_override = None


class Handler(BaseHTTPRequestHandler):
    server_version = "MeshIdentityConsistency/1.0"

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/health":
            self._send(200, {"status": "ok", "service": "meshidentity-consistency"})
            return
        # /api/v1/meshidentity/consistency/{node_id}
        prefix = "/api/v1/meshidentity/consistency/"
        if path.startswith(prefix):
            node_id = unquote(path[len(prefix):].strip("/"))
            if not node_id:
                self._send(400, {"error": "node_id required"})
                return
            qs = parse_qs(parsed.query)
            try:
                days = float(qs.get("days", ["7"])[0])
            except ValueError:
                self._send(400, {"error": "days must be a number"})
                return
            score = consistency.get_consistency_score(
                node_id,
                time_window=timedelta(days=days),
                history_file=_history_file_override,
            )
            self._send(200, {
                "node_id": node_id,
                "days": days,
                "consistency_score": score,
                "interpretation": consistency.interpret(score),
            })
            return
        self._send(404, {"error": f"not found: {path}"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/v1/meshidentity/behavior":
            self._send(404, {"error": f"not found: {parsed.path}"})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            data = json.loads(raw.decode("utf-8") or "{}")
        except (ValueError, json.JSONDecodeError) as e:
            self._send(400, {"error": f"invalid JSON: {e}"})
            return
        node_id = data.get("node_id")
        btype = data.get("behavior_type")
        if not node_id or not btype:
            self._send(400, {"error": "node_id and behavior_type required"})
            return
        try:
            ev = history.record_behavior(
                node_id=node_id,
                behavior_type=btype,
                goal=data.get("goal"),
                timestamp=data.get("timestamp"),
                history_file=_history_file_override,
            )
        except ValueError as e:
            self._send(422, {"error": str(e)})
            return
        self._send(201, {"ok": True, "event": ev})


def main(argv=None) -> int:
    global _history_file_override
    p = argparse.ArgumentParser(description="MeshIdentity 一致性 API")
    p.add_argument("--port", type=int, default=8602)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--file", default=None, help="行为历史文件路径")
    args = p.parse_args(argv)
    _history_file_override = args.file

    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    logger.info("MeshIdentity 一致性 API 已启动: http://%s:%d", args.host, args.port)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
