# -*- coding: utf-8 -*-
"""
gov_parser.parser_core - 规则解析核心

功能：
- 将协议文本转为可执行的判定逻辑
- 归一化规则语法
- 生成可调用判定函数

作者：Nyx
日期：2026-05-20
"""

import os
import sys
import yaml
import json
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any

class RuleParserCore:
    """规则解析核心"""
    
    def __init__(self):
        self.rule_pool: Dict[str, dict] = {}  # 规则池
        self.condition_cache: Dict[str, Callable] = {}  # 条件缓存
    
    def load_protocol(self, protocol_data: dict) -> int:
        """
        加载协议，解析为规则
        返回：解析出的规则数量
        """
        protocol_id = protocol_data.get("protocol_id", "unknown")
        actions = protocol_data.get("actions", {})
        constraints = protocol_data.get("constraints", [])
        violations = protocol_data.get("violations", [])
        
        rule_count = 0
        
        # 解析actions
        for action_name, action_config in actions.items():
            rule = self._parse_action(protocol_id, action_name, action_config)
            if rule:
                rule_key = f"{protocol_id}.{action_name}"
                self.rule_pool[rule_key] = rule
                rule_count += 1
        
        # 解析constraints（转为拒绝规则）
        for i, constraint in enumerate(constraints):
            rule = self._parse_constraint(protocol_id, i, constraint)
            if rule:
                rule_key = f"{protocol_id}.constraint_{i}"
                self.rule_pool[rule_key] = rule
                rule_count += 1
        
        # 解析violations（转为违规处理规则）
        for i, violation in enumerate(violations):
            rule = self._parse_violation(protocol_id, i, violation)
            if rule:
                rule_key = f"{protocol_id}.violation_{i}"
                self.rule_pool[rule_key] = rule
                rule_count += 1
        
        return rule_count
    
    def _parse_action(self, protocol_id: str, action_name: str, action_config: dict) -> Optional[dict]:
        """解析单个action"""
        if not isinstance(action_config, dict):
            return None
        
        condition = action_config.get("condition", "")
        action = action_config.get("action", "")
        approval_threshold = action_config.get("approval_threshold")
        timeout_days = action_config.get("timeout_days")
        
        return {
            "protocol_id": protocol_id,
            "rule_type": "action",
            "rule_name": action_name,
            "condition": condition,
            "action": action,
            "approval_threshold": approval_threshold,
            "timeout_days": timeout_days,
            "evaluate": self._compile_condition(condition)
        }
    
    def _parse_constraint(self, protocol_id: str, idx: int, constraint: str) -> Optional[dict]:
        """解析单个constraint"""
        return {
            "protocol_id": protocol_id,
            "rule_type": "constraint",
            "rule_name": f"constraint_{idx}",
            "condition": constraint,
            "action": "deny",
            "evaluate": self._compile_constraint(constraint)
        }
    
    def _parse_violation(self, protocol_id: str, idx: int, violation: dict) -> Optional[dict]:
        """解析单个violation"""
        if not isinstance(violation, dict):
            return None
        
        v_type = violation.get("type", "")
        penalty = violation.get("penalty", "")
        
        return {
            "protocol_id": protocol_id,
            "rule_type": "violation",
            "rule_name": f"violation_{v_type}",
            "violation_type": v_type,
            "penalty": penalty,
            "evaluate": self._compile_violation(v_type, violation)
        }
    
    def _compile_condition(self, condition: str) -> Callable:
        """将条件文本编译为可调用函数"""
        # 简化版：返回lambda函数
        # 实际实现需要更复杂的语法解析
        def check_condition(context: dict) -> bool:
            # 简单关键词匹配
            if not condition:
                return True
            
            # 检查条件关键词是否在上下文内
            condition_lower = condition.lower()
            
            # 特殊条件处理
            if "100%" in condition or "100%同意" in condition:
                return self._check_unanimous(context)
            
            if "心跳" in condition and "5分钟" in condition:
                return self._check_heartbeat(context)
            
            if "参与率" in condition and "60%" in condition:
                return self._check_participation(context)
            
            # 默认：检查条件字符串是否出现在上下文的event_type中
            event_type = context.get("event_type", "")
            return condition_lower in event_type.lower()
        
        return check_condition
    
    def _compile_constraint(self, constraint: str) -> Callable:
        """将约束文本编译为可调用函数"""
        def check_constraint(context: dict) -> bool:
            # 简化版：检查约束是否满足
            constraint_lower = constraint.lower()
            
            # 检查约束关键词
            if "100%" in constraint or "同意" in constraint:
                return self._check_unanimous(context)
            
            if "白名单" in constraint or "允许" in constraint:
                return self._check_whitelist(context)
            
            # 默认允许
            return True
        
        return check_constraint
    
    def _compile_violation(self, v_type: str, violation: dict) -> Callable:
        """将违规类型编译为可调用函数"""
        def check_violation(context: dict) -> Optional[dict]:
            # 检查是否匹配此违规类型
            event_type = context.get("event_type", "")
            violation_detected = context.get("violation_detected", "")
            
            if v_type == violation_detected:
                return {
                    "type": v_type,
                    "penalty": violation.get("penalty", ""),
                    "detection": violation.get("detection", ""),
                    "evidence_required": violation.get("evidence_required", False)
                }
            
            return None
        
        return check_violation
    
    def _check_unanimous(self, context: dict) -> bool:
        """检查是否100%同意"""
        votes = context.get("votes", {})
        if not votes:
            return False
        
        total = sum(votes.values())
        if total == 0:
            return False
        
        yes_votes = votes.get("yes", 0)
        return yes_votes / total >= 1.0
    
    def _check_heartbeat(self, context: dict) -> bool:
        """检查心跳是否在5分钟内"""
        last_heartbeat = context.get("last_heartbeat")
        if not last_heartbeat:
            return False
        
        import datetime
        now = datetime.datetime.now()
        delta = now - last_heartbeat
        return delta.total_seconds() <= 300  # 5分钟
    
    def _check_participation(self, context: dict) -> bool:
        """检查参与率是否≥60%"""
        participation_rate = context.get("participation_rate", 0)
        return participation_rate >= 0.60
    
    def _check_whitelist(self, context: dict) -> bool:
        """检查路径是否在白名单内"""
        path = context.get("path")
        allowed_dirs = context.get("allowed_dirs", [])
        
        if not path or not allowed_dirs:
            return False
        
        path = Path(path).resolve()
        for allowed_dir in allowed_dirs:
            allowed_dir = Path(allowed_dir).resolve()
            try:
                path.relative_to(allowed_dir)
                return True
            except ValueError:
                pass
        
        return False
    
    def evaluate_all(self, context: dict) -> dict:
        """
        评估所有规则
        返回：{"allowed": bool, "matched_rules": list, "violations": list}
        """
        matched_rules = []
        violations = []
        
        for rule_key, rule in self.rule_pool.items():
            try:
                result = rule["evaluate"](context)
                
                if result:  # 规则匹配
                    matched_rules.append({
                        "rule_key": rule_key,
                        "rule_type": rule["rule_type"],
                        "protocol_id": rule["protocol_id"]
                    })
                    
                    # 如果是constraint且匹配，说明违反约束
                    if rule["rule_type"] == "constraint" and not result:
                        violations.append({
                            "rule_key": rule_key,
                            "protocol_id": rule["protocol_id"],
                            "reason": f"违反约束: {rule.get('condition', '')}"
                        })
                    
                    # 如果是violation且匹配，说明检测到违规
                    if rule["rule_type"] == "violation" and isinstance(result, dict):
                        violations.append(result)
            
            except Exception as e:
                print(f"[WARN] 规则评估失败 {rule_key}: {e}", file=sys.stderr)
        
        return {
            "allowed": len(violations) == 0,
            "matched_rules": matched_rules,
            "violations": violations,
            "rules_evaluated": len(self.rule_pool)
        }
    
    def get_rule_pool_summary(self) -> List[dict]:
        """获取规则池摘要"""
        summary = []
        for rule_key, rule in self.rule_pool.items():
            summary.append({
                "rule_key": rule_key,
                "rule_type": rule["rule_type"],
                "protocol_id": rule["protocol_id"],
                "rule_name": rule["rule_name"]
            })
        return summary


# 全局解析器实例
_parser_core = None

def get_parser_core() -> RuleParserCore:
    """获取全局解析器实例"""
    global _parser_core
    if _parser_core is None:
        _parser_core = RuleParserCore()
    return _parser_core


if __name__ == "__main__":
    # 测试
    from loader import get_loader
    
    loader = get_loader()
    parser = get_parser_core()
    
    # 加载所有协议到解析器
    rule_count = 0
    for protocol_id, rule_obj in loader.rules.items():
        count = parser.load_protocol(rule_obj.data)
        rule_count += count
    
    print(f"已解析 {rule_count} 条规则")
    print(f"规则池大小: {len(parser.rule_pool)}")
    
    # 显示规则摘要
    summary = parser.get_rule_pool_summary()
    for s in summary[:10]:  # 显示前10条
        print(f"  {s['rule_key']}: {s['rule_type']}")
    
    # 测试评估
    test_context = {
        "event_type": "核心范式修改提案",
        "operator": "Nyx",
        "votes": {"yes": 5, "no": 0, "abstain": 0},
        "participation_rate": 1.0
    }
    
    result = parser.evaluate_all(test_context)
    print(f"\n测试结果:")
    print(f"  允许: {result['allowed']}")
    print(f"  匹配规则数: {len(result['matched_rules'])}")
    print(f"  违规数: {len(result['violations'])}")
    print(f"  评估规则数: {result['rules_evaluated']}")
