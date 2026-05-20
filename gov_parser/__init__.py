# -*- coding: utf-8 -*-
"""
gov_parser - 治理协议解析器模块

功能：
- 加载G001-G005治理协议
- 解析为可执行的判定逻辑
- 绑定知识库操作事件
- 提供治理API接口

作者：Nyx
日期：2026-05-20
"""

from pathlib import Path

# 模块版本
__version__ = "1.0.0"
__author__ = "Nyx"

# 协议目录
GOV_PROTOCOL_DIR = Path(__import__("os").path.expanduser("~/.qclaw/workspace-agent-d9479bde/silicon-civilization-kb/gov_protocol"))

# 导入核心组件
from .loader import ProtocolLoader, ProtocolRule, get_loader
from .parser_core import RuleParserCore, get_parser_core
from .rule_matcher import RuleMatcher, get_matcher
from .trigger_hook import TriggerHook, get_hook
from .permission_checker import governance_check
from .circuit_breaker import CircuitBreaker, get_circuit_breaker, is_frozen

# 导出
__all__ = [
    "ProtocolLoader",
    "ProtocolRule",
    "get_loader",
    "RuleParserCore",
    "get_parser_core",
    "RuleMatcher",
    "get_matcher",
    "TriggerHook",
    "get_hook",
    "governance_check",
    "CircuitBreaker",
    "get_circuit_breaker",
    "is_frozen",
    "GOV_PROTOCOL_DIR",
    "init_gov_parser",
    "reload_gov_parser"
]


def init_gov_parser(protocol_dir: Path = None) -> bool:
    """
    初始化治理解析器
    
    参数:
        protocol_dir: 协议目录（可选，默认使用GOV_PROTOCOL_DIR）
    
    返回:
        是否初始化成功
    """
    try:
        # 设置协议目录
        if protocol_dir:
            loader = ProtocolLoader(protocol_dir)
        else:
            loader = get_loader()
        
        # 加载所有协议
        count = loader.load_all()
        
        if count == 0:
            print(f"[WARN] 未加载到任何治理协议，请检查 {GOV_PROTOCOL_DIR}", file=__import__("sys").stderr)
            return False
        
        print(f"[INFO] 已加载 {count} 条治理协议")
        
        # 初始化解析器
        parser = get_parser_core()
        
        # 加载协议到解析器
        rule_count = 0
        for protocol_id, rule_obj in loader.rules.items():
            count = parser.load_protocol(rule_obj.data)
            rule_count += count
        
        print(f"[INFO] 已解析 {rule_count} 条规则")
        
        # 初始化匹配器
        matcher = get_matcher()
        
        print(f"[INFO] 治理解析器初始化完成")
        print(f"  协议数: {count}")
        print(f"  规则数: {rule_count}")
        print(f"  事件处理器: {len(matcher.event_handlers)}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] 初始化治理解析器失败: {e}", file=__import__("sys").stderr)
        import traceback
        traceback.print_exc()
        return False


def reload_gov_parser() -> int:
    """
    重新加载治理解析器（热加载）
    
    返回:
        加载的协议数量
    """
    try:
        loader = get_loader()
        count = loader.reload()
        
        # 重新初始化解析器
        global _parser_core
        _parser_core = None
        parser = get_parser_core()
        
        rule_count = 0
        for protocol_id, rule_obj in loader.rules.items():
            count = parser.load_protocol(rule_obj.data)
            rule_count += count
        
        print(f"[INFO] 热加载完成: {count} 条协议, {rule_count} 条规则")
        
        return count
        
    except Exception as e:
        print(f"[ERROR] 热加载失败: {e}", file=__import__("sys").stderr)
        return 0


def get_gov_status() -> dict:
    """
    获取治理架构运行状态
    
    返回:
        状态字典
    """
    try:
        loader = get_loader()
        parser = get_parser_core()
        matcher = get_matcher()
        
        return {
            "status": "running",
            "protocol_count": len(loader.rules),
            "rule_count": len(parser.rule_pool),
            "event_handlers": len(matcher.event_handlers),
            "protocols": [p.to_dict() for p in loader.get_all_rules()],
            "rules_summary": parser.get_rule_pool_summary(),
            "timestamp": __import__("datetime").datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": __import__("datetime").datetime.now().isoformat()
        }


if __name__ == "__main__":
    # 测试
    print("=" * 60)
    print("  治理协议解析器测试")
    print("=" * 60)
    print()
    
    # 初始化
    success = init_gov_parser()
    
    if success:
        # 显示状态
        status = get_gov_status()
        print(f"\n运行状态:")
        print(f"  状态: {status['status']}")
        print(f"  协议数: {status['protocol_count']}")
        print(f"  规则数: {status['rule_count']}")
        print(f"  事件处理器: {status['event_handlers']}")
        
        # 测试事件检查
        print(f"\n测试事件检查:")
        
        test_events = [
            ("核心范式修改提案", {"event_type": "核心范式修改提案", "votes": {"yes": 5, "no": 0}, "participation_rate": 1.0}),
            ("心跳更新", {"event_type": "心跳更新", "last_heartbeat": __import__("datetime").datetime.now()}),
            ("路径检查", {"event_type": "目录权限锁检查", "path": "C:\\Users\\Administrator\\.qclaw\\workspace-agent-d9479bde\\knowledge-base\\test.md"})
        ]
        
        for name, context in test_events:
            result = matcher.match_event({"event_type": name, **context})
            print(f"  {name}: allowed={result['allowed']}, rules={len(result['matched_rules'])}")
        
    else:
        print("[ERROR] 初始化失败")
    
    print()
    print("=" * 60)
