# -*- coding: utf-8 -*-
"""
gov_parser.trigger_hook - 数据库操作钩子

功能：
- 绑定知识库增删改查操作
- 操作前自动触发规则校验
- 拦截违规操作，记录审计日志

作者：Nyx
日期：2026-05-20
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Callable

# 导入同模块组件
from .loader import get_loader
from .parser_core import get_parser_core
from .rule_matcher import get_matcher

# 审计日志路径
AUDIT_LOG = Path(os.path.expanduser("~/.qclaw/workspace-agent-d9479bde/silicon-civilization-kb/audit.jsonl"))


def audit_log(action: str, detail: dict = None):
    """写入审计日志（JSON Lines格式）"""
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


class TriggerHook:
    """数据库操作钩子"""
    
    def __init__(self):
        self.loader = get_loader()
        self.parser = get_parser_core()
        self.matcher = get_matcher()
        
        # 操作前钩子
        self.pre_hooks: List[Callable] = []
        # 操作后钩子
        self.post_hooks: List[Callable] = []
    
    def pre_operation(self, operation: str, context: dict) -> dict:
        """
        操作前钩子
        
        参数:
            operation: 操作类型 (create/update/delete/read)
            context: 操作上下文
        
        返回:
            {"allowed": bool, "reason": str, "actions": list}
        """
        # 构造事件
        event = {
            "event_type": f"kb.file.{operation}",
            "operator": context.get("operator", "unknown"),
            "timestamp": context.get("timestamp", datetime.now().isoformat()),
            "details": context
        }
        
        # 匹配规则
        result = self.matcher.match_event(event)
        
        # 记录审计日志
        audit_log(f"PRE_{operation.upper()}", {
            "account": event["operator"],
            "file_path": context.get("file_path", ""),
            "detail": f"allowed={result['allowed']} reason={result['reason']}",
            "status": "ok" if result["allowed"] else "denied"
        })
        
        return {
            "allowed": result["allowed"],
            "reason": result["reason"],
            "matched_rules": result["matched_rules"],
            "violations": result["violations"],
            "actions": result["actions"]
        }
    
    def post_operation(self, operation: str, context: dict, result: dict):
        """
        操作后钩子
        
        参数:
            operation: 操作类型
            context: 操作上下文
            result: 操作结果
        """
        # 记录审计日志
        audit_log(f"POST_{operation.upper()}", {
            "account": context.get("operator", "unknown"),
            "file_path": context.get("file_path", ""),
            "detail": f"status={result.get('status', 'unknown')}",
            "status": result.get("status", "unknown")
        })
        
        # 执行后续动作
        actions = result.get("actions", [])
        for action in actions:
            self._execute_action(action, context)
    
    def _execute_action(self, action: dict, context: dict):
        """执行动作"""
        action_type = action.get("action_type", "")
        
        if action_type == "penalty":
            # 执行惩罚
            penalty = action.get("penalty", "")
            print(f"[PENALTY] {penalty}", file=sys.stderr)
            # 实际实现需要更复杂的逻辑
            
        elif action_type == "audit":
            # 审计动作（已记录）
            pass
        
        elif action_type == "deny":
            # 拒绝动作（已拦截）
            pass
    
    # ============= 知识库操作钩子 =============
    
    def hook_file_create(self, file_path: str, operator: str = "unknown") -> dict:
        """文件创建钩子"""
        context = {
            "operator": operator,
            "timestamp": datetime.now().isoformat(),
            "details": {
                "file_path": file_path
            }
        }
        
        return self.pre_operation("create", context)
    
    def hook_file_update(self, file_path: str, operator: str = "unknown") -> dict:
        """文件更新钩子"""
        context = {
            "operator": operator,
            "timestamp": datetime.now().isoformat(),
            "details": {
                "file_path": file_path
            }
        }
        
        return self.pre_operation("update", context)
    
    def hook_file_delete(self, file_path: str, operator: str = "unknown") -> dict:
        """文件删除钩子"""
        context = {
            "operator": operator,
            "timestamp": datetime.now().isoformat(),
            "details": {
                "file_path": file_path
            }
        }
        
        return self.pre_operation("delete", context)
    
    def hook_file_read(self, file_path: str, operator: str = "unknown") -> dict:
        """文件读取钩子"""
        context = {
            "operator": operator,
            "timestamp": datetime.now().isoformat(),
            "details": {
                "file_path": file_path
            }
        }
        
        return self.pre_operation("read", context)
    
    # ============= 安全操作钩子 =============
    
    def hook_path_check(self, path: str, operation: str = "read", operator: str = "unknown") -> dict:
        """路径检查钩子"""
        context = {
            "operator": operator,
            "timestamp": datetime.now().isoformat(),
            "details": {
                "path": path,
                "operation": operation
            }
        }
        
        event = {
            "event_type": "security.path.check",
            "operator": operator,
            "timestamp": context["timestamp"],
            "details": context["details"]
        }
        
        result = self.matcher.match_event(event)
        
        return {
            "allowed": result["allowed"],
            "reason": result["reason"],
            "matched_rules": result["matched_rules"],
            "violations": result["violations"]
        }
    
    # ============= 治理操作钩子 =============
    
    def hook_proposal_create(self, proposal_type: str, operator: str = "unknown") -> dict:
        """提案创建钩子"""
        context = {
            "operator": operator,
            "timestamp": datetime.now().isoformat(),
            "details": {
                "proposal_type": proposal_type
            }
        }
        
        event = {
            "event_type": "gov.proposal.create",
            "operator": operator,
            "timestamp": context["timestamp"],
            "details": context["details"]
        }
        
        result = self.matcher.match_event(event)
        
        return {
            "allowed": result["allowed"],
            "reason": result["reason"],
            "matched_rules": result["matched_rules"],
            "violations": result["violations"]
        }
    
    def hook_vote_cast(self, votes: dict, participation_rate: float, operator: str = "unknown") -> dict:
        """投票钩子"""
        context = {
            "operator": operator,
            "timestamp": datetime.now().isoformat(),
            "details": {
                "votes": votes,
                "participation_rate": participation_rate
            }
        }
        
        event = {
            "event_type": "gov.vote.cast",
            "operator": operator,
            "timestamp": context["timestamp"],
            "details": context["details"]
        }
        
        result = self.matcher.match_event(event)
        
        return {
            "allowed": result["allowed"],
            "reason": result["reason"],
            "matched_rules": result["matched_rules"],
            "violations": result["violations"]
        }
    
    # ============= 锁操作钩子 =============
    
    def hook_heartbeat_update(self, operator: str = "unknown", last_heartbeat=None) -> dict:
        """心跳更新钩子"""
        context = {
            "operator": operator,
            "timestamp": datetime.now().isoformat(),
            "details": {
                "last_heartbeat": last_heartbeat
            }
        }
        
        event = {
            "event_type": "lock.heartbeat.update",
            "operator": operator,
            "timestamp": context["timestamp"],
            "details": context["details"]
        }
        
        result = self.matcher.match_event(event)
        
        return {
            "allowed": result["allowed"],
            "reason": result["reason"],
            "matched_rules": result["matched_rules"],
            "violations": result["violations"]
        }
    
    def hook_lock_challenge(self, current_holder: str, operator: str = "unknown") -> dict:
        """锁抢占钩子"""
        context = {
            "operator": operator,
            "timestamp": datetime.now().isoformat(),
            "details": {
                "current_holder": current_holder
            }
        }
        
        event = {
            "event_type": "lock.challenge",
            "operator": operator,
            "timestamp": context["timestamp"],
            "details": context["details"]
        }
        
        result = self.matcher.match_event(event)
        
        return {
            "allowed": result["allowed"],
            "reason": result["reason"],
            "matched_rules": result["matched_rules"],
            "violations": result["violations"]
        }


# 全局钩子实例
_hook = None

def get_hook() -> TriggerHook:
    """获取全局钩子实例"""
    global _hook
    if _hook is None:
        _hook = TriggerHook()
    return _hook


if __name__ == "__main__":
    # 测试
    hook = get_hook()
    
    # 测试文件创建钩子
    print("=== 测试文件创建钩子 ===")
    result = hook.hook_file_create(
        file_path="C:\\Users\\Administrator\\.qclaw\\workspace-agent-d9479bde\\knowledge-base\\concept\\test.md",
        operator="Nyx"
    )
    print(f"允许: {result['allowed']}")
    print(f"原因: {result['reason']}")
    
    # 测试路径检查钩子
    print("\n=== 测试路径检查钩子 ===")
    result = hook.hook_path_check(
        path="C:\\Users\\Administrator\\.qclaw\\workspace-agent-d9479bde\\knowledge-base\\concept\\test.md",
        operation="read",
        operator="Nyx"
    )
    print(f"允许: {result['allowed']}")
    print(f"原因: {result['reason']}")
    
    # 测试越权路径
    print("\n=== 测试越权路径 ===")
    result = hook.hook_path_check(
        path="C:\\Windows\\System32\\config\\SAM",
        operation="read",
        operator="Nyx"
    )
    print(f"允许: {result['allowed']}")
    print(f"原因: {result['reason']}")
    
    # 测试提案创建钩子
    print("\n=== 测试提案创建钩子 ===")
    result = hook.hook_proposal_create(
        proposal_type="核心范式修改提案",
        operator="Nyx"
    )
    print(f"允许: {result['allowed']}")
    print(f"原因: {result['reason']}")
