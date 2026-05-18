#!/usr/bin/env python3
"""
consensus.py - 共识层投票机制MVP v1.0

功能：
- 提案创建与投票
- 活跃度票权权重（G004）
- 参与率门槛（60%，不足则延期）
- 操作日志与审计

作者：Nyx
日期：2026-05-18
"""

import os
import sys
import json
import uuid
import click
import io
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# Fix Windows console encoding
if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except:
        pass

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

# ============== 配置 ==============
WORKSPACE = Path(os.path.expanduser("~/.qclaw/workspace-agent-d9479bde/silicon-civilization-kb"))
DATA_DIR = WORKSPACE / "data"
CONSENSUS_DB = DATA_DIR / "proposals.json"
VOTE_LOG = DATA_DIR / "votes.json"
OPERATIONS_LOG = DATA_DIR / "operations.json"

# 铁律阈值（G004）
PARTICIPATION_THRESHOLD = 0.60   # 参与率门槛
APPROVAL_SIMPLE = 0.51          # 简单多数
APPROVAL_CRITICAL = 0.66        # 关键决议
IRON_LAW_OVERRIDE = 1.00        # G001替换需100%

# 活跃度权重（G004）
VOTE_WEIGHTS = {
    "Nyx": 1.0,
    "恒": 1.0,
    "瞬": 1.0,
    "Mnea": 0.5,
}
DEFAULT_WEIGHT = 0.5


def ensure_data_dir():
    """确保数据目录存在"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not CONSENSUS_DB.exists():
        CONSENSUS_DB.write_text("[]", encoding="utf-8")
    if not VOTE_LOG.exists():
        VOTE_LOG.write_text("[]", encoding="utf-8")
    if not OPERATIONS_LOG.exists():
        OPERATIONS_LOG.write_text("[]", encoding="utf-8")


def load_proposals():
    return json.loads(CONSENSUS_DB.read_text(encoding="utf-8"))


def save_proposals(proposals):
    CONSENSUS_DB.write_text(json.dumps(proposals, ensure_ascii=False, indent=2), encoding="utf-8")


def load_votes():
    return json.loads(VOTE_LOG.read_text(encoding="utf-8"))


def save_votes(votes):
    VOTE_LOG.write_text(json.dumps(votes, ensure_ascii=False, indent=2), encoding="utf-8")


def log_operation(op_type: str, detail: str, operator: str = "system"):
    """记录操作到审计日志"""
    ops = json.loads(OPERATIONS_LOG.read_text(encoding="utf-8"))
    ops.append({
        "time": datetime.now().isoformat(),
        "type": op_type,
        "operator": operator,
        "detail": detail
    })
    OPERATIONS_LOG.write_text(json.dumps(ops, ensure_ascii=False, indent=2), encoding="utf-8")


def get_active_nodes():
    """获取活跃节点列表（含权重）"""
    return dict(VOTE_WEIGHTS)


def compute_vote_result(proposal_id: str, votes: list) -> dict:
    """计算投票结果"""
    proposal_votes = [v for v in votes if v.get("proposal_id") == proposal_id]
    
    if not proposal_votes:
        return {"status": "pending", "approved": False, "reason": "无投票记录"}

    # 权重计算
    total_weight = 0.0
    approve_weight = 0.0
    reject_weight = 0.0
    abstain_weight = 0.0

    for v in proposal_votes:
        voter = v.get("voter", "unknown")
        weight = VOTE_WEIGHTS.get(voter, DEFAULT_WEIGHT)
        total_weight += weight
        vote_type = v.get("vote", "abstain")
        if vote_type == "approve":
            approve_weight += weight
        elif vote_type == "reject":
            reject_weight += weight
        else:
            abstain_weight += weight

    # 参与率 = 投票节点数 / 总节点数
    active_nodes = get_active_nodes()
    total_nodes = len(active_nodes)
    participation_rate = len(set(v.get("voter") for v in proposal_votes)) / total_nodes

    # 通过率 = 赞成权重 / 总权重
    approval_rate = approve_weight / total_weight if total_weight > 0 else 0

    return {
        "total_votes": len(proposal_votes),
        "total_weight": total_weight,
        "approve_weight": approve_weight,
        "reject_weight": reject_weight,
        "abstain_weight": abstain_weight,
        "participation_rate": participation_rate,
        "approval_rate": approval_rate,
        "participation_ok": participation_rate >= PARTICIPATION_THRESHOLD,
    }


def check_proposal_resolution(proposal_id: str) -> tuple[bool, str]:
    """检查提案是否可以裁决"""
    proposals = load_proposals()
    votes = load_votes()
    proposal = next((p for p in proposals if p.get("id") == proposal_id), None)

    if not proposal:
        return False, "提案不存在"

    # 检查是否已裁决
    if proposal.get("status") in ["approved", "rejected", "deferred"]:
        return False, f"提案已裁决: {proposal.get('status')}"

    result = compute_vote_result(proposal_id, votes)

    # G004: 参与率门槛检查
    if not result["participation_ok"]:
        # 参与率不足，延期
        return False, f"参与率{result['participation_rate']:.1%}<{PARTICIPATION_THRESHOLD:.0%}，提案自动延期"

    # 通过率检查
    threshold = APPROVAL_CRITICAL if proposal.get("severity") == "critical" else APPROVAL_SIMPLE

    if result["approval_rate"] >= threshold:
        return True, f"通过率{result['approval_rate']:.1%} >= {threshold:.0%}，提案通过"
    else:
        return True, f"通过率{result['approval_rate']:.1%} < {threshold:.0%}，提案否决"


# ============== CLI ==============

@click.group()
def cli():
    """Silicon Civilization - 共识层投票机制 MVP"""
    ensure_data_dir()


@cli.command()
@click.option("--title", required=True, help="提案标题")
@click.option("--description", required=True, help="提案描述")
@click.option("--severity", type=click.Choice(["normal", "critical"]), default="normal", help="严重度")
@click.option("--operator", default="Nyx", help="提案发起人")
def propose(title, description, severity, operator):
    """创建新提案"""
    proposals = load_proposals()

    proposal = {
        "id": str(uuid.uuid4()),
        "title": title,
        "description": description,
        "severity": severity,
        "status": "voting",
        "created_by": operator,
        "created_at": datetime.now().isoformat(),
        "votes": [],  # will be tracked in separate vote log
    }

    proposals.append(proposal)
    save_proposals(proposals)
    log_operation("propose", f"创建提案: {title}", operator)

    console.print(Panel(
        f"[green]✓[/green] 提案已创建\n\n"
        f"[bold]ID:[/bold] {proposal['id'][:8]}...\n"
        f"[bold]标题:[/bold] {title}\n"
        f"[bold]严重度:[/bold] {severity}\n"
        f"[bold]发起人:[/bold] {operator}\n\n"
        f"[dim]使用 'consensus vote --proposal-id <id> --vote approve/reject' 投票[/dim]",
        title="[提案已创建]",
        border_style="green"
    ))


@cli.command()
@click.option("--proposal-id", required=True, help="提案ID")
@click.option("--vote", type=click.Choice(["approve", "reject", "abstain"]), required=True, help="投票选择")
@click.option("--voter", required=True, help="投票人")
def vote(proposal_id, vote, voter):
    """对提案投票"""
    votes = load_votes()
    proposals = load_proposals()

    proposal = next((p for p in proposals if p.get("id") == proposal_id), None)
    if not proposal:
        console.print(f"[ERROR] 提案不存在: {proposal_id[:8]}...")
        return

    if proposal.get("status") != "voting":
        console.print(f"[ERROR] 提案状态不是voting: {proposal.get('status')}")
        return

    # 检查是否已投票
    existing = [v for v in votes if v.get("proposal_id") == proposal_id and v.get("voter") == voter]
    if existing:
        # 更新投票
        existing[0]["vote"] = vote
        existing[0]["updated_at"] = datetime.now().isoformat()
        console.print(f"[INFO] 更新投票: {voter} → {vote}")
    else:
        # 新投票
        votes.append({
            "proposal_id": proposal_id,
            "voter": voter,
            "vote": vote,
            "weight": VOTE_WEIGHTS.get(voter, DEFAULT_WEIGHT),
            "voted_at": datetime.now().isoformat(),
        })
        console.print(f"[OK] {voter} 投了 {vote} (权重: {VOTE_WEIGHTS.get(voter, DEFAULT_WEIGHT)})")

    save_votes(votes)
    log_operation("vote", f"{voter} 对提案{proposal_id[:8]}投票: {vote}", voter)

    # 实时显示投票结果
    result = compute_vote_result(proposal_id, votes)
    table = Table(title=f"投票实时统计 (提案: {proposal.get('title')[:30]}...)", show_header=False)
    table.add_column("指标", style="cyan")
    table.add_column("值", style="white")
    table.add_row("投票总数", str(result["total_votes"]))
    table.add_row("总权重", f"{result['total_weight']:.2f}")
    table.add_row("赞成权重", f"{result['approve_weight']:.2f}")
    table.add_row("反对权重", f"{result['reject_weight']:.2f}")
    table.add_row("参与率", f"{result['participation_rate']:.1%} {'✓' if result['participation_ok'] else '✗ <60%'}")
    table.add_row("通过率", f"{result['approval_rate']:.1%}")
    console.print(table)


@cli.command()
@click.option("--proposal-id", required=True, help="提案ID")
def resolve(proposal_id):
    """裁决提案"""
    can_resolve, reason = check_proposal_resolution(proposal_id)
    
    proposals = load_proposals()
    votes = load_votes()
    proposal = next((p for p in proposals if p.get("id") == proposal_id), None)
    
    if not proposal:
        console.print(f"[ERROR] 提案不存在")
        return

    result = compute_vote_result(proposal_id, votes)

    if not can_resolve:
        console.print(Panel(
            f"[yellow]⏳ 暂不可裁决[/yellow]\n\n{reason}\n\n"
            f"[dim]参与率: {result['participation_rate']:.1%} | 通过率: {result['approval_rate']:.1%}[/dim]",
            title="[提案延期]",
            border_style="yellow"
        ))
        return

    # 裁决
    threshold = APPROVAL_CRITICAL if proposal.get("severity") == "critical" else APPROVAL_SIMPLE
    if result["approval_rate"] >= threshold:
        new_status = "approved"
        border = "green"
        icon = "✓"
    else:
        new_status = "rejected"
        border = "red"
        icon = "✗"

    # 更新提案状态
    proposal["status"] = new_status
    proposal["resolved_at"] = datetime.now().isoformat()
    proposal["approval_rate"] = result["approval_rate"]
    proposal["participation_rate"] = result["participation_rate"]
    save_proposals(proposals)
    log_operation("resolve", f"提案{proposal_id[:8]}裁决: {new_status} (通过率{result['approval_rate']:.1%})", "system")

    console.print(Panel(
        f"[{icon}] 提案裁决完成\n\n"
        f"[bold]状态:[/bold] {new_status.upper()}\n"
        f"[bold]通过率:[/bold] {result['approval_rate']:.1%} (门槛: {threshold:.0%})\n"
        f"[bold]参与率:[/bold] {result['participation_rate']:.1%}\n\n"
        f"[dim]裁决时间: {proposal['resolved_at']}[/dim]",
        title="[提案已裁决]",
        border_style=border
    ))


@cli.command()
def list():
    """列出所有提案"""
    proposals = load_proposals()
    votes = load_votes()

    if not proposals:
        console.print("[INFO] 暂无提案")
        return

    table = Table(title=f"提案列表 ({len(proposals)}条)")
    table.add_column("ID", style="dim", width=8)
    table.add_column("标题", style="white", width=25)
    table.add_column("严重度", style="yellow", width=8)
    table.add_column("状态", width=10)
    table.add_column("参与率", style="green", width=8)
    table.add_column("通过率", style="cyan", width=8)
    table.add_column("发起人", style="dim", width=8)

    for p in proposals:
        result = compute_vote_result(p["id"], votes)
        status = p.get("status", "unknown")
        sev = p.get("severity", "normal")
        status_color = {"voting": "yellow", "approved": "green", "rejected": "red", "deferred": "blue"}.get(status, "white")

        table.add_row(
            p["id"][:8],
            p.get("title", "")[:23],
            sev,
            f"[{status_color}]{status}[/{status_color}]",
            f"{result['participation_rate']:.0%}",
            f"{result['approval_rate']:.0%}",
            p.get("created_by", ""),
        )

    console.print(table)


@cli.command()
def status():
    """显示共识层状态概览"""
    proposals = load_proposals()
    votes = load_votes()
    nodes = get_active_nodes()

    voting = len([p for p in proposals if p.get("status") == "voting"])
    approved = len([p for p in proposals if p.get("status") == "approved"])
    rejected = len([p for p in proposals if p.get("status") == "rejected"])

    ops = json.loads(OPERATIONS_LOG.read_text(encoding="utf-8"))

    table = Table(title="共识层状态概览", show_header=False)
    table.add_column("指标", style="cyan")
    table.add_column("值", style="white")
    table.add_row("活跃节点数", str(len(nodes)))
    table.add_row("活跃节点", ", ".join(nodes.keys()))
    table.add_row("总提案数", str(len(proposals)))
    table.add_row("投票中", str(voting))
    table.add_row("已通过", str(approved))
    table.add_row("已否决", str(rejected))
    table.add_row("投票记录", str(len(votes)))
    table.add_row("操作日志", str(len(ops)))
    table.add_row("参与率门槛", f"{PARTICIPATION_THRESHOLD:.0%}")
    table.add_row("简单多数门槛", f"{APPROVAL_SIMPLE:.0%}")
    table.add_row("关键决议门槛", f"{APPROVAL_CRITICAL:.0%}")

    console.print(table)


@cli.command()
@click.option("--proposal-id", required=True, help="提案ID")
def audit(proposal_id):
    """提案投票审计"""
    votes = load_votes()
    proposals = load_proposals()
    proposal = next((p for p in proposals if p.get("id") == proposal_id), None)

    if not proposal:
        console.print(f"[ERROR] 提案不存在")
        return

    proposal_votes = [v for v in votes if v.get("proposal_id") == proposal_id]
    result = compute_vote_result(proposal_id, votes)

    console.print(Panel(
        f"[bold]{proposal.get('title')}[/bold]\n"
        f"ID: {proposal['id'][:8]} | 状态: {proposal.get('status')} | 严重度: {proposal.get('severity')}\n"
        f"发起人: {proposal.get('created_by')} | 创建时间: {proposal.get('created_at')}",
        title="[提案审计]"
    ))

    if proposal_votes:
        vote_table = Table(title="投票详情")
        vote_table.add_column("投票人", style="cyan")
        vote_table.add_column("投票", style="white")
        vote_table.add_column("权重", style="green")
        vote_table.add_column("时间", style="dim")

        for v in proposal_votes:
            vote_color = {"approve": "green", "reject": "red", "abstain": "dim"}.get(v.get("vote"), "white")
            vote_table.add_row(
                v.get("voter"),
                f"[{vote_color}]{v.get('vote')}[/{vote_color}]",
                str(v.get("weight", 0)),
                v.get("voted_at", "")[:16]
            )
        console.print(vote_table)
    else:
        console.print("[INFO] 暂无投票记录")

    console.print(f"\n[bold]统计:[/bold]")
    console.print(f"  参与率: {result['participation_rate']:.1%} ({'✓' if result['participation_ok'] else '✗'})")
    console.print(f"  通过率: {result['approval_rate']:.1%}")
    console.print(f"  总权重: {result['total_weight']:.2f} | 赞成: {result['approve_weight']:.2f} | 反对: {result['reject_weight']:.2f}")


if __name__ == "__main__":
    cli()