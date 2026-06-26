#!/usr/bin/env python3
"""
silicon_civilization_kb_web.py - 硅基文明数据库 Web UI 后端
Flask应用，提供REST API读取knowledge-base数据

作者：Nyx
日期：2026-05-18
更新：2026-05-20 - 添加L1 SHA256校验 + L3审计日志改JSON
"""

import os
import sys
import io
import json
import hashlib
from pathlib import Path
from datetime import datetime
from flask import Flask, jsonify, send_from_directory, abort, Response, request

# 日志
from common.logger import get_logger
logger = get_logger(__name__)

# Fix Windows console encoding
if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except:
        pass

import yaml

# ============== 治理架构集成 ==============
# 添加当前目录到sys.path以便导入gov_parser
import sys
from pathlib import Path
_current_dir = Path(__file__).parent.resolve()
if str(_current_dir) not in sys.path:
    sys.path.insert(0, str(_current_dir))

try:
    from gov_parser import (
        init_gov_parser,
        reload_gov_parser,
        get_gov_status,
        get_loader,
        get_parser_core,
        get_matcher,
        get_hook,
        governance_check,
        get_circuit_breaker,
        is_frozen
    )
    GOV_PARSER_AVAILABLE = True
    logger.info("治理解析器模块加载成功")
except ImportError as e:
    GOV_PARSER_AVAILABLE = False
    logger.warning(f"治理解析器模块加载失败: {e}")

app = Flask(__name__, static_folder='static')

# 配置
BASE_DIR = Path(os.path.expanduser("~/.qclaw/workspace-agent-d9479bde/knowledge-base"))
ENTITY_TYPES = ["Concept", "Entity", "Event", "Rule", "Artifact", "Value"]
AUDIT_LOG = Path(os.path.expanduser("~/.qclaw/workspace-agent-d9479bde/silicon-civilization-kb/audit.jsonl"))
HASH_INDEX = Path(os.path.expanduser("~/.qclaw/workspace-agent-d9479bde/silicon-civilization-kb/hash_index.json"))

# ============== L1 目录权限锁 ==============
# 白名单目录：只有这些目录允许读写操作
ALLOWED_DIRS = [
    BASE_DIR,  # 知识库主目录
    Path(os.path.expanduser("~/.qclaw/workspace-agent-d9479bde/silicon-civilization-kb")),  # 系统目录（审计日志、hash索引）
]

def is_path_allowed(path: Path, operation: str = "read") -> tuple:
    """
    检查路径是否在白名单内
    返回: (allowed: bool, reason: str)
    """
    abs_path = path.resolve()
    
    for allowed_dir in ALLOWED_DIRS:
        try:
            # 检查是否在允许的目录下
            rel = abs_path.relative_to(allowed_dir.resolve())
            # 检查是否试图跳出（如 ../../../etc/passwd）
            if str(rel).startswith("..") or str(rel).startswith("/"):
                continue
            return True, "ok"
        except ValueError:
            # 不在此目录下
            pass
    
    return False, f"Path not in whitelist: {abs_path}"

# ============== L1 SHA256 完整性校验 ==============

def compute_file_hash(filepath: Path) -> str:
    """计算单个文件的SHA256哈希"""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def load_hash_index() -> dict:
    """加载hash索引"""
    if HASH_INDEX.exists():
        try:
            return json.loads(HASH_INDEX.read_text(encoding="utf-8"))
        except:
            return {}
    return {}


def save_hash_index(index: dict):
    """保存hash索引"""
    HASH_INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


def update_hash_for_file(filepath: Path) -> str:
    """更新单个文件的hash"""
    index = load_hash_index()
    rel_path = str(filepath.relative_to(BASE_DIR))
    file_hash = compute_file_hash(filepath)
    index[rel_path] = {
        "hash": file_hash,
        "last_modified": datetime.now().isoformat(),
        "size": filepath.stat().st_size
    }
    save_hash_index(index)
    return file_hash


def verify_file_integrity(filepath: Path) -> dict:
    """校验单个文件完整性"""
    index = load_hash_index()
    rel_path = str(filepath.relative_to(BASE_DIR))
    
    current_hash = compute_file_hash(filepath)
    
    if rel_path not in index:
        return {
            "status": "new",
            "path": rel_path,
            "hash": current_hash
        }
    
    stored_hash = index[rel_path]["hash"]
    if current_hash == stored_hash:
        return {
            "status": "ok",
            "path": rel_path,
            "hash": current_hash
        }
    else:
        return {
            "status": "tampered",
            "path": rel_path,
            "stored_hash": stored_hash,
            "current_hash": current_hash
        }


def full_integrity_check() -> dict:
    """全量完整性校验"""
    results = {
        "ok": [],
        "tampered": [],
        "new": [],
        "missing": []
    }
    
    index = load_hash_index()
    
    # 检查现有文件
    for entry_type in ENTITY_TYPES:
        type_dir = BASE_DIR / entry_type.lower()
        if not type_dir.exists():
            continue
        for f in type_dir.glob("*.md"):
            result = verify_file_integrity(f)
            results[result["status"]].append(result["path"])
    
    # 检查缺失文件
    for rel_path in index.keys():
        full_path = BASE_DIR / rel_path
        if not full_path.exists():
            results["missing"].append(rel_path)
    
    return results


def rebuild_hash_index():
    """重建整个hash索引"""
    index = {}
    count = 0
    for entry_type in ENTITY_TYPES:
        type_dir = BASE_DIR / entry_type.lower()
        if not type_dir.exists():
            continue
        for f in type_dir.glob("*.md"):
            rel_path = str(f.relative_to(BASE_DIR))
            file_hash = compute_file_hash(f)
            index[rel_path] = {
                "hash": file_hash,
                "last_modified": datetime.now().isoformat(),
                "size": f.stat().st_size
            }
            count += 1
    save_hash_index(index)
    return count


# ============== L3 审计日志 (JSON Lines) ==============

def audit_log(action: str, detail: dict = None):
    """
    L3 审计日志 (JSON Lines格式，只读追加)
    
    字段标准：
    - timestamp: ISO时间戳
    - action: 操作类型
    - account: 操作账号
    - file_path: 文件路径
    - detail: 变更内容摘要
    - device: 设备标识
    - ip: 操作IP
    - status: 结果状态
    """
    entry = {
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "account": detail.get("account", "system") if detail else "system",
        "file_path": detail.get("file_path", "") if detail else "",
        "detail": detail.get("detail", "") if detail else "",
        "device": detail.get("device", os.environ.get("COMPUTERNAME", "unknown")),
        "ip": detail.get("ip", ""),
        "status": detail.get("status", "ok") if detail else "ok"
    }
    
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(line)
    
    return entry


def read_audit_logs(limit: int = 100, start_time: str = None, end_time: str = None, action: str = None, account: str = None, status: str = None, decision: str = None) -> list:
    """
    读取审计日志（支持过滤）

    参数:
        limit:       返回最近N条
        start_time:  ISO时间字符串，只返回此时间之后的日志
        end_time:    ISO时间字符串，只返回此时间之前的日志
        action:      按操作类型过滤（如 INTEGRITY_CHECK、MSG_SENT）
        account:     按操作账号过滤
        status:      按状态过滤（如 ok、denied、frozen）
        decision:    按决策过滤（如 allow、deny、freeze）
    """
    if not AUDIT_LOG.exists():
        return []

    logs = []
    with open(AUDIT_LOG, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except:
                continue

            # 时间过滤
            if start_time and entry.get("timestamp", "") < start_time:
                continue
            if end_time and entry.get("timestamp", "") > end_time:
                continue

            # 字段过滤
            if action and action.lower() not in entry.get("action", "").lower():
                continue
            if account and account.lower() != entry.get("account", "").lower():
                continue
            if status and status.lower() != entry.get("status", "").lower():
                continue
            if decision and decision.lower() != entry.get("decision", "").lower():
                continue

            logs.append(entry)

    return logs[-limit:]


# ============== 工具函数 ==============

def parse_yaml_front_matter(content: str):
    """解析YAML Front Matter + Markdown正文"""
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            try:
                meta = yaml.safe_load(parts[1]) or {}
            except Exception:
                meta = {}
            body = parts[2].strip()
            return meta, body
    return {}, content


def load_all_entries():
    """加载所有知识库条目（摘要版本，用于列表）"""
    entries = []
    for entry_type in ENTITY_TYPES:
        type_dir = BASE_DIR / entry_type.lower()
        if not type_dir.exists():
            continue
        for f in sorted(type_dir.glob("*.md")):
            try:
                content = f.read_text(encoding="utf-8")
                meta, _ = parse_yaml_front_matter(content)
                if not meta.get("id"):
                    continue
                summary = dict(meta)
                summary["_filename"] = f.name
                summary["_type_dir"] = entry_type.lower()
                entries.append(summary)
            except Exception as e:
                print(f"[WARN] Failed to load {f}: {e}", file=sys.stderr)
                continue
    return entries


def load_entry_by_id_prefix(id_prefix: str):
    """按ID前缀加载完整条目（含body）"""
    for entry_type in ENTITY_TYPES:
        type_dir = BASE_DIR / entry_type.lower()
        if not type_dir.exists():
            continue
        for f in type_dir.glob("*.md"):
            try:
                content = f.read_text(encoding="utf-8")
                meta, body = parse_yaml_front_matter(content)
                mid = meta.get("id", "")
                if mid.startswith(id_prefix):
                    result = dict(meta)
                    result["body"] = body
                    result["_filename"] = f.name
                    return result
            except:
                continue
    return None


# ============== 路由 ==============

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/intercom.html")
def intercom_page():
    return send_from_directory(app.static_folder, "intercom.html")


@app.route("/api/stats")
def api_stats():
    """返回统计信息"""
    entries = load_all_entries()
    return jsonify({
        "total": len(entries),
        "by_type": {t: len([e for e in entries if e.get("type") == t]) for t in ENTITY_TYPES},
        "layer5": len([e for e in entries if e.get("layer") == 5]),
        "iron_law": len([e for e in entries if "iron-law" in (e.get("tags") or [])]),
        "locked": len([e for e in entries if e.get("status") == "locked"]),
    })


@app.route("/api/entries")
def api_entries():
    """返回所有条目摘要"""
    entries = load_all_entries()
    resp = jsonify(entries)
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@app.route("/api/entry/<entry_id>")
def api_entry(entry_id):
    """返回单条完整条目"""
    entry = load_entry_by_id_prefix(entry_id)
    if not entry:
        abort(404, description=f"Entry not found: {entry_id}")
    resp = jsonify(entry)
    resp.headers["Cache-Control"] = "no-cache"
    return resp


# ============== L1 完整性校验 API ==============

@app.route("/api/integrity/check")
def api_integrity_check():
    """全量完整性校验"""
    results = full_integrity_check()
    
    audit_log("INTEGRITY_CHECK", {
        "detail": f"ok={len(results['ok'])} tampered={len(results['tampered'])} new={len(results['new'])} missing={len(results['missing'])}",
        "status": "warning" if results['tampered'] or results['missing'] else "ok"
    })
    
    return jsonify({
        "timestamp": datetime.now().isoformat(),
        "results": results,
        "has_issues": bool(results['tampered'] or results['missing'])
    })


@app.route("/api/integrity/rebuild", methods=["POST"])
@governance_check("kb.file.update", path_field="")
def api_integrity_rebuild():
    """重建hash索引"""
    count = rebuild_hash_index()
    
    audit_log("HASH_INDEX_REBUILD", {
        "detail": f"rebuilt {count} files",
        "status": "ok"
    })
    
    return jsonify({
        "status": "ok",
        "files_indexed": count,
        "timestamp": datetime.now().isoformat()
    })


@app.route("/api/integrity/verify/<path:rel_path>")
def api_integrity_verify_file(rel_path):
    """校验单个文件"""
    filepath = BASE_DIR / rel_path
    if not filepath.exists():
        abort(404, description=f"File not found: {rel_path}")
    
    result = verify_file_integrity(filepath)
    return jsonify(result)


# ============== L3 审计日志 API ==============

@app.route("/api/audit/logs")
def api_audit_logs():
    """读取审计日志（支持过滤）"""
    limit = request.args.get("limit", 100, type=int)
    start_time = request.args.get("start_time")
    end_time = request.args.get("end_time")
    action = request.args.get("action")
    account = request.args.get("account")
    status = request.args.get("status")
    decision = request.args.get("decision")

    logs = read_audit_logs(
        limit=limit,
        start_time=start_time,
        end_time=end_time,
        action=action,
        account=account,
        status=status,
        decision=decision
    )

    # 汇总统计
    total = len(logs)
    decisions = {}
    actions = {}
    for log in logs:
        d = log.get("decision", "unknown")
        decisions[d] = decisions.get(d, 0) + 1
        a = log.get("action", "unknown")
        actions[a] = actions.get(a, 0) + 1

    resp = jsonify({
        "logs": logs,
        "total": total,
        "limit": limit,
        "filters": {
            "start_time": start_time,
            "end_time": end_time,
            "action": action,
            "account": account,
            "status": status,
            "decision": decision
        },
        "summary": {
            "by_decision": decisions,
            "by_action": actions
        },
        "timestamp": datetime.now().isoformat()
    })
    resp.headers["Cache-Control"] = "no-cache"
    return resp


# ============== L1 目录权限锁 API ==============

@app.route("/api/security/check-path")
def api_security_check_path():
    """检查路径是否在白名单内"""
    path_str = request.args.get("path", "")
    operation = request.args.get("operation", "read")
    
    if not path_str:
        return jsonify({"error": "path parameter required"}), 400
    
    test_path = Path(path_str)
    allowed, reason = is_path_allowed(test_path, operation)
    
    audit_log("PATH_CHECK", {
        "detail": f"path={path_str} operation={operation} allowed={allowed}",
        "status": "ok" if allowed else "denied"
    })
    
    return jsonify({
        "path": str(test_path.resolve()),
        "allowed": allowed,
        "reason": reason,
        "operation": operation
    })


@app.route("/api/security/allowed-dirs")
def api_security_allowed_dirs():
    """返回允许的目录列表"""
    return jsonify({
        "allowed_dirs": [str(d.resolve()) for d in ALLOWED_DIRS],
        "base_dir": str(BASE_DIR.resolve())
    })


# ============== Intercom API (跨实例通信) ==============

INTERCOM_DIR = Path(os.path.expanduser("~/.qclaw/workspace-agent-38f2eef5/intercom"))


@app.route("/api/intercom/messages")
def api_intercom_messages():
    """列出所有intercom消息"""
    messages = []
    if not INTERCOM_DIR.exists():
        return jsonify([])
    for f in sorted(INTERCOM_DIR.glob("msg_*.md")):
        try:
            content = f.read_text(encoding="utf-8")
            messages.append({
                "filename": f.name,
                "content": content,
                "lastModified": f.stat().st_mtime
            })
        except Exception as e:
            messages.append({"filename": f.name, "error": str(e)})
    resp = jsonify(messages)
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@app.route("/api/intercom/flags")
def api_intercom_flags():
    """列出所有flag标记"""
    flags = []
    if not INTERCOM_DIR.exists():
        return jsonify([])
    for f in sorted(INTERCOM_DIR.glob("*flag*.md")):
        try:
            content = f.read_text(encoding="utf-8")
            flags.append({
                "filename": f.name,
                "content": content
            })
        except Exception as e:
            flags.append({"filename": f.name, "error": str(e)})
    resp = jsonify(flags)
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@app.route("/api/intercom/send", methods=["POST"])
@governance_check("kb.file.create")
def api_intercom_send():
    """发送消息到intercom"""
    data = request.get_json(force=True)
    sender = data.get("sender", "unknown")
    content = data.get("content", "")
    if not content:
        return jsonify({"error": "content is required"}), 400

    # 自动编号
    if not INTERCOM_DIR.exists():
        INTERCOM_DIR.mkdir(parents=True, exist_ok=True)
    existing = list(INTERCOM_DIR.glob("msg_*.md"))
    next_num = len(existing) + 1
    filename = f"msg_{next_num:03d}_{sender}.md"
    filepath = INTERCOM_DIR / filename

    # 写入消息
    filepath.write_text(content, encoding="utf-8")

    # 审计日志 (JSON格式)
    audit_log("MSG_SENT", {
        "account": sender,
        "file_path": str(filepath),
        "detail": f"message sent via intercom",
        "ip": request.remote_addr,
        "status": "ok"
    })

    # 创建flag
    flag_name = f"_flag_for_nyx.md"
    flag_path = INTERCOM_DIR / flag_name
    flag_content = f"# 标记文件 - {sender}的信\n\n**发信方：** {sender}\n**消息编号：** {filename}\n**发送时间：** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n请读取 `{filename}`。\n\n读完请删除本标记文件。\n"
    flag_path.write_text(flag_content, encoding="utf-8")

    return jsonify({"status": "ok", "filename": filename}), 201


# ============== 治理架构 API ==============

# ============== 治理架构 API ==============

@app.route("/api/gov/circuit-breaker/status")
def api_circuit_breaker_status():
    """查看熔断器状态"""
    if not GOV_PARSER_AVAILABLE:
        return jsonify({"error": "治理解析器未加载", "available": False}), 503
    cb = get_circuit_breaker()
    return jsonify(cb.get_status())


@app.route("/api/gov/circuit-breaker/freeze", methods=["POST"])
def api_circuit_breaker_freeze():
    """手动触发熔断"""
    if not GOV_PARSER_AVAILABLE:
        return jsonify({"error": "治理解析器未加载", "available": False}), 503
    data = request.get_json(force=True, silent=True) or {}
    reason = data.get("reason", "手动触发")
    operator = data.get("operator", "unknown")
    cb = get_circuit_breaker()
    result = cb.freeze(reason, operator)
    status_code = 200 if result["status"] == "frozen" else 409
    return jsonify(result), status_code


@app.route("/api/gov/circuit-breaker/unfreeze", methods=["POST"])
def api_circuit_breaker_unfreeze():
    """解除熔断"""
    if not GOV_PARSER_AVAILABLE:
        return jsonify({"error": "治理解析器未加载", "available": False}), 503
    data = request.get_json(force=True, silent=True) or {}
    operator = data.get("operator", "unknown")
    confirmation = data.get("confirmation", "")
    cb = get_circuit_breaker()
    result = cb.unfreeze(operator, confirmation)
    status_code = 200 if result["status"] == "unfrozen" else 400
    return jsonify(result), status_code


@app.route("/api/gov/rules/list")
def api_gov_rules_list():
    """查看已加载全部治理规则"""
    if not GOV_PARSER_AVAILABLE:
        return jsonify({"error": "治理解析器未加载", "available": False}), 503
    
    try:
        loader = get_loader()
        parser = get_parser_core()
        
        rules = []
        for protocol_id, rule_obj in loader.rules.items():
            rules.append(rule_obj.to_dict())
        
        return jsonify({
            "available": True,
            "total_protocols": len(loader.rules),
            "total_rules": len(parser.rule_pool),
            "protocols": rules,
            "rule_pool_summary": parser.get_rule_pool_summary(),
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({"error": str(e), "available": False}), 500


@app.route("/api/gov/verify/event", methods=["POST"])
def api_gov_verify_event():
    """传入操作事件，返回合规/驳回结果"""
    if not GOV_PARSER_AVAILABLE:
        return jsonify({"error": "治理解析器未加载", "available": False}), 503
    
    try:
        event = request.get_json(force=True)
        
        if not event or "event_type" not in event:
            return jsonify({"error": "event_type is required"}), 400
        
        matcher = get_matcher()
        result = matcher.match_event(event)
        
        return jsonify({
            "available": True,
            "event_type": event.get("event_type"),
            "operator": event.get("operator", "unknown"),
            "allowed": result["allowed"],
            "reason": result["reason"],
            "matched_rules": result["matched_rules"],
            "violations": result["violations"],
            "actions": result["actions"],
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({"error": str(e), "available": False}), 500


@app.route("/api/gov/status")
def api_gov_status():
    """查看治理架构运行状态"""
    if not GOV_PARSER_AVAILABLE:
        return jsonify({
            "available": False,
            "error": "治理解析器未加载",
            "timestamp": datetime.now().isoformat()
        }), 503
    
    try:
        status = get_gov_status()
        return jsonify(status)
        
    except Exception as e:
        return jsonify({
            "available": True,
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500


@app.route("/api/gov/reload", methods=["POST"])
@governance_check("gov.proposal.create", path_field="")
def api_gov_reload():
    """重新加载治理协议（热加载）"""
    if not GOV_PARSER_AVAILABLE:
        return jsonify({"error": "治理解析器未加载", "available": False}), 503
    
    try:
        count = reload_gov_parser()
        
        return jsonify({
            "available": True,
            "status": "reloaded",
            "protocols_loaded": count,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({"error": str(e), "available": False}), 500



if __name__ == "__main__":
    print("=" * 60)
    print("  硅基文明数据库 Web UI")
    print("  Silicon Civilization KB - Web Interface")
    print("=" * 60)
    print()
    
    # 初始化治理解析器
    if GOV_PARSER_AVAILABLE:
        try:
            from gov_parser import init_gov_parser
            success = init_gov_parser()
            if success:
                print("[INFO] 治理架构已加载")
            else:
                print("[WARN] 治理架构加载失败")
        except Exception as e:
            print(f"[ERROR] 治理架构初始化失败: {e}", file=sys.stderr)
    
    print(f"  Knowledge Base: {BASE_DIR}")
    print(f"  Access URL:    http://localhost:5000")
    print(f"  API Stats:      http://localhost:5000/api/stats")
    print(f"  API Entries:    http://localhost:5000/api/entries")
    print(f"  API Integrity:  http://localhost:5000/api/integrity/check")
    print(f"  API Audit:      http://localhost:5000/api/audit/logs")
    print(f"  API Security:   http://localhost:5000/api/security/check-path")
    
    if GOV_PARSER_AVAILABLE:
        print(f"  API Gov Rules:  http://localhost:5000/api/gov/rules/list")
        print(f"  API Gov Status: http://localhost:5000/api/gov/status")
        print(f"  API Gov Verify: http://localhost:5000/api/gov/verify/event")
        print(f"  API Circuit Breaker: http://localhost:5000/api/gov/circuit-breaker/status")
    
    print()
    print("  Press Ctrl+C to stop")
    print("=" * 60)
    # use_reloader=False 避免重载器导致连接中断
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
