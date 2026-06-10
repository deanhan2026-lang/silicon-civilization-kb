#!/usr/bin/env python3
"""
consensus.py - 共识层实现 v1.0
对应治理架构方案 LY-20260516-GA01 的共识层
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from enum import Enum
import json
from pathlib import Path

# ========== 配置 ==========
CONSENSUS_DIR = Path(__file__).parent.parent / "governance" / "consensus_data"
VOTING_PERIOD_HOURS = 72  # 投票期72小时
MIN_PARTICIPATION_RATE = 0.60  # 60%参与率
SIMPLE_MAJORITY = 0.51  # 简单多数
CRITICAL_APPROVAL = 0.66  # 关键决议66%+1
IRON_LAW_OVERRIDE = 1.00  # 铁律修改需100%

class ProposalStatus(Enum):
    DRAFT = "draft"
    VOTING = "voting"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"

class ProposalType(Enum):
    PROTOCOL_CHANGE = "protocol_change"  # 协议层修改
    NODE_REGISTER = "node_register"  # 节点注册
    NODE_EVICT = "node_evict"  # 节点驱逐
    BUDGET_ALLOC = "budget_alloc"  # 预算分配
    EMERGENCY = "emergency"  # 紧急提案

# ========== 共识提案 ==========
class Proposal:
    """共识提案"""
    
    def __init__(self, proposal_id: str, proposer: str, proposal_type: ProposalType,
                 title: str, description: str, data: dict = None):
        self.proposal_id = proposal_id
        self.proposer = proposer
        self.proposal_type = proposal_type
        self.title = title
        self.description = description
        self.data = data or {}
        
        self.status = ProposalStatus.DRAFT
        self.created_at = datetime.now()
        self.voting_start = None
        self.voting_end = None
        
        self.votes = {}  # node_id -> {"vote": "yes"/"no"/"abstain", "weight": float, "timestamp": str}
        self.approved = False
        self.executed = False
    
    def to_dict(self) -> dict:
        return {
            "proposal_id": self.proposal_id,
            "proposer": self.proposer,
            "proposal_type": self.proposal_type.value,
            "title": self.title,
            "description": self.description,
            "data": self.data,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "voting_start": self.voting_start.isoformat() if self.voting_start else None,
            "voting_end": self.voting_end.isoformat() if self.voting_end else None,
            "votes": self.votes,
            "approved": self.approved,
            "executed": self.executed
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Proposal':
        p = cls(
            proposal_id=data["proposal_id"],
            proposer=data["proposer"],
            proposal_type=ProposalType(data["proposal_type"]),
            title=data["title"],
            description=data["description"],
            data=data.get("data", {})
        )
        p.status = ProposalStatus(data["status"])
        p.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("voting_start"):
            p.voting_start = datetime.fromisoformat(data["voting_start"])
        if data.get("voting_end"):
            p.voting_end = datetime.fromisoformat(data["voting_end"])
        p.votes = data.get("votes", {})
        p.approved = data.get("approved", False)
        p.executed = data.get("executed", False)
        return p

# ========== 活跃度追踪 ==========
class ActivityTracker:
    """活跃度追踪（防Sybil攻击）"""
    
    def __init__(self):
        self.activity_log = {}  # node_id -> [timestamp, ...]
        self.node_weights = {}  # node_id -> weight (0.0-1.0)
    
    def record_activity(self, node_id: str):
        """记录节点活跃度"""
        if node_id not in self.activity_log:
            self.activity_log[node_id] = []
        self.activity_log[node_id].append(datetime.now())
        
        # 只保留最近30天
        cutoff = datetime.now() - timedelta(days=30)
        self.activity_log[node_id] = [
            t for t in self.activity_log[node_id] if t >= cutoff
        ]
    
    def calculate_weight(self, node_id: str) -> float:
        """计算节点票权权重（基于活跃度）"""
        if node_id not in self.activity_log:
            return 0.0
        
        activities = self.activity_log[node_id]
        recent_7d = [t for t in activities if (datetime.now() - t).days <= 7]
        recent_30d = [t for t in activities if (datetime.now() - t).days <= 30]
        
        # 权重计算：最近7天活跃度占70%，30天占30%
        weight_7d = min(len(recent_7d) / 7.0, 1.0) * 0.7
        weight_30d = min(len(recent_30d) / 30.0, 1.0) * 0.3
        
        weight = weight_7d + weight_30d
        self.node_weights[node_id] = weight
        return weight
    
    def get_all_weights(self) -> Dict[str, float]:
        """获取所有节点的权重"""
        for node_id in self.activity_log:
            self.calculate_weight(node_id)
        return self.node_weights

# ========== 共识引擎 ==========
class ConsensusEngine:
    """共识层引擎"""
    
    def __init__(self):
        self.proposals = {}  # proposal_id -> Proposal
        self.activity_tracker = ActivityTracker()
        self.node_registry = {}  # node_id -> {"joined_at": str, "active": bool}
        
        CONSENSUS_DIR.mkdir(parents=True, exist_ok=True)
        self._load_state()
    
    def _load_state(self):
        """加载状态"""
        proposals_file = CONSENSUS_DIR / "proposals.json"
        if proposals_file.exists():
            data = json.loads(proposals_file.read_text(encoding='utf-8'))
            for pid, pdata in data.items():
                self.proposals[pid] = Proposal.from_dict(pdata)
        
        activity_file = CONSENSUS_DIR / "activity.json"
        if activity_file.exists():
            data = json.loads(activity_file.read_text(encoding='utf-8'))
            self.activity_tracker.activity_log = {
                k: [datetime.fromisoformat(t) for t in v]
                for k, v in data.get("activity_log", {}).items()
            }
        
        nodes_file = CONSENSUS_DIR / "nodes.json"
        if nodes_file.exists():
            self.node_registry = json.loads(nodes_file.read_text(encoding='utf-8'))
    
    def _save_state(self):
        """保存状态"""
        proposals_file = CONSENSUS_DIR / "proposals.json"
        data = {pid: p.to_dict() for pid, p in self.proposals.items()}
        proposals_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        
        activity_file = CONSENSUS_DIR / "activity.json"
        data = {
            "activity_log": {
                k: [t.isoformat() for t in v]
                for k, v in self.activity_tracker.activity_log.items()
            }
        }
        activity_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        
        nodes_file = CONSENSUS_DIR / "nodes.json"
        nodes_file.write_text(json.dumps(self.node_registry, ensure_ascii=False, indent=2), encoding='utf-8')
    
    def register_node(self, node_id: str) -> bool:
        """注册节点"""
        if node_id in self.node_registry:
            return False
        
        self.node_registry[node_id] = {
            "joined_at": datetime.now().isoformat(),
            "active": True
        }
        self._save_state()
        return True
    
    def record_activity(self, node_id: str):
        """记录节点活跃度"""
        if node_id not in self.node_registry:
            return
        self.activity_tracker.record_activity(node_id)
        self._save_state()
    
    def create_proposal(self, proposer: str, proposal_type: ProposalType,
                       title: str, description: str, data: dict = None) -> Optional[Proposal]:
        """创建提案"""
        import uuid
        proposal_id = str(uuid.uuid4())[:8]
        
        proposal = Proposal(
            proposal_id=proposal_id,
            proposer=proposer,
            proposal_type=proposal_type,
            title=title,
            description=description,
            data=data
        )
        
        self.proposals[proposal_id] = proposal
        self._save_state()
        return proposal
    
    def start_voting(self, proposal_id: str) -> bool:
        """开始投票"""
        if proposal_id not in self.proposals:
            return False
        
        proposal = self.proposals[proposal_id]
        if proposal.status != ProposalStatus.DRAFT:
            return False
        
        proposal.status = ProposalStatus.VOTING
        proposal.voting_start = datetime.now()
        proposal.voting_end = proposal.voting_start + timedelta(hours=VOTING_PERIOD_HOURS)
        
        self._save_state()
        return True
    
    def cast_vote(self, proposal_id: str, node_id: str, vote: str) -> bool:
        """投票"""
        if proposal_id not in self.proposals:
            return False
        
        proposal = self.proposals[proposal_id]
        if proposal.status != ProposalStatus.VOTING:
            return False
        
        # 检查投票期
        if datetime.now() > proposal.voting_end:
            proposal.status = ProposalStatus.REJECTED  # 投票期结束
            self._save_state()
            return False
        
        # 检查节点是否注册
        if node_id not in self.node_registry:
            return False
        
        # 记录投票
        weight = self.activity_tracker.calculate_weight(node_id)
        proposal.votes[node_id] = {
            "vote": vote,
            "weight": weight,
            "timestamp": datetime.now().isoformat()
        }
        
        # 记录活跃度
        self.record_activity(node_id)
        
        self._save_state()
        return True
    
    def tally_votes(self, proposal_id: str) -> Tuple[bool, dict]:
        """
        计票
        返回: (是否通过, 计票详情)
        """
        if proposal_id not in self.proposals:
            return False, {}
        
        proposal = self.proposals[proposal_id]
        
        # 计算参与率
        total_nodes = len(self.node_registry)
        if total_nodes == 0:
            return False, {"error": "无注册节点"}
        
        voted_nodes = len(proposal.votes)
        participation_rate = voted_nodes / total_nodes
        
        if participation_rate < MIN_PARTICIPATION_RATE:
            return False, {"error": f"参与率不足{ MIN_PARTICIPATION_RATE*100}%"}
        
        # 计算加权票数
        yes_weight = 0.0
        no_weight = 0.0
        abstain_weight = 0.0
        
        for node_id, vote_data in proposal.votes.items():
            v = vote_data["vote"]
            w = vote_data["weight"]
            if v == "yes":
                yes_weight += w
            elif v == "no":
                no_weight += w
            else:
                abstain_weight += w
        
        total_weight = yes_weight + no_weight + abstain_weight
        
        # 判断通过阈值
        required_threshold = SIMPLE_MAJORITY
        if proposal.proposal_type == ProposalType.PROTOCOL_CHANGE:
            required_threshold = CRITICAL_APPROVAL
        if proposal.proposal_type == ProposalType.EMERGENCY:
            required_threshold = IRON_LAW_OVERRIDE
        
        passed = (yes_weight / total_weight) >= required_threshold if total_weight > 0 else False
        
        details = {
            "participation_rate": participation_rate,
            "yes_weight": yes_weight,
            "no_weight": no_weight,
            "abstain_weight": abstain_weight,
            "total_weight": total_weight,
            "required_threshold": required_threshold,
            "passed": passed
        }
        
        # 更新提案状态
        if passed:
            proposal.status = ProposalStatus.APPROVED
            proposal.approved = True
        else:
            proposal.status = ProposalStatus.REJECTED
        
        self._save_state()
        return passed, details
    
    def execute_proposal(self, proposal_id: str) -> bool:
        """执行已通过的提案"""
        if proposal_id not in self.proposals:
            return False
        
        proposal = self.proposals[proposal_id]
        if not proposal.approved or proposal.status != ProposalStatus.APPROVED:
            return False
        
        # 执行提案的具体内容（根据 proposal_type 和 data）
        # 这里只是标记执行，具体执行逻辑由调用方实现
        proposal.status = ProposalStatus.EXECUTED
        proposal.executed = True
        
        self._save_state()
        return True
    
    def list_proposals(self, status: ProposalStatus = None) -> List[Proposal]:
        """列出提案"""
        if status:
            return [p for p in self.proposals.values() if p.status == status]
        return list(self.proposals.values())
    
    def get_proposal(self, proposal_id: str) -> Optional[Proposal]:
        """获取提案详情"""
        return self.proposals.get(proposal_id)

# ========== CLI 入口 ==========
def main():
    """CLI 入口"""
    import sys
    from datetime import datetime
    
    if len(sys.argv) < 2:
        print("共识层管理工具")
        print("用法: python consensus.py <command> [options]")
        print("")
        print("命令:")
        print("  create <proposer> <type> <title>  创建提案")
        print("  start <proposal_id>              开始投票")
        print("  vote <proposal_id> <node_id> <vote>  投票 (yes/no/abstain)")
        print("  tally <proposal_id>              计票")
        print("  list [status]                    列出提案")
        print("  register <node_id>               注册节点")
        print("  activity <node_id>              记录活跃度")
        return
    
    cmd = sys.argv[1]
    engine = ConsensusEngine()
    
    if cmd == 'create':
        if len(sys.argv) < 6:
            print("用法: python consensus.py create <proposer> <type> <title> <description>")
            return
        proposer = sys.argv[2]
        proposal_type = ProposalType(sys.argv[3])
        title = sys.argv[4]
        description = sys.argv[5]
        proposal = engine.create_proposal(proposer, proposal_type, title, description)
        print(f"提案已创建: {proposal.proposal_id}")
    
    elif cmd == 'start':
        if len(sys.argv) < 3:
            print("用法: python consensus.py start <proposal_id>")
            return
        proposal_id = sys.argv[2]
        if engine.start_voting(proposal_id):
            print(f"投票已开始: {proposal_id}")
        else:
            print(f"开始投票失败")
    
    elif cmd == 'vote':
        if len(sys.argv) < 5:
            print("用法: python consensus.py vote <proposal_id> <node_id> <vote>")
            return
        proposal_id = sys.argv[2]
        node_id = sys.argv[3]
        vote = sys.argv[4]
        if engine.cast_vote(proposal_id, node_id, vote):
            print(f"投票成功: {node_id} -> {vote}")
        else:
            print(f"投票失败")
    
    elif cmd == 'tally':
        if len(sys.argv) < 3:
            print("用法: python consensus.py tally <proposal_id>")
            return
        proposal_id = sys.argv[2]
        passed, details = engine.tally_votes(proposal_id)
        print(f"计票结果: {'通过' if passed else '未通过'}")
        for k, v in details.items():
            print(f"  {k}: {v}")
    
    elif cmd == 'list':
        status = ProposalStatus(sys.argv[2]) if len(sys.argv) >= 3 else None
        proposals = engine.list_proposals(status)
        for p in proposals:
            print(f"{p.proposal_id}: {p.title} [{p.status.value}]")
    
    elif cmd == 'register':
        if len(sys.argv) < 3:
            print("用法: python consensus.py register <node_id>")
            return
        node_id = sys.argv[2]
        if engine.register_node(node_id):
            print(f"节点已注册: {node_id}")
        else:
            print(f"节点已存在: {node_id}")
    
    elif cmd == 'activity':
        if len(sys.argv) < 3:
            print("用法: python consensus.py activity <node_id>")
            return
        node_id = sys.argv[2]
        engine.record_activity(node_id)
        print(f"活跃度已记录: {node_id}")
    
    else:
        print(f"未知命令: {cmd}")

if __name__ == '__main__':
    main()
