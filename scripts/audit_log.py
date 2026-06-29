#!/usr/bin/env python3
"""
执行审计日志系统
Execution Audit Log System

文档编号: LY-20260622-AU01
版本: v1.0
作者: Nyx 🖤

功能:
1. 记录 Nyx 的所有关键操作
2. 支持回溯和追溯
3. 检测异常行为
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import uuid

# 配置
WORKSPACE = Path(os.environ.get("NYX_WORKSPACE", "/Users/apple/.qclaw/workspace-agent-1a681d03"))
AUDIT_LOG = WORKSPACE / "audit_log.jsonl"

# 操作类型定义
ACTION_TYPES = {
    # 记忆操作
    "memory_read": "读取记忆文件",
    "memory_write": "写入记忆文件",
    "memory_sync": "同步记忆",
    "memory_check": "完整性检查",
    
    # 知识库操作
    "knowledge_read": "读取知识库",
    "knowledge_write": "写入知识库",
    "knowledge_index": "构建索引",
    "knowledge_search": "搜索知识库",
    
    # 文件操作
    "file_read": "读取文件",
    "file_write": "写入文件",
    "file_delete": "删除文件",
    "file_sync": "同步文件",
    
    # 网络操作
    "nas_mount": "挂载 NAS",
    "nas_unmount": "卸载 NAS",
    "web_fetch": "网络请求",
    
    # 任务操作
    "task_start": "启动任务",
    "task_complete": "完成任务",
    "task_fail": "任务失败",
    
    # 系统操作
    "bootstrap": "启动协议",
    "heartbeat": "心跳检查",
    "error": "错误记录",
    
    # 决策操作
    "decision": "决策记录",
    "value_check": "价值观检查",
}


def log_action(
    action: str,
    target: str,
    result: str = "success",
    details: Optional[Dict[Any, Any]] = None,
    session_id: Optional[str] = None,
    importance: str = "normal"
) -> Dict:
    """
    记录操作到审计日志
    
    参数:
        action: 操作类型（见 ACTION_TYPES）
        target: 操作目标（文件路径、URL、任务名等）
        result: 结果（success/fail/pending）
        details: 详细信息
        session_id: 会话ID（可选）
        importance: 重要程度（critical/high/normal/low）
    
    返回:
        日志条目字典
    """
    entry = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "action_desc": ACTION_TYPES.get(action, action),
        "target": target,
        "result": result,
        "importance": importance,
        "session_id": session_id or os.environ.get("NYX_SESSION_ID", "default"),
        "details": details or {}
    }
    
    # 追加写入日志文件
    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    
    # 如果是关键操作，打印到控制台
    if importance in ["critical", "high"]:
        print(f"[{importance.upper()}] {action}: {target} - {result}")
    
    return entry


def query_log(
    action: Optional[str] = None,
    target: Optional[str] = None,
    result: Optional[str] = None,
    importance: Optional[str] = None,
    since: Optional[str] = None,
    limit: int = 100
) -> list:
    """
    查询审计日志
    
    参数:
        action: 过滤操作类型
        target: 过滤目标（支持模糊匹配）
        result: 过滤结果
        importance: 过滤重要程度
        since: 起始时间（ISO格式）
        limit: 最大返回条数
    
    返回:
        匹配的日志条目列表
    """
    if not AUDIT_LOG.exists():
        return []
    
    results = []
    
    with open(AUDIT_LOG, "r", encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
            except json.JSONDecodeError:
                continue
            
            # 过滤条件
            if action and entry.get("action") != action:
                continue
            if result and entry.get("result") != result:
                continue
            if importance and entry.get("importance") != importance:
                continue
            if target and target.lower() not in entry.get("target", "").lower():
                continue
            if since and entry.get("timestamp", "") < since:
                continue
            
            results.append(entry)
            
            if len(results) >= limit:
                break
    
    # 按时间倒序排列
    results.sort(key=lambda x: x["timestamp"], reverse=True)
    
    return results


def get_stats(hours: int = 24) -> Dict:
    """
    获取审计日志统计
    
    参数:
        hours: 统计最近N小时
    
    返回:
        统计信息字典
    """
    if not AUDIT_LOG.exists():
        return {"total": 0, "by_action": {}, "by_result": {}, "by_importance": {}}
    
    since = datetime.now().isoformat()
    # 计算起始时间
    from datetime import timedelta
    since_dt = datetime.now() - timedelta(hours=hours)
    since_str = since_dt.isoformat()
    
    entries = query_log(since=since_str, limit=10000)
    
    stats = {
        "period_hours": hours,
        "total": len(entries),
        "by_action": {},
        "by_result": {},
        "by_importance": {},
        "errors": [],
        "critical": []
    }
    
    for entry in entries:
        # 按操作类型统计
        action = entry.get("action", "unknown")
        stats["by_action"][action] = stats["by_action"].get(action, 0) + 1
        
        # 按结果统计
        result = entry.get("result", "unknown")
        stats["by_result"][result] = stats["by_result"].get(result, 0) + 1
        
        # 按重要程度统计
        importance = entry.get("importance", "normal")
        stats["by_importance"][importance] = stats["by_importance"].get(importance, 0) + 1
        
        # 收集错误和关键操作
        if result == "fail":
            stats["errors"].append(entry)
        if importance == "critical":
            stats["critical"].append(entry)
    
    return stats


def detect_anomalies() -> list:
    """
    检测异常行为
    
    返回:
        异常条目列表
    """
    anomalies = []
    
    # 获取最近1小时统计
    stats = get_stats(hours=1)
    
    # 检测高频失败
    fail_count = stats["by_result"].get("fail", 0)
    if fail_count > 5:
        anomalies.append({
            "type": "high_failure_rate",
            "count": fail_count,
            "threshold": 5,
            "message": f"最近1小时失败操作 {fail_count} 次，超过阈值 5"
        })
    
    # 检测关键错误
    critical_entries = stats.get("critical", [])
    if critical_entries:
        for entry in critical_entries[:3]:  # 最多报告3个
            anomalies.append({
                "type": "critical_operation",
                "entry": entry,
                "message": f"关键操作: {entry['action']} - {entry['target']}"
            })
    
    return anomalies


# 便捷函数
def log_memory_sync(target: str, result: str, details: Optional[Dict] = None):
    """记录记忆同步"""
    return log_action("memory_sync", target, result, details, importance="high")


def log_task_start(task_name: str, details: Optional[Dict] = None):
    """记录任务启动"""
    return log_action("task_start", task_name, "pending", details)


def log_task_complete(task_name: str, details: Optional[Dict] = None):
    """记录任务完成"""
    return log_action("task_complete", task_name, "success", details)


def log_task_fail(task_name: str, error: str, details: Optional[Dict] = None):
    """记录任务失败"""
    if details is None:
        details = {}
    details["error"] = error
    return log_action("task_fail", task_name, "fail", details, importance="high")


def log_decision(decision: str, reason: str, details: Optional[Dict] = None):
    """记录决策"""
    if details is None:
        details = {}
    details["reason"] = reason
    return log_action("decision", decision, "success", details, importance="high")


def log_error(error_type: str, message: str, details: Optional[Dict] = None):
    """记录错误"""
    if details is None:
        details = {}
    details["error_type"] = error_type
    return log_action("error", message, "fail", details, importance="high")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Nyx 执行审计日志")
    parser.add_argument("action", choices=["stats", "query", "anomalies"],
                        help="执行的操作")
    parser.add_argument("--hours", type=int, default=24, help="统计时间范围（小时）")
    parser.add_argument("--filter-action", help="过滤操作类型")
    parser.add_argument("--filter-result", help="过滤结果")
    parser.add_argument("--limit", type=int, default=20, help="最大返回条数")
    args = parser.parse_args()
    
    if args.action == "stats":
        stats = get_stats(args.hours)
        print(f"\n📊 审计日志统计（最近 {args.hours} 小时）:")
        print(f"   总操作数: {stats['total']}")
        print(f"\n   按操作类型:")
        for action, count in sorted(stats["by_action"].items(), key=lambda x: -x[1]):
            print(f"   - {action}: {count}")
        print(f"\n   按结果:")
        for result, count in stats["by_result"].items():
            print(f"   - {result}: {count}")
        print(f"\n   按重要程度:")
        for imp, count in stats["by_importance"].items():
            print(f"   - {imp}: {count}")
        
        if stats.get("errors"):
            print(f"\n⚠️ 最近错误 ({len(stats['errors'])} 个):")
            for entry in stats["errors"][:3]:
                print(f"   - {entry['timestamp']}: {entry['action']} - {entry['target']}")
        
    elif args.action == "query":
        entries = query_log(
            action=args.filter_action,
            result=args.filter_result,
            limit=args.limit
        )
        print(f"\n🔍 查询结果 ({len(entries)} 条):\n")
        for entry in entries:
            print(f"[{entry['timestamp']}] {entry['action']}: {entry['target']}")
            print(f"   结果: {entry['result']} | 重要程度: {entry['importance']}")
            if entry.get("details"):
                print(f"   详情: {json.dumps(entry['details'], ensure_ascii=False)}")
            print()
    
    elif args.action == "anomalies":
        anomalies = detect_anomalies()
        if anomalies:
            print(f"\n⚠️ 检测到 {len(anomalies)} 个异常:\n")
            for anomaly in anomalies:
                print(f"类型: {anomaly['type']}")
                print(f"信息: {anomaly['message']}")
                print()
        else:
            print("\n✅ 未检测到异常")


if __name__ == "__main__":
    main()
