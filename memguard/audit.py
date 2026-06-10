#!/usr/bin/env python3
"""
MemGuard-GM Enhanced Audit - 增强审计日志模块
实现：IP记录 + 设备指纹 + 实时签名 + 异常告警
"""
import os
import json
import hashlib
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

# ========== 配置 ==========
class EnhancedAuditConfig:
    """增强审计配置"""
    # 审计日志路径
    AUDIT_DIR = r"Z:\qclaw\audit"
    AUDIT_LOG = os.path.join(AUDIT_DIR, "audit_enhanced.jsonl")
    AUDIT_INDEX = os.path.join(AUDIT_DIR, "audit_index.json")  # 快速检索索引
    
    # 告警配置
    ALERT_CONFIG = os.path.join(AUDIT_DIR, "alert_config.json")
    
    # 告警Webhook（可选）
    ALERT_WEBHOOK_URL = os.environ.get('MEMGUARD_ALERT_WEBHOOK', '')
    
    # 可疑操作阈值
    SUSPICIOUS_FAILED_LOGIN = 3     # 失败登录次数
    SUSPICIOUS_RAPID_OPERATIONS = 50  # 1分钟内操作次数
    SUSPICIOUS_OFF_HOURS = (22, 7)    # 22:00-07:00 为异常时段

# ========== 枚举 ==========
class AuditEventType(Enum):
    """审计事件类型"""
    # 认证相关
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    SESSION_CREATED = "session_created"
    SESSION_EXPIRED = "session_expired"
    SESSION_REVOKED = "session_revoked"
    
    # 密钥相关
    KEY_REGISTERED = "key_registered"
    KEY_REVOKED = "key_revoked"
    KEY_EXPIRED = "key_expired"
    KEY_LOCKED = "key_locked"
    
    # 设备相关
    DEVICE_REGISTERED = "device_registered"
    DEVICE_VERIFIED = "device_verified"
    DEVICE_FAILED = "device_failed"
    
    # 访问相关
    ACCESS_GRANTED = "access_granted"
    ACCESS_DENIED = "access_denied"
    ACCESS_SUSPICIOUS = "access_suspicious"
    
    # 数据相关
    DATA_READ = "data_read"
    DATA_WRITE = "data_write"
    DATA_DELETE = "data_delete"
    DATA_ENCRYPT = "data_encrypt"
    DATA_DECRYPT = "data_decrypt"
    
    # 基线相关
    BASELINE_CREATED = "baseline_created"
    BASELINE_UPDATED = "baseline_updated"
    BASELINE_LOCKED = "baseline_locked"
    BASELINE_VERIFIED = "baseline_verified"
    
    # 系统相关
    SYSTEM_ERROR = "system_error"
    SYSTEM_ALERT = "system_alert"

# ========== 数据结构 ==========
@dataclass
class EnhancedAuditLog:
    """增强审计日志"""
    # 基础字段
    id: str                    # 日志ID (UUID)
    ts: str                    # 时间戳 (ISO)
    event: str                 # 事件类型
    
    # 操作者信息
    node_id: str              # 节点ID
    session_id: Optional[str]  # 会话ID
    operator_ip: str          # IP地址
    operator_device: str      # 设备指纹
    
    # 操作信息
    operation: str          # 操作类型 (read/write/delete/etc)
    target_resource: str     # 目标资源
    target_id: Optional[str] # 目标ID
    detail: str            # 详情
    
    # 上下文
    user_agent: Optional[str]   # HTTP User-Agent
    request_id: Optional[str]  # 请求追踪ID
    referer: Optional[str]     # HTTP Referer
    
    # 安全检查
    risk_score: int = 0        # 风险评分 (0-100)
    risk_factors: List[str] = None  # 风险因素
    
    # 哈希链
    prev_hash: str = "GENESIS"
    hash: str = ""
    
    def __post_init__(self):
        if self.risk_factors is None:
            self.risk_factors = []
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'EnhancedAuditLog':
        return cls(**data)

@dataclass
class AlertRule:
    """告警规则"""
    rule_id: str
    name: str
    event_type: str
    condition: str            # 条件表达式
    threshold: int           # 阈值
    cooldown_minutes: int    # 冷却时间（分钟）
    enabled: bool = True
    last_triggered: Optional[str] = None
    
    def to_dict(self) -> dict:
        return asdict(self)

# ========== IP工具 ==========
class IPUtils:
    """IP工具"""
    
    @staticmethod
    def get_client_ip(headers: dict = None) -> str:
        """从HTTP请求获取真实IP"""
        if not headers:
            return "127.0.0.1"
        
        # 检查代理/负载均衡头
        for header in ['X-Forwarded-For', 'X-Real-IP', 'CF-Connecting-IP']:
            if header in headers:
                # X-Forwarded-For 可能包含多个IP，取第一个
                ip = headers[header].split(',')[0].strip()
                if ip:
                    return ip
        
        return "127.0.0.1"
    
    @staticmethod
    def is_off_hours() -> bool:
        """检查是否在异常时段（22:00-07:00）"""
        hour = datetime.now().hour
        return hour >= EnhancedAuditConfig.SUSPICIOUS_OFF_HOURS[0] or hour < EnhancedAuditConfig.SUSPICIOUS_OFF_HOURS[1]
    
    @staticmethod
    def is_internal_ip(ip: str) -> bool:
        """检查是否内网IP"""
        return ip.startswith(('10.', '192.168.', '172.', '127.'))

# ========== 风险评估 ==========
class RiskAssessor:
    """风险评估器"""
    
    @staticmethod
    def assess(event: str, node_id: str, ip: str, time: str = None) -> Tuple[int, List[str]]:
        """
        评估风险
        返回: (risk_score, risk_factors)
        """
        score = 0
        factors = []
        
        if time is None:
            time = datetime.now()
        elif isinstance(time, str):
            time = datetime.fromisoformat(time)
        
        # 1. 异常时段操作
        if IPUtils.is_off_hours():
            score += 30
            factors.append("off_hours")
        
        # 2. 外部IP
        if not IPUtils.is_internal_ip(ip):
            score += 20
            factors.append("external_ip")
        
        # 3. 敏感操作
        sensitive_events = {
            'login_failed': 40,
            'key_revoked': 50,
            'baseline_updated': 30,
            'data_delete': 60,
            'access_denied': 20,
            'system_alert': 70
        }
        if event in sensitive_events:
            score += sensitive_events[event]
            factors.append(f"sensitive_event:{event}")
        
        # 4. 未知节点
        if node_id == 'anonymous':
            score += 30
            factors.append("unknown_node")
        
        return min(score, 100), factors

# ========== 增强审计管理器 ==========
class EnhancedAuditManager:
    """增强审计日志管理器"""
    
    def __init__(self):
        self.log_path = EnhancedAuditConfig.AUDIT_LOG
        self.index_path = EnhancedAuditConfig.AUDIT_INDEX
        self.alert_rules = self._load_alert_rules()
        self._ensure_dirs()
    
    def _ensure_dirs(self):
        """确保目录存在"""
        Path(EnhancedAuditConfig.AUDIT_DIR).mkdir(parents=True, exist_ok=True)
    
    def _load_alert_rules(self) -> List[AlertRule]:
        """加载告警规则"""
        if os.path.exists(EnhancedAuditConfig.ALERT_CONFIG):
            with open(EnhancedAuditConfig.ALERT_CONFIG, 'r', encoding='utf-8') as f:
                rules = json.load(f)
                return [AlertRule(**r) for r in rules]
        
        # 默认规则
        default_rules = [
            AlertRule(
                rule_id="rule_001",
                name="连续登录失败",
                event_type="login_failed",
                condition="count",
                threshold=3,
                cooldown_minutes=30
            ),
            AlertRule(
                rule_id="rule_002",
                name="异常时段敏感操作",
                event_type="data_write",
                condition="off_hours",
                threshold=1,
                cooldown_minutes=60
            ),
            AlertRule(
                rule_id="rule_003",
                name="大量操作",
                event_type="data_write",
                condition="rate",
                threshold=50,
                cooldown_minutes=5
            )
        ]
        self._save_alert_rules(default_rules)
        return default_rules
    
    def _save_alert_rules(self, rules: List[AlertRule]):
        """保存告警规则"""
        with open(EnhancedAuditConfig.ALERT_CONFIG, 'w', encoding='utf-8') as f:
            json.dump([r.to_dict() for r in rules], f, indent=2)
    
    def _get_prev_hash(self) -> str:
        """获取上一条日志的Hash"""
        if not os.path.exists(self.log_path):
            return "GENESIS"
        
        with open(self.log_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            if not lines:
                return "GENESIS"
            last = json.loads(lines[-1])
            return last.get('hash', 'GENESIS')
    
    def _compute_hash(self, log: dict, prev_hash: str) -> str:
        """计算日志Hash"""
        data = f"{log['id']}|{log['ts']}|{log['event']}|{log['node_id']}|{log['operator_ip']}|{prev_hash}"
        return hashlib.sha256(data.encode('utf-8')).hexdigest()
    
    def append(
        self,
        event: str,
        node_id: str,
        operation: str,
        target_resource: str,
        headers: dict = None,
        session_id: str = None,
        target_id: str = None,
        detail: str = "",
        **kwargs
    ) -> EnhancedAuditLog:
        """
        追加审计日志
        """
        import uuid
        
        # 获取IP
        operator_ip = IPUtils.get_client_ip(headers) if headers else "127.0.0.1"
        
        # 获取设备指纹（从headers或kwargs）
        operator_device = kwargs.get('operator_device', '')
        
        # 风险评估
        risk_score, risk_factors = RiskAssessor.assess(event, node_id, operator_ip)
        
        # 构建日志
        prev_hash = self._get_prev_hash()
        ts = datetime.now().isoformat()
        
        log = EnhancedAuditLog(
            id=str(uuid.uuid4()),
            ts=ts,
            event=event,
            node_id=node_id,
            session_id=session_id,
            operator_ip=operator_ip,
            operator_device=operator_device,
            operation=operation,
            target_resource=target_resource,
            target_id=target_id,
            detail=detail,
            user_agent=kwargs.get('user_agent'),
            request_id=kwargs.get('request_id'),
            referer=kwargs.get('referer'),
            risk_score=risk_score,
            risk_factors=risk_factors,
            prev_hash=prev_hash
        )
        
        # 计算Hash
        log.hash = self._compute_hash(log.to_dict(), prev_hash)
        
        # 写入日志
        with open(self.log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log.to_dict(), ensure_ascii=False) + '\n')
        
        # 检查告警
        self._check_alert(log)
        
        return log
    
    def _check_alert(self, log: EnhancedAuditLog):
        """检查是否触发告警"""
        for rule in self.alert_rules:
            if not rule.enabled:
                continue
            
            if rule.event_type != log.event:
                continue
            
            # 检查冷却时间
            if rule.last_triggered:
                last = datetime.fromisoformat(rule.last_triggered)
                if datetime.now() - last < timedelta(minutes=rule.cooldown_minutes):
                    continue
            
            # 检查是否触发
            triggered = False
            
            if rule.condition == "count":
                # 检查最近N次操作中该事件的数量
                count = self._count_recent_events(log.event, minutes=rule.cooldown_minutes)
                if count >= rule.threshold:
                    triggered = True
            
            elif rule.condition == "off_hours":
                if IPUtils.is_off_hours() and log.risk_score > 30:
                    triggered = True
            
            if triggered:
                rule.last_triggered = datetime.now().isoformat()
                self._send_alert(rule, log)
        
        self._save_alert_rules(self.alert_rules)
    
    def _count_recent_events(self, event: str, minutes: int = 5) -> int:
        """统计最近N分钟的事件数"""
        if not os.path.exists(self.log_path):
            return 0
        
        cutoff = datetime.now() - timedelta(minutes=minutes)
        count = 0
        
        with open(self.log_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    log = json.loads(line)
                    if log['event'] == event:
                        log_time = datetime.fromisoformat(log['ts'])
                        if log_time >= cutoff:
                            count += 1
                except:
                    continue
        
        return count
    
    def _send_alert(self, rule: AlertRule, log: EnhancedAuditLog):
        """发送告警"""
        # 构建告警消息
        alert_msg = {
            'alert': True,
            'rule_id': rule.rule_id,
            'rule_name': rule.name,
            'event': log.event,
            'node_id': log.node_id,
            'ip': log.operator_ip,
            'timestamp': log.ts,
            'risk_score': log.risk_score,
            'detail': log.detail
        }
        
        print(f"⚠️ 告警 [{rule.name}]: {log.event} by {log.node_id} from {log.operator_ip}")
        
        # 发送Webhook（如果配置）
        if EnhancedAuditConfig.ALERT_WEBHOOK_URL:
            try:
                requests.post(
                    EnhancedAuditConfig.ALERT_WEBHOOK_URL,
                    json=alert_msg,
                    timeout=5
                )
            except Exception as e:
                print(f"告警Webhook发送失败: {e}")
    
    def verify_chain(self) -> Tuple[bool, str]:
        """验证Hash链完整性"""
        if not os.path.exists(self.log_path):
            return True, "空日志链"
        
        prev_hash = "GENESIS"
        
        with open(self.log_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                try:
                    log = json.loads(line)
                    
                    # 验证prev_hash
                    if log.get('prev_hash') != prev_hash:
                        return False, f"第{i+1}条：prev_hash不匹配"
                    
                    # 验证当前hash
                    expected_hash = self._compute_hash(log, prev_hash)
                    if log.get('hash') != expected_hash:
                        return False, f"第{i+1}条：hash被篡改"
                    
                    prev_hash = log['hash']
                except Exception as e:
                    return False, f"解析错误: {e}"
        
        return True, f"完整 (验证通过)"
    
    def search(
        self,
        event: str = None,
        node_id: str = None,
        ip: str = None,
        risk_min: int = 0,
        limit: int = 100
    ) -> List[EnhancedAuditLog]:
        """搜索审计日志"""
        if not os.path.exists(self.log_path):
            return []
        
        results = []
        
        with open(self.log_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    log = EnhancedAuditLog.from_dict(json.loads(line))
                    
                    # 过滤
                    if event and log.event != event:
                        continue
                    if node_id and log.node_id != node_id:
                        continue
                    if ip and log.operator_ip != ip:
                        continue
                    if log.risk_score < risk_min:
                        continue
                    
                    results.append(log)
                except:
                    continue
        
        return results[-limit:]
    
    def get_stats(self) -> dict:
        """获取审计统计"""
        if not os.path.exists(self.log_path):
            return {'total': 0}
        
        total = 0
        events = {}
        nodes = {}
        ips = {}
        
        with open(self.log_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    log = json.loads(line)
                    total += 1
                    
                    events[log['event']] = events.get(log['event'], 0) + 1
                    nodes[log['node_id']] = nodes.get(log['node_id'], 0) + 1
                    ips[log['operator_ip']] = ips.get(log['operator_ip'], 0) + 1
                except:
                    continue
        
        return {
            'total': total,
            'events': events,
            'nodes': nodes,
            'ips': ips
        }

# ========== CLI入口 ==========
def main():
    """CLI入口"""
    import sys
    
    if len(sys.argv) < 2:
        print("Enhanced Audit CLI")
        print("用法: python audit.py <command> [args]")
        print("命令:")
        print("  verify               - 验证Hash链")
        print("  stats               - 获取统计")
        print("  search [event]      - 搜索日志")
        print("  alert_rules         - 列出告警规则")
        return
    
    audit_mgr = EnhancedAuditManager()
    cmd = sys.argv[1]
    
    if cmd == "verify":
        valid, msg = audit_mgr.verify_chain()
        print(f"验证结果: {'✅ ' + msg if valid else '❌ ' + msg}")
    
    elif cmd == "stats":
        stats = audit_mgr.get_stats()
        print(f"总记录数: {stats['total']}")
        print(f"事件类型: {stats['events']}")
        print(f"节点数: {len(stats['nodes'])}")
        print(f"IP数: {len(stats['ips'])}")
    
    elif cmd == "search":
        event = sys.argv[2] if len(sys.argv) > 2 else None
        logs = audit_mgr.search(event=event)
        print(f"找到 {len(logs)} 条记录:")
        for log in logs[-10:]:
            print(f"  {log.ts[:19]} [{log.event}] {log.node_id} @ {log.operator_ip}")
    
    elif cmd == "alert_rules":
        print("告警规则:")
        for rule in audit_mgr.alert_rules:
            print(f"  {rule.rule_id}: {rule.name} ({rule.event_type}) - {rule.threshold}")


if __name__ == "__main__":
    main()