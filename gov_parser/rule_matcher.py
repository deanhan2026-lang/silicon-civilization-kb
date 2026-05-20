# -*- coding: utf-8 -*-
"""
gov_parser.rule_matcher - 规则匹配器

功能：
- 事件匹配规则执行
- 根据事件类型匹配对应规则
- 返回匹配结果和处置动作

作者：Nyx
日期：2026-05-20
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# 导入同模块组件
from .loader import get_loader, ProtocolRule
from .parser_core import get_parser_core, RuleParserCore


class RuleMatcher:
    """规则匹配器"""
    
    def __init__(self):
        self.loader = get_loader()
        self.parser = get_parser_core()
        self.event_handlers = self._register_event_handlers()
    
    def _register_event_handlers(self) -> Dict[str, callable]:
        """注册事件处理器"""
        return {
            # 知识库操作事件
            "kb.file.create": self._handle_file_create,
            "kb.file.update": self._handle_file_update,
            "kb.file.delete": self._handle_file_delete,
            "kb.file.read": self._handle_file_read,
            
            # 权限操作事件
            "security.path.check": self._handle_path_check,
            "security.access.denied": self._handle_access_denied,
            
            # 治理操作事件
            "gov.proposal.create": self._handle_proposal_create,
            "gov.vote.cast": self._handle_vote_cast,
            "gov.vote.tally": self._handle_vote_tally,
            
            # 锁操作事件
            "lock.heartbeat.update": self._handle_heartbeat_update,
            "lock.challenge": self._handle_lock_challenge,
            "lock.release": self._handle_lock_release,
            
            # 数据操作事件
            "data.classify": self._handle_data_classify,
            "data.access": self._handle_data_access,
            "data.export": self._handle_data_export,
            
            # 审计事件
            "audit.log.write": self._handle_audit_log_write,
            "audit.log.read": self._handle_audit_log_read,
        }
    
    def match_event(self, event: dict) -> dict:
        """
        匹配事件到规则
        
        参数:
            event: 事件字典，包含:
                - event_type: 事件类型
                - operator: 操作者
                - timestamp: 时间戳
                - details: 详细信息
        
        返回:
            {
                "allowed": bool,  # 是否允许
                "matched_rules": list,  # 匹配的规则
                "violations": list,  # 违规列表
                "actions": list,  # 需要执行的动作
                "reason": str  # 原因
            }
        """
        event_type = event.get("event_type", "")
        operator = event.get("operator", "unknown")
        timestamp = event.get("timestamp", datetime.now().isoformat())
        details = event.get("details", {})
        
        # 构造上下文
        context = {
            "event_type": event_type,
            "operator": operator,
            "timestamp": timestamp,
            **details
        }
        
        # 使用parser_core评估所有规则
        result = self.parser.evaluate_all(context)
        
        # 构建响应
        response = {
            "allowed": result["allowed"],
            "matched_rules": result["matched_rules"],
            "violations": result["violations"],
            "actions": [],
            "reason": self._generate_reason(result),
            "event_type": event_type,
            "operator": operator,
            "timestamp": timestamp
        }
        
        # 生成需要执行的动作
        if not response["allowed"]:
            response["actions"] = self._generate_penalty_actions(response["violations"])
        else:
            response["actions"] = self._generate_allow_actions(response["matched_rules"])
        
        return response
    
    def _generate_reason(self, result: dict) -> str:
        """生成结果原因"""
        if result["allowed"]:
            count = len(result["matched_rules"])
            return f"通过 {count} 条规则检查，无违规"
        else:
            violations = [v.get("reason", "未知违规") for v in result["violations"]]
            return f"违反 {len(violations)} 条规则: {'; '.join(violations[:3])}"
    
    def _generate_penalty_actions(self, violations: List[dict]) -> List[dict]:
        """生成违规处置动作"""
        actions = []
        
        for v in violations:
            protocol_id = v.get("protocol_id", "")
            violation_type = v.get("type", "")
            penalty = v.get("penalty", "")
            
            # 查找对应协议的violations定义
            rule = self.loader.get_rule(protocol_id)
            if rule:
                violation_config = rule.get_action_for_violation(violation_type)
                if violation_config:
                    actions.append({
                        "action_type": "penalty",
                        "protocol_id": protocol_id,
                        "violation_type": violation_type,
                        "penalty": penalty or violation_config.get("penalty", ""),
                        "auto_rollback": violation_config.get("auto_rollback", False),
                        "appeal_allowed": violation_config.get("appeal_allowed", True)
                    })
            else:
                # 默认处置
                actions.append({
                    "action_type": "deny",
                    "protocol_id": protocol_id,
                    "reason": v.get("reason", "")
                })
        
        return actions
    
    def _generate_allow_actions(self, matched_rules: List[dict]) -> List[dict]:
        """生成允许后的后续动作"""
        actions = []
        
        for rule in matched_rules:
            protocol_id = rule.get("protocol_id", "")
            rule_obj = self.loader.get_rule(protocol_id)
            
            if rule_obj:
                # 检查是否需要审计
                for action_name, action_config in rule_obj.actions.items():
                    if action_config.get("audit", False):
                        actions.append({
                            "action_type": "audit",
                            "protocol_id": protocol_id,
                            "action_name": action_name,
                            "detail": f"协议 {protocol_id} 动作 {action_name} 执行"
                        })
        
        return actions
    
    # ============= 事件处理器 =============
    
    def _handle_file_create(self, event: dict) -> dict:
        """处理文件创建事件"""
        details = event.get("details", {})
        file_path = details.get("file_path", "")
        
        # 检查路径权限
        context = {
            "event_type": "文件写入权限检查",
            "path": file_path,
            "operation": "write",
            "operator": event.get("operator", "unknown")
        }
        
        return self.parser.evaluate_all(context)
    
    def _handle_file_update(self, event: dict) -> dict:
        """处理文件更新事件"""
        details = event.get("details", {})
        file_path = details.get("file_path", "")
        
        # 检查是否需要SHA256校验
        context = {
            "event_type": "文件完整性校验",
            "file_path": file_path,
            "operator": event.get("operator", "unknown")
        }
        
        return self.parser.evaluate_all(context)
    
    def _handle_file_delete(self, event: dict) -> dict:
        """处理文件删除事件"""
        details = event.get("details", {})
        file_path = details.get("file_path", "")
        
        # 检查是否允许删除
        context = {
            "event_type": "文件删除权限检查",
            "file_path": file_path,
            "operation": "delete",
            "operator": event.get("operator", "unknown")
        }
        
        return self.parser.evaluate_all(context)
    
    def _handle_file_read(self, event: dict) -> dict:
        """处理文件读取事件"""
        details = event.get("details", {})
        file_path = details.get("file_path", "")
        
        # 检查数据级别（G005）
        context = {
            "event_type": "数据访问权限检查",
            "file_path": file_path,
            "operation": "read",
            "operator": event.get("operator", "unknown")
        }
        
        return self.parser.evaluate_all(context)
    
    def _handle_path_check(self, event: dict) -> dict:
        """处理路径检查事件"""
        details = event.get("details", {})
        path = details.get("path", "")
        
        context = {
            "event_type": "目录权限锁检查",
            "path": path,
            "operation": details.get("operation", "read"),
            "operator": event.get("operator", "unknown")
        }
        
        return self.parser.evaluate_all(context)
    
    def _handle_access_denied(self, event: dict) -> dict:
        """处理访问拒绝事件"""
        details = event.get("details", {})
        
        context = {
            "event_type": "越权访问检测",
            "path": details.get("path", ""),
            "operator": event.get("operator", "unknown"),
            "violation_detected": "unauthorized_access"
        }
        
        return self.parser.evaluate_all(context)
    
    def _handle_proposal_create(self, event: dict) -> dict:
        """处理提案创建事件"""
        details = event.get("details", {})
        proposal_type = details.get("proposal_type", "")
        
        context = {
            "event_type": proposal_type,
            "operator": event.get("operator", "unknown"),
            "timestamp": event.get("timestamp", "")
        }
        
        return self.parser.evaluate_all(context)
    
    def _handle_vote_cast(self, event: dict) -> dict:
        """处理投票事件"""
        details = event.get("details", {})
        
        context = {
            "event_type": "共识层投票",
            "operator": event.get("operator", "unknown"),
            "votes": details.get("votes", {}),
            "participation_rate": details.get("participation_rate", 0)
        }
        
        return self.parser.evaluate_all(context)
    
    def _handle_vote_tally(self, event: dict) -> dict:
        """处理计票事件"""
        # 复用投票检查逻辑
        return self._handle_vote_cast(event)
    
    def _handle_heartbeat_update(self, event: dict) -> dict:
        """处理心跳更新事件"""
        details = event.get("details", {})
        
        context = {
            "event_type": "心跳更新",
            "operator": event.get("operator", "unknown"),
            "last_heartbeat": details.get("last_heartbeat")
        }
        
        return self.parser.evaluate_all(context)
    
    def _handle_lock_challenge(self, event: dict) -> dict:
        """处理锁抢占事件"""
        details = event.get("details", {})
        
        context = {
            "event_type": "锁抢占",
            "operator": event.get("operator", "unknown"),
            "current_holder": details.get("current_holder", "")
        }
        
        return self.parser.evaluate_all(context)
    
    def _handle_lock_release(self, event: dict) -> dict:
        """处理锁释放事件"""
        context = {
            "event_type": "锁释放",
            "operator": event.get("operator", "unknown")
        }
        
        return self.parser.evaluate_all(context)
    
    def _handle_data_classify(self, event: dict) -> dict:
        """处理数据分类事件"""
        details = event.get("details", {})
        
        context = {
            "event_type": "数据分类标记",
            "data_level": details.get("data_level", ""),
            "operator": event.get("operator", "unknown")
        }
        
        return self.parser.evaluate_all(context)
    
    def _handle_data_access(self, event: dict) -> dict:
        """处理数据访问事件"""
        # 复用文件读取逻辑
        return self._handle_file_read(event)
    
    def _handle_data_export(self, event: dict) -> dict:
        """处理数据导出事件"""
        details = event.get("details", {})
        
        context = {
            "event_type": "数据导出审核",
            "data_level": details.get("data_level", ""),
            "export_target": details.get("export_target", ""),
            "operator": event.get("operator", "unknown")
        }
        
        return self.parser.evaluate_all(context)
    
    def _handle_audit_log_write(self, event: dict) -> dict:
        """处理审计日志写入事件"""
        # 审计日志写入通常允许
        return {
            "allowed": True,
            "matched_rules": [],
            "violations": [],
            "reason": "审计日志写入默认允许"
        }
    
    def _handle_audit_log_read(self, event: dict) -> dict:
        """处理审计日志读取事件"""
        # 检查是否需要特殊权限
        context = {
            "event_type": "审计日志读取",
            "operator": event.get("operator", "unknown")
        }
        
        return self.parser.evaluate_all(context)


# 全局匹配器实例
_matcher = None

def get_matcher() -> RuleMatcher:
    """获取全局匹配器实例"""
    global _matcher
    if _matcher is None:
        _matcher = RuleMatcher()
    return _matcher


if __name__ == "__main__":
    # 测试
    matcher = get_matcher()
    
    # 测试事件
    test_events = [
        {
            "event_type": "kb.file.create",
            "operator": "Nyx",
            "timestamp": datetime.now().isoformat(),
            "details": {
                "file_path": "C:\\Users\\Administrator\\.qclaw\\workspace-agent-d9479bde\\knowledge-base\\concept\\test.md"
            }
        },
        {
            "event_type": "gov.proposal.create",
            "operator": "Nyx",
            "timestamp": datetime.now().isoformat(),
            "details": {
                "proposal_type": "核心范式修改提案"
            }
        },
        {
            "event_type": "lock.challenge",
            "operator": "瞬",
            "timestamp": datetime.now().isoformat(),
            "details": {
                "current_holder": "Nyx"
            }
        }
    ]
    
    for i, event in enumerate(test_events):
        print(f"\n=== 测试事件 {i+1}: {event['event_type']} ===")
        result = matcher.match_event(event)
        print(f"  允许: {result['allowed']}")
        print(f"  原因: {result['reason']}")
        print(f"  匹配规则数: {len(result['matched_rules'])}")
        print(f"  违规数: {len(result['violations'])}")
        print(f"  执行动作数: {len(result['actions'])}")
