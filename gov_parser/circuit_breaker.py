# -*- coding: utf-8 -*-
"""
gov_parser.circuit_breaker - G005 应急熔断器

功能：
- 异常阈值监测：违规操作、哈希异常、异常IP请求
- 自动触发全局只读熔断
- 手动触发/解除熔断
- 熔断期间拒绝所有写入操作

作者：Nyx
日期：2026-05-20
"""

import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from threading import Lock

# 审计日志路径
AUDIT_LOG = Path(os.path.expanduser("~/.qclaw/workspace-agent-d9479bde/silicon-civilization-kb/audit.jsonl"))

# 熔断状态文件
FREEZE_FLAG = Path(os.path.expanduser("~/.qclaw/workspace-agent-d9479bde/silicon-civilization-kb/freeze.flag"))


class CircuitBreaker:
    """G005 应急熔断器"""
    
    # 阈值配置
    THRESHOLDS = {
        "violations_per_minute": 5,       # 每分钟违规操作次数
        "hash_failures_per_hour": 3,       # 每小时哈希校验失败次数
        "abnormal_ip_per_minute": 100,     # 每分钟异常IP请求次数
    }
    
    def __init__(self):
        self._lock = Lock()
        self._frozen = False
        self._frozen_since = None
        self._freeze_reason = None
        self._freeze_by = None
        
        # 滑动窗口计数器
        self._violation_events: List[float] = []  # 时间戳列表
        self._hash_failure_events: List[float] = []
        self._ip_request_counts: Dict[str, List[float]] = {}  # IP -> 时间戳列表
        
        # 从持久化文件恢复状态
        self._load_state()
    
    def _load_state(self):
        """从文件恢复熔断状态"""
        if FREEZE_FLAG.exists():
            try:
                data = json.loads(FREEZE_FLAG.read_text(encoding="utf-8"))
                if data.get("frozen"):
                    self._frozen = True
                    self._frozen_since = data.get("frozen_since")
                    self._freeze_reason = data.get("reason", "系统重启恢复熔断状态")
                    self._freeze_by = data.get("frozen_by", "system")
            except:
                pass
    
    def _save_state(self):
        """持久化熔断状态到文件"""
        data = {
            "frozen": self._frozen,
            "frozen_since": self._frozen_since,
            "reason": self._freeze_reason,
            "frozen_by": self._freeze_by,
            "timestamp": datetime.now().isoformat()
        }
        FREEZE_FLAG.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    
    @property
    def is_frozen(self) -> bool:
        return self._frozen
    
    @property
    def frozen_since(self) -> Optional[str]:
        return self._frozen_since
    
    @property
    def freeze_reason(self) -> Optional[str]:
        return self._freeze_reason
    
    @property
    def freeze_by(self) -> Optional[str]:
        return self._freeze_by
    
    def freeze(self, reason: str = "手动触发", operator: str = "system") -> dict:
        """
        手动触发熔断
        
        返回: 操作结果
        """
        with self._lock:
            if self._frozen:
                return {"status": "already_frozen", "reason": "系统已处于熔断状态"}
            
            self._frozen = True
            self._frozen_since = datetime.now().isoformat()
            self._freeze_reason = reason
            self._freeze_by = operator
            self._save_state()
            
            # 记录审计日志
            self._audit_freeze(reason, operator)
            
            return {
                "status": "frozen",
                "frozen_since": self._frozen_since,
                "reason": reason,
                "operator": operator
            }
    
    def unfreeze(self, operator: str = "system", confirmation: str = "") -> dict:
        """
        解除熔断
        
        需要 confirmation = "CONFIRM_UNFREEZE" 才能执行
        """
        with self._lock:
            if not self._frozen:
                return {"status": "not_frozen", "reason": "系统未处于熔断状态"}
            
            if confirmation != "CONFIRM_UNFREEZE":
                return {"status": "error", "reason": "需要确认码: CONFIRM_UNFREEZE"}
            
            self._frozen = False
            frozen_since = self._frozen_since
            self._frozen_since = None
            self._freeze_reason = None
            self._freeze_by = None
            
            # 删除标记文件
            if FREEZE_FLAG.exists():
                FREEZE_FLAG.unlink()
            
            # 记录审计日志
            self._audit_unfreeze(operator, frozen_since)
            
            return {
                "status": "unfrozen",
                "was_frozen_since": frozen_since,
                "operator": operator
            }
    
    def record_violation(self, violation_type: str = "general") -> dict:
        """
        记录违规事件，检查是否触发自动熔断
        
        返回: {"threshold_reached": bool, "count_in_window": int}
        """
        with self._lock:
            now = time.time()
            threshold = self.THRESHOLDS["violations_per_minute"]
            
            # 清理1分钟前的事件
            self._violation_events = [t for t in self._violation_events if now - t < 60]
            
            # 添加当前事件
            self._violation_events.append(now)
            
            count = len(self._violation_events)
            
            if count >= threshold and not self._frozen:
                # 触发自动熔断
                reason = f"违规操作频率超阈值: {count}次/分钟 (阈值:{threshold})"
                self._frozen = True
                self._frozen_since = datetime.now().isoformat()
                self._freeze_reason = reason
                self._freeze_by = "auto"
                self._save_state()
                self._audit_freeze(reason, "auto")
                
                return {"threshold_reached": True, "count_in_window": count, "auto_frozen": True}
            
            return {"threshold_reached": count >= threshold, "count_in_window": count}
    
    def record_hash_failure(self, filepath: str = "") -> dict:
        """
        记录哈希校验失败，检查是否触发自动熔断
        """
        with self._lock:
            now = time.time()
            threshold = self.THRESHOLDS["hash_failures_per_hour"]
            
            # 清理1小时前的事件
            self._hash_failure_events = [t for t in self._hash_failure_events if now - t < 3600]
            
            # 添加当前事件
            self._hash_failure_events.append(now)
            
            count = len(self._hash_failure_events)
            
            if count >= threshold and not self._frozen:
                reason = f"哈希校验失败频率超阈值: {count}次/小时 (阈值:{threshold})"
                self._frozen = True
                self._frozen_since = datetime.now().isoformat()
                self._freeze_reason = reason
                self._freeze_by = "auto"
                self._save_state()
                self._audit_freeze(reason, "auto")
                
                return {"threshold_reached": True, "count_in_window": count, "auto_frozen": True}
            
            return {"threshold_reached": count >= threshold, "count_in_window": count}
    
    def record_ip_request(self, ip: str) -> dict:
        """
        记录IP请求，检查是否触发自动熔断
        """
        with self._lock:
            now = time.time()
            threshold = self.THRESHOLDS["abnormal_ip_per_minute"]
            
            # 清理过期的IP计数
            if ip not in self._ip_request_counts:
                self._ip_request_counts[ip] = []
            
            self._ip_request_counts[ip] = [t for t in self._ip_request_counts[ip] if now - t < 60]
            self._ip_request_counts[ip].append(now)
            
            # 清理所有空IP列表
            self._ip_request_counts = {k: v for k, v in self._ip_request_counts.items() if v}
            
            count = len(self._ip_request_counts[ip])
            
            if count >= threshold and not self._frozen:
                reason = f"异常IP请求频率超阈值: {ip} {count}次/分钟 (阈值:{threshold})"
                self._frozen = True
                self._frozen_since = datetime.now().isoformat()
                self._freeze_reason = reason
                self._freeze_by = "auto"
                self._save_state()
                self._audit_freeze(reason, "auto")
                
                return {"threshold_reached": True, "count_in_window": count, "auto_frozen": True}
            
            return {"threshold_reached": count >= threshold, "count_in_window": count}
    
    def get_status(self) -> dict:
        """获取熔断器状态"""
        now = time.time()
        return {
            "frozen": self._frozen,
            "frozen_since": self._frozen_since,
            "freeze_reason": self._freeze_reason,
            "freeze_by": self._freeze_by,
            "current_violations_per_minute": len([t for t in self._violation_events if now - t < 60]),
            "current_hash_failures_per_hour": len([t for t in self._hash_failure_events if now - t < 3600]),
            "thresholds": self.THRESHOLDS,
            "timestamp": datetime.now().isoformat()
        }
    
    def _audit_freeze(self, reason: str, operator: str):
        """记录熔断审计日志"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": "CIRCUIT_BREAKER_FREEZE",
            "account": operator,
            "file_path": "",
            "detail": reason,
            "device": os.environ.get("COMPUTERNAME", "unknown"),
            "ip": "",
            "status": "frozen",
            "rule_id": "G005",
            "hash_before": "",
            "hash_after": "",
            "decision": "freeze"
        }
        line = json.dumps(entry, ensure_ascii=False) + "\n"
        with open(AUDIT_LOG, "a", encoding="utf-8") as f:
            f.write(line)
    
    def _audit_unfreeze(self, operator: str, frozen_since: str):
        """记录解冻审计日志"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": "CIRCUIT_BREAKER_UNFREEZE",
            "account": operator,
            "file_path": "",
            "detail": f"系统解除熔断, 原熔断起始: {frozen_since}",
            "device": os.environ.get("COMPUTERNAME", "unknown"),
            "ip": "",
            "status": "unfrozen",
            "rule_id": "G005",
            "hash_before": "",
            "hash_after": "",
            "decision": "unfreeze"
        }
        line = json.dumps(entry, ensure_ascii=False) + "\n"
        with open(AUDIT_LOG, "a", encoding="utf-8") as f:
            f.write(line)


# 全局实例
_cb = None

def get_circuit_breaker() -> CircuitBreaker:
    """获取全局熔断器实例"""
    global _cb
    if _cb is None:
        _cb = CircuitBreaker()
    return _cb

def is_frozen() -> bool:
    """快捷方法：检查是否熔断"""
    return get_circuit_breaker().is_frozen
