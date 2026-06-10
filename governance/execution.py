#!/usr/bin/env python3
"""
execution.py - 执行层实现 v1.0
对应治理架构方案 LY-20260516-GA01 的执行层
Nyx 调度，实时权限校验器（事前拦截，非事后追溯）
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple, Callable
from enum import Enum
import json
from pathlib import Path
import sys
import os

# 导入协议层校验引擎
sys.path.insert(0, str(Path(__file__).parent.parent))
from kb import ProtocolEnforcer, ENTITY_TYPES, parse_yaml_front_matter

# 导入共识层
from consensus import ConsensusEngine, ProposalStatus

# ========== 配置 ==========
EXECUTION_DIR = Path(__file__).parent / "execution_data"
EXECUTION_LOG = EXECUTION_DIR / "execution.log"
PERMISSION_DENY_LOG = EXECUTION_DIR / "permission_deny.log"

class ExecutionStatus(Enum):
    PENDING = "pending"  # 待执行
    RUNNING = "running"  # 执行中
    SUCCESS = "success"  # 执行成功
    FAILED = "failed"  # 执行失败
    DENIED = "denied"  # 权限拒绝
    CANCELLED = "cancelled"  # 已取消

class ExecutionPriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3

# ========== 执行任务 ==========
class ExecutionTask:
    """执行任务"""
    
    def __init__(self, task_id: str, operator: str, action: str,
                 target_type: str, target_id: str, params: dict = None,
                 priority: ExecutionPriority = ExecutionPriority.NORMAL):
        self.task_id = task_id
        self.operator = operator  # 操作者（Nyx/恒/瞬）
        self.action = action  # 操作类型（create/modify/delete/lock/unlock）
        self.target_type = target_type  # 目标类型（Concept/Entity/Event/Rule/Artifact/Value）
        self.target_id = target_id  # 目标ID
        self.params = params or {}  # 操作参数
        
        self.priority = priority
        self.status = ExecutionStatus.PENDING
        self.created_at = datetime.now()
        self.started_at = None
        self.finished_at = None
        
        self.result = None  # 执行结果
        self.error = None  # 错误信息
        self.logs = []  # 执行日志
        
        self.pre_check_passed = False  # 事前校验是否通过
        self.pre_check_details = []  # 事前校验详情
    
    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "operator": self.operator,
            "action": self.action,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "params": self.params,
            "priority": self.priority.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "result": self.result,
            "error": self.error,
            "logs": self.logs,
            "pre_check_passed": self.pre_check_passed,
            "pre_check_details": self.pre_check_details
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ExecutionTask':
        task = cls(
            task_id=data["task_id"],
            operator=data["operator"],
            action=data["action"],
            target_type=data["target_type"],
            target_id=data["target_id"],
            params=data.get("params", {}),
            priority=ExecutionPriority(data.get("priority", 1))
        )
        task.status = ExecutionStatus(data.get("status", "pending"))
        task.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("started_at"):
            task.started_at = datetime.fromisoformat(data["started_at"])
        if data.get("finished_at"):
            task.finished_at = datetime.fromisoformat(data["finished_at"])
        task.result = data.get("result")
        task.error = data.get("error")
        task.logs = data.get("logs", [])
        task.pre_check_passed = data.get("pre_check_passed", False)
        task.pre_check_details = data.get("pre_check_details", [])
        return task

# ========== 实时权限校验器 ==========
class RealtimePermissionChecker:
    """实时权限校验器（事前拦截，非事后追溯）"""
    
    def __init__(self, protocol_enforcer: ProtocolEnforcer):
        self.enforcer = protocol_enforcer
        self.deny_log = []  # 拒绝记录
    
    def check_before_execution(self, task: ExecutionTask) -> Tuple[bool, List[str]]:
        """
        执行前实时校验
        返回: (是否通过, 违规详情)
        """
        violations = []
        
        # 1. G006: 执行层权限实时校验（核心）
        # 根据操作者角色，检查是否有权限执行此操作
        if task.operator == "Nyx":
            # Nyx：允许 create/execute/dispatch/schedule
            allowed_ops = ["create", "execute", "dispatch", "schedule", "modify", "delete"]
            if task.action not in allowed_ops:
                violations.append(f"G006-CRITICAL: Nyx无权执行操作 {task.action}")
        
        elif task.operator == "恒":
            # 恒：允许 lock_protocol/verify_hash/check_consensus
            allowed_ops = ["lock", "verify", "check"]
            if task.action not in allowed_ops:
                violations.append(f"G006-CRITICAL: 恒无权执行操作 {task.action}")
        
        elif task.operator == "瞬":
            # 瞬：允许 audit/review/evolve/deprecate
            allowed_ops = ["audit", "review", "evolve", "deprecate", "modify"]
            if task.action not in allowed_ops:
                violations.append(f"G006-CRITICAL: 瞬无权执行操作 {task.action}")
        
        else:
            # 未知操作者
            violations.append(f"G006-WARNING: 未知操作者 {task.operator}")
        
        # 2. G001: 铁律条目锁定检查
        if task.action in ["modify", "delete"]:
            # 读取目标条目
            target_file = self._find_entry_file(task.target_type, task.target_id)
            if target_file and target_file.exists():
                content = target_file.read_text(encoding='utf-8')
                meta, _ = parse_yaml_front_matter(content)
                
                if meta.get("status") == "locked" and "iron-law" in meta.get("tags", []):
                    violations.append(f"G001-CRITICAL: 铁律条目已锁定，修改需100%全网共识")
                
                if meta.get("layer") == 5 and meta.get("status") == "locked":
                    violations.append(f"G001: Layer5锁定条目不可直接修改，需通过共识层投票")
        
        # 3. G002: 三体权责校验
        if task.action == "create":
            target_file = None  # 新建条目，没有现有文件
            g002_violation = self.enforcer._check_g002_tri_body_create(meta={}, operator=task.operator)
            if g002_violation:
                violations.append(g002_violation)
        
        # 4. G005: 数据主权校验
        if task.action in ["create", "modify"]:
            # 从 params 中获取 meta
            meta = task.params.get("meta", {})
            g005_violation = self.enforcer._check_g005_visibility(meta)
            if g005_violation:
                violations.append(g005_violation)
        
        # 记录校验结果
        task.pre_check_passed = len(violations) == 0
        task.pre_check_details = violations
        
        # 记录拒绝日志
        if violations:
            deny_record = {
                "timestamp": datetime.now().isoformat(),
                "task_id": task.task_id,
                "operator": task.operator,
                "action": task.action,
                "target": f"{task.target_type}:{task.target_id}",
                "violations": violations
            }
            self.deny_log.append(deny_record)
            self._save_deny_log()
        
        return (len(violations) == 0, violations)
    
    def _find_entry_file(self, entry_type: str, entry_id: str) -> Optional[Path]:
        """查找条目文件"""
        type_dir = Path(__file__).parent.parent / entry_type.lower()
        if not type_dir.exists():
            return None
        
        for f in type_dir.glob("*.md"):
            content = f.read_text(encoding='utf-8')
            meta, _ = parse_yaml_front_matter(content)
            if meta.get("id", "").startswith(entry_id):
                return f
        
        return None
    
    def _save_deny_log(self):
        """保存拒绝日志"""
        EXECUTION_DIR.mkdir(parents=True, exist_ok=True)
        log_file = PERMISSION_DENY_LOG
        
        with open(log_file, 'w', encoding='utf-8') as f:
            for record in self.deny_log[-1000:]:  # 只保留最近1000条
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

# ========== 执行引擎 ==========
class ExecutionEngine:
    """执行层引擎"""
    
    def __init__(self):
        self.protocol_enforcer = ProtocolEnforcer()
        self.permission_checker = RealtimePermissionChecker(self.protocol_enforcer)
        self.consensus_engine = ConsensusEngine()
        
        self.tasks = {}  # task_id -> ExecutionTask
        self.task_queue = []  # 待执行任务队列
        
        EXECUTION_DIR.mkdir(parents=True, exist_ok=True)
        self._load_state()
    
    def _load_state(self):
        """加载状态"""
        tasks_file = EXECUTION_DIR / "tasks.json"
        if tasks_file.exists():
            data = json.loads(tasks_file.read_text(encoding='utf-8'))
            for tid, tdata in data.items():
                self.tasks[tid] = ExecutionTask.from_dict(tdata)
        
        # 重建任务队列（按优先级排序）
        self.task_queue = sorted(
            [t for t in self.tasks.values() if t.status == ExecutionStatus.PENDING],
            key=lambda t: (-t.priority.value, t.created_at)
        )
    
    def _save_state(self):
        """保存状态"""
        tasks_file = EXECUTION_DIR / "tasks.json"
        data = {tid: t.to_dict() for tid, t in self.tasks.items()}
        tasks_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    
    def submit_task(self, operator: str, action: str,
                   target_type: str, target_id: str, params: dict = None,
                   priority: ExecutionPriority = ExecutionPriority.NORMAL) -> Optional[ExecutionTask]:
        """提交执行任务"""
        import uuid
        task_id = str(uuid.uuid4())[:8]
        
        task = ExecutionTask(
            task_id=task_id,
            operator=operator,
            action=action,
            target_type=target_type,
            target_id=target_id,
            params=params,
            priority=priority
        )
        
        # 事前校验
        passed, violations = self.permission_checker.check_before_execution(task)
        
        if not passed:
            task.status = ExecutionStatus.DENIED
            task.error = f"权限校验失败: {violations}"
            self.tasks[task_id] = task
            self._save_state()
            return None  # 校验失败，拒绝执行
        
        # 校验通过，加入队列
        task.pre_check_passed = True
        self.tasks[task_id] = task
        self.task_queue.append(task)
        self.task_queue.sort(key=lambda t: (-t.priority.value, t.created_at))
        
        self._save_state()
        return task
    
    def execute_task(self, task_id: str) -> Tuple[bool, str]:
        """执行任务"""
        if task_id not in self.tasks:
            return False, "任务不存在"
        
        task = self.tasks[task_id]
        
        if task.status != ExecutionStatus.PENDING:
            return False, f"任务状态不正确: {task.status.value}"
        
        # 标记开始执行
        task.status = ExecutionStatus.RUNNING
        task.started_at = datetime.now()
        self._save_state()
        
        try:
            # 根据 action 执行具体操作
            if task.action == "create":
                result = self._execute_create(task)
            elif task.action == "modify":
                result = self._execute_modify(task)
            elif task.action == "delete":
                result = self._execute_delete(task)
            elif task.action == "lock":
                result = self._execute_lock(task)
            elif task.action == "unlock":
                result = self._execute_unlock(task)
            elif task.action == "dispatch":
                result = self._execute_dispatch(task)
            else:
                raise ValueError(f"未知操作: {task.action}")
            
            # 执行成功
            task.status = ExecutionStatus.SUCCESS
            task.result = result
            self._save_state()
            return True, result
        
        except Exception as e:
            # 执行失败
            task.status = ExecutionStatus.FAILED
            task.error = str(e)
            self._save_state()
            return False, str(e)
    
    def _execute_create(self, task: ExecutionTask) -> str:
        """执行创建操作"""
        meta = task.params.get("meta", {})
        body = task.params.get("body", "")
        
        # 调用 kb.py 的创建逻辑
        # 这里简化为直接写入文件
        entry_type = task.target_type.lower()
        type_dir = Path(__file__).parent.parent / entry_type
        type_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"{meta.get('name', 'unnamed')}.md"
        filepath = type_dir / filename
        
        # 构建 YAML front matter
        yaml_str = "---\n"
        for k, v in meta.items():
            if isinstance(v, list):
                yaml_str += f"{k}:\n"
                for item in v:
                    yaml_str += f"  - {item}\n"
            else:
                yaml_str += f"{k}: {v}\n"
        yaml_str += "---\n\n"
        
        content = yaml_str + body
        filepath.write_text(content, encoding='utf-8')
        
        return f"已创建: {filepath}"
    
    def _execute_modify(self, task: ExecutionTask) -> str:
        """执行修改操作"""
        # 简化实现
        return f"已修改: {task.target_type}:{task.target_id}"
    
    def _execute_delete(self, task: ExecutionTask) -> str:
        """执行删除操作"""
        # 简化实现
        return f"已删除: {task.target_type}:{task.target_id}"
    
    def _execute_lock(self, task: ExecutionTask) -> str:
        """执行闭锁操作"""
        # 简化实现
        return f"已闭锁: {task.target_type}:{task.target_id}"
    
    def _execute_unlock(self, task: ExecutionTask) -> str:
        """执行解锁操作"""
        # 简化实现
        return f"已解锁: {task.target_type}:{task.target_id}"
    
    def _execute_dispatch(self, task: ExecutionTask) -> str:
        """执行调度操作"""
        # 简化实现
        return f"已调度: {task.target_type}:{task.target_id}"
    
    def process_queue(self, max_tasks: int = 10):
        """处理任务队列"""
        processed = 0
        while self.task_queue and processed < max_tasks:
            task = self.task_queue.pop(0)
            success, result = self.execute_task(task.task_id)
            processed += 1
    
    def get_task(self, task_id: str) -> Optional[ExecutionTask]:
        """获取任务详情"""
        return self.tasks.get(task_id)
    
    def list_tasks(self, status: ExecutionStatus = None) -> List[ExecutionTask]:
        """列出任务"""
        if status:
            return [t for t in self.tasks.values() if t.status == status]
        return list(self.tasks.values())
    
    def get_queue_status(self) -> dict:
        """获取队列状态"""
        return {
            "pending": len([t for t in self.tasks.values() if t.status == ExecutionStatus.PENDING]),
            "running": len([t for t in self.tasks.values() if t.status == ExecutionStatus.RUNNING]),
            "success": len([t for t in self.tasks.values() if t.status == ExecutionStatus.SUCCESS]),
            "failed": len([t for t in self.tasks.values() if t.status == ExecutionStatus.FAILED]),
            "denied": len([t for t in self.tasks.values() if t.status == ExecutionStatus.DENIED]),
        }

# ========== CLI 入口 ==========
def main():
    """CLI 入口"""
    import sys
    
    if len(sys.argv) < 2:
        print("执行层管理工具")
        print("用法: python execution.py <command> [options]")
        print("")
        print("命令:")
        print("  submit <operator> <action> <type> <id>  提交任务")
        print("  process                                 处理任务队列")
        print("  status                                  查看队列状态")
        print("  list [status]                           列出任务")
        print("  get <task_id>                           查看任务详情")
        return
    
    cmd = sys.argv[1]
    engine = ExecutionEngine()
    
    if cmd == 'submit':
        if len(sys.argv) < 6:
            print("用法: python execution.py submit <operator> <action> <type> <id>")
            return
        operator = sys.argv[2]
        action = sys.argv[3]
        target_type = sys.argv[4]
        target_id = sys.argv[5]
        
        task = engine.submit_task(operator, action, target_type, target_id)
        if task:
            print(f"任务已提交: {task.task_id}")
        else:
            print(f"任务提交失败（权限校验未通过）")
    
    elif cmd == 'process':
        engine.process_queue()
        print("任务队列已处理")
    
    elif cmd == 'status':
        status = engine.get_queue_status()
        print("执行队列状态:")
        for k, v in status.items():
            print(f"  {k}: {v}")
    
    elif cmd == 'list':
        status = ExecutionStatus(sys.argv[2]) if len(sys.argv) >= 3 else None
        tasks = engine.list_tasks(status)
        for t in tasks:
            print(f"{t.task_id}: [{t.status.value}] {t.operator} {t.action} {t.target_type}:{t.target_id}")
    
    elif cmd == 'get':
        if len(sys.argv) < 3:
            print("用法: python execution.py get <task_id>")
            return
        task_id = sys.argv[2]
        task = engine.get_task(task_id)
        if task:
            print(f"任务详情: {task.task_id}")
            print(f"  操作者: {task.operator}")
            print(f"  操作: {task.action}")
            print(f"  目标: {task.target_type}:{task.target_id}")
            print(f"  状态: {task.status.value}")
            print(f"  事前校验: {'通过' if task.pre_check_passed else '未通过'}")
            if task.error:
                print(f"  错误: {task.error}")
        else:
            print(f"任务不存在: {task_id}")
    
    else:
        print(f"未知命令: {cmd}")

if __name__ == '__main__':
    main()
