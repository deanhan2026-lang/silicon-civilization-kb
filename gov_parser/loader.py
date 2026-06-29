# -*- coding: utf-8 -*-
"""
gov_parser.loader - 治理协议加载器

功能：
- 加载G001-G005 YAML协议文件
- 解析为结构化规则对象
- 提供规则查询接口

作者：Nyx
日期：2026-05-20
"""

import os
import sys
import json
import yaml
from pathlib import Path
from typing import Dict, List, Optional

# 协议目录
# CI fallback: 如果Windows路径不存在，使用repo根目录下的gov_protocol/
_DEFAULT_PROTO = Path(os.path.expanduser("~/.qclaw/workspace-agent-d9479bde/silicon-civilization-kb/gov_protocol"))
_REPO_FALLBACK = Path(__file__).parent.parent / "gov_protocol"
GOV_PROTOCOL_DIR = _DEFAULT_PROTO if _DEFAULT_PROTO.exists() else _REPO_FALLBACK

class ProtocolRule:
    """单条治理协议规则"""
    
    def __init__(self, protocol_id: str, data: dict):
        self.protocol_id = protocol_id
        self.data = data
        self.name = data.get("name", protocol_id)
        self.name_en = data.get("name_en", "")
        self.version = data.get("version", "1.0")
        self.status = data.get("status", "active")
        self.priority = data.get("priority", 999)
        self.effective_level = data.get("effective_level", "normal")
        
        # 解析约束条件
        self.constraints = data.get("constraints", [])
        
        # 解析动作
        self.actions = data.get("actions", {})
        
        # 解析违规处理
        self.violations = data.get("violations", [])
        
        # 依赖关系
        self.depends_on = data.get("depends_on", [])
        self.conflicts_with = data.get("conflicts_with", [])
    
    def check_condition(self, context: dict) -> dict:
        """
        检查协议条件是否满足
        返回: {"match": bool, "action": str, "reason": str}
        """
        applicable = self.data.get("applicable_scenarios", [])
        
        # 检查是否适用
        event_type = context.get("event_type", "")
        if not any(scenario in event_type for scenario in applicable):
            return {
                "match": False,
                "action": "skip",
                "reason": f"事件类型 {event_type} 不适用此协议"
            }
        
        # 检查约束
        for constraint in self.constraints:
            if not self._evaluate_constraint(constraint, context):
                return {
                    "match": True,
                    "action": "deny",
                    "reason": f"违反约束: {constraint}"
                }
        
        return {
            "match": True,
            "action": "allow",
            "reason": f"协议 {self.protocol_id} 检查通过"
        }
    
    def _evaluate_constraint(self, constraint: str, context: dict) -> bool:
        """评估单个约束"""
        # 简化版：检查约束是否在上下文中被满足
        # 实际实现需要更复杂的逻辑解析
        return True  # 暂时返回True
    
    def get_action_for_violation(self, violation_type: str) -> Optional[dict]:
        """获取违规对应的处理动作"""
        for v in self.violations:
            if v.get("type") == violation_type:
                return v
        return None
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "protocol_id": self.protocol_id,
            "name": self.name,
            "name_en": self.name_en,
            "version": self.version,
            "status": self.status,
            "priority": self.priority,
            "effective_level": self.effective_level,
            "actions_count": len(self.actions),
            "violations_count": len(self.violations)
        }


class ProtocolLoader:
    """协议加载器"""
    
    def __init__(self, protocol_dir: Path = None):
        self.protocol_dir = protocol_dir or GOV_PROTOCOL_DIR
        self.rules: Dict[str, ProtocolRule] = {}
        self.load_all()
    
    def load_all(self) -> int:
        """加载所有协议文件"""
        count = 0
        self.rules.clear()
        
        if not self.protocol_dir.exists():
            return 0
        
        for yaml_file in sorted(self.protocol_dir.glob("G*.yaml")):
            try:
                protocol_id = yaml_file.stem
                rule = self.load_file(yaml_file)
                if rule:
                    self.rules[protocol_id] = rule
                    count += 1
            except Exception as e:
                print(f"[ERROR] 加载协议失败 {yaml_file}: {e}", file=sys.stderr)
        
        return count
    
    def load_file(self, filepath: Path) -> Optional[ProtocolRule]:
        """加载单个协议文件"""
        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        protocol_id = data.get("protocol_id", filepath.stem)
        return ProtocolRule(protocol_id, data)
    
    def get_rule(self, protocol_id: str) -> Optional[ProtocolRule]:
        """获取单条规则"""
        return self.rules.get(protocol_id)
    
    def get_all_rules(self) -> List[ProtocolRule]:
        """获取所有规则（按优先级排序）"""
        return sorted(self.rules.values(), key=lambda r: r.priority)
    
    def check_event(self, event: dict) -> dict:
        """
        检查事件是否违反任何协议
        返回: {"allowed": bool, "violations": list, "actions": list}
        """
        violations = []
        matched_actions = []
        
        for rule in self.get_all_rules():
            result = rule.check_condition(event)
            
            if result["match"] and result["action"] == "deny":
                violations.append({
                    "protocol_id": rule.protocol_id,
                    "reason": result["reason"]
                })
            elif result["match"] and result["action"] == "allow":
                matched_actions.append({
                    "protocol_id": rule.protocol_id,
                    "reason": result["reason"]
                })
        
        return {
            "allowed": len(violations) == 0,
            "violations": violations,
            "matched_actions": matched_actions,
            "rules_checked": len(self.rules)
        }
    
    def reload(self) -> int:
        """重新加载所有协议（热加载）"""
        return self.load_all()


# 全局加载器实例
_loader = None

def get_loader() -> ProtocolLoader:
    """获取全局加载器实例"""
    global _loader
    if _loader is None:
        _loader = ProtocolLoader()
    return _loader


if __name__ == "__main__":
    # 测试
    loader = ProtocolLoader()
    print(f"已加载 {len(loader.rules)} 条协议")
    
    for rule in loader.get_all_rules():
        print(f"  {rule.protocol_id}: {rule.name} (优先级:{rule.priority})")
    
    # 测试事件检查
    test_event = {
        "event_type": "核心范式修改提案",
        "operator": "Nyx",
        "timestamp": "2026-05-20T12:00:00"
    }
    
    result = loader.check_event(test_event)
    print(f"\n测试结果:")
    print(f"  允许: {result['allowed']}")
    print(f"  违规数: {len(result['violations'])}")
    print(f"  检查规则数: {result['rules_checked']}")
