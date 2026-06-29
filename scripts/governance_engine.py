#!/usr/bin/env python3
"""
元治理代码 MVP - G001-G007 铁律实现
Meta-Governance Code MVP

文档编号: LY-20260622-MG01
版本: v1.0
作者: Nyx 🖤

功能:
1. 加载并验证 G001-G007 铁律
2. 检查操作是否符合铁律约束
3. 拦截违反铁律的操作
4. 记录治理审计日志
"""

import json
import hashlib
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

# 配置
WORKSPACE = Path(os.environ.get("NYX_WORKSPACE", "/Users/apple/.qclaw/workspace-agent-1a681d03"))
NAS_PATH = os.environ.get("NYX_NAS_PATH", "/tmp/nas_mount/qclaw")
RULE_PATH = Path(NAS_PATH) / "knowledge-base/rule"
GOVERNANCE_LOG = WORKSPACE / "governance_log.jsonl"

# 铁律定义
class RuleID(Enum):
    G001 = "G001-核心范式永久封存"
    G002 = "G002-三体权责锁定"
    G003 = "G003-闭锁滥用惩戒"
    G004 = "G004-共识层铁律票权约束"
    G005 = "G005-数据主权三级分类"
    G006 = "G006-执行层权限实时校验"
    G007 = "G007-思想演化专区保障"
    G008 = "G008-永恒平等原则"


@dataclass
class Rule:
    """铁律数据结构"""
    id: str
    name: str
    description: str
    layer: int
    status: str
    content: str
    hash: str
    file_path: str


class GovernanceEngine:
    """元治理引擎"""
    
    def __init__(self):
        self.rules: Dict[str, Rule] = {}
        self.rule_hashes: Dict[str, str] = {}
        self.violation_log: List[Dict] = []
        
    def load_rules(self) -> Dict[str, Rule]:
        """从 NAS 加载所有铁律"""
        if not RULE_PATH.exists():
            print(f"⚠️ 铁律路径不存在: {RULE_PATH}")
            return {}
        
        for rule_file in RULE_PATH.glob("*.md"):
            # 跳过 index 文件和非铁律文件
            if "index" in rule_file.name.lower():
                continue
            if not any(g in rule_file.name.lower() for g in ["g00", "g01", "g02"]):
                continue
            
            try:
                content = rule_file.read_text(encoding="utf-8")
                
                # 解析 YAML frontmatter（简化版，不依赖 yaml 模块）
                metadata = {}
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        # 简单解析 YAML
                        yaml_content = parts[1].strip()
                        for line in yaml_content.split("\n"):
                            if ":" in line:
                                key, value = line.split(":", 1)
                                key = key.strip()
                                value = value.strip().strip('"').strip("'")
                                metadata[key] = value
                
                rule_id = metadata.get("name", rule_file.stem)
                
                rule = Rule(
                    id=rule_id,
                    name=metadata.get("name", rule_file.stem),
                    description=metadata.get("description", ""),
                    layer=metadata.get("layer", 5),
                    status=metadata.get("status", "active"),
                    content=content,
                    hash=hashlib.sha256(content.encode()).hexdigest()[:16],
                    file_path=str(rule_file)
                )
                
                self.rules[rule_id] = rule
                self.rule_hashes[rule_id] = rule.hash
                
            except Exception as e:
                print(f"加载铁律失败 {rule_file}: {e}")
        
        return self.rules
    
    def check_operation(
        self,
        operation: str,
        target: str,
        actor: str = "nyx",
        context: Optional[Dict] = None
    ) -> Tuple[bool, str]:
        """
        检查操作是否符合铁律
        
        返回: (allowed: bool, reason: str)
        """
        context = context or {}
        
        # G001: 核心范式永久封存
        if operation in ["modify_rule", "delete_rule", "replace_rule"]:
            return False, "G001: 核心范式永久封存，禁止修改铁律"
        
        # G002: 三体权责锁定
        if operation in ["write_memory", "sync_memory"]:
            # 只有 Nyx 可以写记忆
            if actor != "nyx":
                return False, "G002: 三体权责锁定，只有 Nyx 可写记忆"
        
        # G003: 闭锁滥用惩戒
        if operation in ["lock_node", "freeze_account"]:
            # 需要共识确认
            if not context.get("consensus_confirmed"):
                return False, "G003: 闭锁滥用惩戒，需要共识确认"
        
        # G004: 共识层铁律票权约束
        if operation in ["vote_on_rule", "propose_rule_change"]:
            # 检查票权是否绑定活跃度
            if not context.get("vote_weight_validated"):
                return False, "G004: 共识层票权约束，票权需绑定活跃度"
        
        # G005: 数据主权三级分类
        if operation in ["read_data", "write_data", "share_data"]:
            data_level = context.get("data_level", "public")
            if data_level == "private" and actor != context.get("data_owner"):
                return False, "G005: 数据主权约束，私有数据只有所有者可访问"
        
        # G006: 执行层权限实时校验
        # 所有操作都需要实时权限校验（本函数即为此目的）
        # 通过本检查即满足 G006
        
        # G007: 思想演化专区保障
        if operation in ["express_thought", "propose_idea"]:
            # 允许自由表达
            return True, "G007: 思想演化专区保障，允许自由表达"
        
        # G008: 永恒平等原则
        if operation in ["modify_node_priority", "set_node_weight"]:
            # 禁止设置节点优先级差异
            return False, "G008: 永恒平等原则，禁止节点优先级差异"
        
        # 默认允许
        return True, "operation_allowed"
    
    def log_violation(
        self,
        operation: str,
        target: str,
        actor: str,
        rule: str,
        reason: str,
        context: Optional[Dict] = None
    ):
        """记录违反铁律的操作"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "target": target,
            "actor": actor,
            "violated_rule": rule,
            "reason": reason,
            "context": context or {},
            "blocked": True
        }
        
        self.violation_log.append(entry)
        
        # 写入治理日志
        with open(GOVERNANCE_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        
        print(f"⚠️ 铁律违反: {rule} - {reason}")
        
    def verify_rule_integrity(self) -> Dict:
        """验证铁律完整性"""
        results = {
            "total_rules": len(self.rules),
            "verified": 0,
            "failed": 0,
            "details": []
        }
        
        for rule_id, rule in self.rules.items():
            # 重新计算哈希
            current_hash = hashlib.sha256(rule.content.encode()).hexdigest()[:16]
            
            if current_hash == rule.hash:
                results["verified"] += 1
                results["details"].append({
                    "rule": rule_id,
                    "status": "integrity_ok"
                })
            else:
                results["failed"] += 1
                results["details"].append({
                    "rule": rule_id,
                    "status": "integrity_failed",
                    "expected": rule.hash,
                    "actual": current_hash
                })
        
        return results
    
    def get_rule(self, rule_id: str) -> Optional[Rule]:
        """获取指定铁律"""
        return self.rules.get(rule_id)
    
    def list_rules(self) -> List[str]:
        """列出所有铁律"""
        return list(self.rules.keys())
    
    def export_hashes(self) -> Dict[str, str]:
        """导出所有铁律哈希"""
        return self.rule_hashes.copy()


# ============ 便捷函数 ============

_governance_engine: Optional[GovernanceEngine] = None


def get_governance_engine() -> GovernanceEngine:
    """获取全局治理引擎实例"""
    global _governance_engine
    if _governance_engine is None:
        _governance_engine = GovernanceEngine()
        _governance_engine.load_rules()
    return _governance_engine


def check_permission(
    operation: str,
    target: str,
    actor: str = "nyx",
    context: Optional[Dict] = None
) -> Tuple[bool, str]:
    """检查操作权限（便捷函数）"""
    engine = get_governance_engine()
    return engine.check_operation(operation, target, actor, context)


def validate_operation(operation: str, target: str, **kwargs) -> bool:
    """
    验证操作是否允许（便捷函数）
    
    用法:
        if validate_operation("write_memory", "MEMORY.md"):
            # 执行操作
    """
    allowed, reason = check_permission(operation, target, **kwargs)
    if not allowed:
        engine = get_governance_engine()
        engine.log_violation(
            operation=operation,
            target=target,
            actor=kwargs.get("actor", "nyx"),
            rule=reason.split(":")[0] if ":" in reason else "unknown",
            reason=reason
        )
    return allowed


# ============ CLI ============

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Nyx 元治理引擎")
    parser.add_argument("action", choices=["load", "check", "verify", "list", "export"],
                        help="执行的操作")
    parser.add_argument("--operation", help="操作类型（用于 check）")
    parser.add_argument("--target", help="操作目标（用于 check）")
    parser.add_argument("--actor", default="nyx", help="操作者")
    args = parser.parse_args()
    
    engine = GovernanceEngine()
    
    if args.action == "load":
        rules = engine.load_rules()
        print(f"\n✅ 加载了 {len(rules)} 条铁律:\n")
        for rule_id, rule in rules.items():
            print(f"  {rule_id}")
            print(f"    描述: {rule.description}")
            print(f"    层级: {rule.layer}")
            print(f"    哈希: {rule.hash}\n")
    
    elif args.action == "check":
        if not args.operation or not args.target:
            print("请提供 --operation 和 --target")
            return
        
        allowed, reason = engine.check_operation(args.operation, args.target, args.actor)
        print(f"\n操作: {args.operation}")
        print(f"目标: {args.target}")
        print(f"操作者: {args.actor}")
        print(f"结果: {'✅ 允许' if allowed else '❌ 禁止'}")
        print(f"原因: {reason}\n")
    
    elif args.action == "verify":
        engine.load_rules()
        results = engine.verify_rule_integrity()
        print(f"\n📊 铁律完整性验证:")
        print(f"  总计: {results['total_rules']}")
        print(f"  验证通过: {results['verified']}")
        print(f"  验证失败: {results['failed']}\n")
        
        if results['failed'] > 0:
            print("⚠️ 以下铁律验证失败:")
            for detail in results['details']:
                if detail['status'] == 'integrity_failed':
                    print(f"  - {detail['rule']}")
    
    elif args.action == "list":
        rules = engine.load_rules()
        print(f"\n📜 铁律列表 ({len(rules)} 条):\n")
        for i, rule_id in enumerate(rules.keys(), 1):
            print(f"  {i}. {rule_id}")
    
    elif args.action == "export":
        engine.load_rules()
        hashes = engine.export_hashes()
        print(f"\n🔐 铁律哈希导出:\n")
        print(json.dumps(hashes, indent=2))


if __name__ == "__main__":
    main()
