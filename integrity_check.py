#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
integrity_check.py - 知识库完整性定时检查脚本
Fixes: relative paths
"""

import os
import sys
import json
import hashlib
import argparse
from pathlib import Path
from datetime import datetime

_current_dir = Path(__file__).parent.resolve()
if str(_current_dir) not in sys.path:
    sys.path.insert(0, str(_current_dir))

REPO_ROOT = Path(__file__).parent.resolve()
BASE_DIR = REPO_ROOT / "knowledge-base"
ENTITY_TYPES = ["Concept", "Entity", "Event", "Rule", "Artifact", "Value"]
HASH_INDEX = REPO_ROOT / "hash_index.json"
AUDIT_LOG = REPO_ROOT / "audit.jsonl"
CRON_LOG = REPO_ROOT / "integrity_cron.log"

ALERT_WEBHOOK = os.environ.get("INTEGRITY_ALERT_WEBHOOK", "")


def compute_file_hash(filepath: Path) -> str:
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def load_hash_index() -> dict:
    if HASH_INDEX.exists():
        try:
            return json.loads(HASH_INDEX.read_text(encoding="utf-8"))
        except:
            return {}
    return {}


def full_integrity_check() -> dict:
    results = {"ok": [], "tampered": [], "new": [], "missing": []}
    index = load_hash_index()

    for entry_type in ENTITY_TYPES:
        type_dir = BASE_DIR / entry_type.lower()
        if not type_dir.exists():
            continue
        for f in sorted(type_dir.glob("*.md")):
            rel_path = str(f.relative_to(REPO_ROOT))
            current_hash = compute_file_hash(f)
            if rel_path not in index:
                results["new"].append({"path": rel_path, "hash": current_hash})
            elif current_hash != index[rel_path]["hash"]:
                results["tampered"].append({
                    "path": rel_path,
                    "stored_hash": index[rel_path]["hash"],
                    "current_hash": current_hash
                })
            else:
                results["ok"].append({"path": rel_path, "hash": current_hash})

    for rel_path in index.keys():
        full_path = REPO_ROOT / rel_path
        if not full_path.exists():
            results["missing"].append({"path": rel_path})

    return results


def audit_log(action: str, detail: str, status: str = "ok"):
    entry = {
        "timestamp": datetime.now().isoformat(),
        "action": f"CRON_{action}",
        "account": "cron",
        "file_path": "",
        "detail": detail,
        "device": os.environ.get("COMPUTERNAME", "unknown"),
        "ip": "",
        "status": status,
        "rule_id": "G005",
        "hash_before": "",
        "hash_after": "",
        "decision": "cron_check"
    }
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(line)


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    CRON_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(CRON_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def trigger_circuit_breaker(reason: str):
    try:
        from gov_parser.circuit_breaker import get_circuit_breaker
        cb = get_circuit_breaker()
        result = cb.freeze(reason=reason, operator="cron")
        log(f"CIRCUIT_BREAKER TRIGGERED: {reason}")
        log(f"Result: {result}")
        return result
    except Exception as e:
        log(f"WARNING: Failed to trigger circuit breaker: {e}")
        return None


def send_alert(results: dict):
    if not ALERT_WEBHOOK:
        return
    try:
        import urllib.request
        payload = json.dumps({
            "text": f"[硅基文明知识库] 完整性检查告警",
            "attachments": [{
                "color": "danger",
                "fields": [
                    {"title": "被篡改文件", "value": str(len(results["tampered"])), "short": True},
                    {"title": "新增文件", "value": str(len(results["new"])), "short": True},
                    {"title": "缺失文件", "value": str(len(results["missing"])), "short": True},
                    {"title": "正常文件", "value": str(len(results["ok"])), "short": True}
                ]
            }]
        }).encode("utf-8")
        req = urllib.request.Request(
            ALERT_WEBHOOK,
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=5)
        log("Alert sent successfully")
    except Exception as e:
        log(f"WARNING: Failed to send alert: {e}")


def main():
    parser = argparse.ArgumentParser(description="知识库完整性检查")
    parser.add_argument("--dry-run", action="store_true", help="只检查不操作")
    parser.add_argument("--quiet", action="store_true", help="静默模式")
    args = parser.parse_args()

    log("=" * 40)
    log("Integrity Check Started")

    results = full_integrity_check()

    issues = results["tampered"] + results["missing"]
    has_issues = len(issues) > 0

    if has_issues:
        detail = f"完整性检查: ok={len(results['ok'])} tampered={len(results['tampered'])} missing={len(results['missing'])} new={len(results['new'])}"
        audit_log("INTEGRITY_ALERT", detail, status="warning")
        log(f"ISSUES FOUND: {len(results['tampered'])} tampered, {len(results['missing'])} missing")

        if not args.dry_run:
            reason = f"知识库完整性检查失败: {len(results['tampered'])}个文件被篡改, {len(results['missing'])}个文件缺失"
            trigger_circuit_breaker(reason)
            send_alert(results)
    else:
        detail = f"完整性检查: ok={len(results['ok'])} new={len(results['new'])}"
        audit_log("INTEGRITY_CHECK", detail, status="ok")
        if not args.quiet:
            log(f"All OK: {len(results['ok'])} files verified, {len(results['new'])} new files")

    log("Integrity Check Completed")
    log("=" * 40)

    return 1 if has_issues else 0


if __name__ == "__main__":
    sys.exit(main())
