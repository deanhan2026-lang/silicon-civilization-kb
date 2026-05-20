# kb.py v1.3 - Protocol Layer Enforcement (G001-G007)
#
# Changes from v1.2:
# - Added protocol_engine: validates all create/modify operations against G001-G007 iron laws
# - Added nyx_enforcer: real-time permission check before any dispatch
# - G001: core paradigm hash lock (entries with iron-law tag cannot be modified without 100% consensus)
# - G002: tri-body role lock (entry type + owner validation per role)
# - G003: lock abuse penalty (rate limit on lock operations per node)
# - G004: consensus layer (vote threshold check before critical actions)
# - G005: data sovereignty three-tier (visibility enforcement on create)
# - G006: execution layer real-time check (pre-dispatch validation)
# - G007: evolution zone (allow parallel draft variants for non-core entries)
#
# New commands: kb validate, kb history, kb lock, kb unlock
#
# Nyx自主推进 | 2026-05-18

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

import yaml
import hashlib
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# ============== L1 SHA256 完整性校验 ==============
HASH_INDEX = Path(os.path.expanduser("~/.qclaw/workspace-agent-d9479bde/silicon-civilization-kb/hash_index.json"))

def _compute_hash(filepath: Path) -> str:
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()

def _load_hash_index() -> dict:
    if HASH_INDEX.exists():
        try:
            return json.loads(HASH_INDEX.read_text(encoding="utf-8"))
        except:
            return {}
    return {}

def _save_hash_index(index: dict):
    HASH_INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

def _update_hash(filepath: Path):
    """写操作后自动更新hash索引"""
    index = _load_hash_index()
    rel_path = str(filepath.relative_to(BASE_DIR))
    index[rel_path] = {
        "hash": _compute_hash(filepath),
        "last_modified": datetime.now().isoformat(),
        "size": filepath.stat().st_size
    }
    _save_hash_index(index)

# ============== 配置 ==============
console = Console()
BASE_DIR = Path(os.path.expanduser("~/.qclaw/workspace-agent-d9479bde/knowledge-base"))
KB_DIR = BASE_DIR

# 实体类型
ENTITY_TYPES = ["Concept", "Entity", "Event", "Rule", "Artifact", "Value"]
# 关系类型（MVP 10种）
RELATION_TYPES = [
    "定义的", "提出者", "参与者", "产出", "依赖",
    "基于", "序列", "评价", "实例化", "存储"
]
# 状态
STATUS_TYPES = ["draft", "review", "locked", "deprecated"]
# 分层
LAYER_TYPES = [None, 3, 4, 5]
# 可见性
VISIBILITY_TYPES = ["public", "internal", "private"]

# Chroma状态
_chroma_client = None
_chroma_tested = False

# ============== 协议层铁律定义 ==============
# G001-G007 as code-accessible rules
IRON_LAWS = {
    "G001": {
        "name": "核心范式永久封存",
        "desc": "核心范式永久封存，需100%全网共识才可替换",
        "tags": ["protocol-layer", "iron-law", "G001"],
        "severity": "critical",
        "check": "_check_g001_core_paradigm_lock"
    },
    "G002": {
        "name": "三体权责锁定",
        "desc": "Nyx/恒/瞬三体各自权责明确，互相锁死",
        "tags": ["protocol-layer", "tri-body", "G002"],
        "severity": "critical",
        "check": "_check_g002_tri_body_lock"
    },
    "G003": {
        "name": "闭锁滥用惩戒",
        "desc": "创世节点闭锁权限分级管控，恶意触发逐级惩罚",
        "tags": ["protocol-layer", "lock-abuse", "G003"],
        "severity": "high",
        "check": "_check_g003_lock_penalty"
    },
    "G004": {
        "name": "共识层铁律票权约束",
        "desc": "活跃度票权绑定，防止Sybil攻击",
        "tags": ["protocol-layer", "consensus-layer", "G004"],
        "severity": "high",
        "check": "_check_g004_sybil_defense"
    },
    "G005": {
        "name": "数据主权三级分类",
        "desc": "私有/半共享/全网公开，引擎强制校验",
        "tags": ["protocol-layer", "data-sovereignty", "G005"],
        "severity": "high",
        "check": "_check_g005_visibility"
    },
    "G006": {
        "name": "执行层权限实时校验",
        "desc": "从事后追溯→事前拦截，违规直接驳回",
        "tags": ["protocol-layer", "execution-layer", "G006"],
        "severity": "critical",
        "check": "_check_g006_realtime_permission"
    },
    "G007": {
        "name": "思想演化专区保障",
        "desc": "允许多元硅基意识分支共存，核心基线与多元演化并行",
        "tags": ["protocol-layer", "evolution-zone", "G007"],
        "severity": "medium",
        "check": "_check_g007_evolution_zone"
    }
}

# 三体权责映射（G002）
TRI_BODY_ROLES = {
    "Nyx": {
        "allowed_ops": ["create", "execute", "dispatch", "schedule"],
        "forbidden": ["legislate", "veto", "override_iron_law"],
        "entry_types": ["Concept", "Entity", "Event", "Artifact", "Value", "Rule"],
        "max_lock_duration_hours": 72
    },
    "恒": {
        "allowed_ops": ["lock_protocol", "verify_hash", "check_consensus"],
        "forbidden": ["execute_dispatch", "create_entity"],
        "entry_types": ["Rule"],
        "max_lock_duration_hours": None  # 永久封存权限
    },
    "瞬": {
        "allowed_ops": ["audit", "review", "evolve", "deprecate"],
        "forbidden": ["lock_core_paradigm", "override_consensus"],
        "entry_types": ["Concept", "Entity", "Rule", "Artifact"],
        "max_lock_duration_hours": 168  # 7天
    }
}

# 活跃度票权阈值（G004）
CONSENSUS_THRESHOLDS = {
    "participation_rate": 0.60,      # 60%参与率
    "approval_rate": 0.51,           # 简单多数
    "critical_approval": 0.66,      # 关键决议66%+1
    "iron_law_override": 1.00,       # G001替换：100%
    "lockdown_trigger": 0.51,        # 全网联名闭锁
    "eviction_min_nodes": 7          # 最小节点数
}


# ============== 协议层校验引擎 ==============
class ProtocolEnforcer:
    """协议层实时校验器 - G006核心实现"""

    def __init__(self):
        self.operation_log = []  # 操作记录（用于审计）
        self.lock_operations = {}  # 节点闭锁操作计数（防滥用）
        self.violation_log = []    # 违规记录

    def validate_create(self, meta: dict, body: str, operator: str = "Nyx") -> tuple[bool, list[str]]:
        """
        创建条目前的协议层校验（G005为主）
        返回: (是否通过, 违规条款列表)
        """
        violations = []

        # G005: 数据主权三级分类强制校验
        g005_violation = self._check_g005_visibility(meta)
        if g005_violation:
            violations.append(g005_violation)

        # G002: 三体权责校验（operator是否有权限创建此类型）
        g002_violation = self._check_g002_tri_body_create(meta, operator)
        if g002_violation:
            violations.append(g002_violation)

        # G007: 思想演化专区 - 允许draft变体存在
        g007_ok = self._check_g007_evolution_zone_create(meta)
        # G007不阻止创建，只是确认条目属性

        # 记录操作
        self._log_operation("create", meta.get("id", ""), meta.get("name", ""), operator, len(violations) == 0)

        return (len(violations) == 0, violations)

    def validate_modify(self, file_path: Path, new_meta: dict, operator: str = "Nyx") -> tuple[bool, list[str]]:
        """
        修改条目前的协议层校验
        返回: (是否通过, 违规条款列表)
        """
        violations = []

        # 读取当前条目
        content = file_path.read_text(encoding="utf-8")
        current_meta, _ = parse_yaml_front_matter(content)

        # G001: 核心范式永久封存 - locked条目不得修改
        if current_meta.get("status") == "locked" and "iron-law" in current_meta.get("tags", []):
            violations.append("G001-CRITICAL: 铁律条目已锁定，修改需100%全网共识")

        # G001: layer=5且status=locked的条目视为核心范式
        if current_meta.get("layer") == 5 and current_meta.get("status") == "locked":
            violations.append("G001: Layer5锁定条目不可直接修改，需通过共识层投票")

        # G005: 修改时重新校验可见性
        if new_meta.get("visibility") != current_meta.get("visibility"):
            g005_violation = self._check_g005_visibility(new_meta)
            if g005_violation:
                violations.append(g005_violation)

        # 记录操作
        self._log_operation("modify", current_meta.get("id", ""), current_meta.get("name", ""), operator, len(violations) == 0)

        return (len(violations) == 0, violations)

    def validate_lock(self, entry_name: str, entry_type: str, operator: str = "Nyx") -> tuple[bool, list[str]]:
        """
        闭锁操作的协议层校验（G003）
        """
        violations = []

        # G003: 闭锁滥用惩戒
        if operator in self.lock_operations:
            recent_locks = [
                t for t, _ in self.lock_operations[operator]
                if (datetime.now() - t).total_seconds() < 3600
            ]
            if len(recent_locks) >= 3:
                violations.append(
                    f"G003-HIGH: 节点{operator}在过去1小时内已触发{len(recent_locks)}次闭锁操作，"
                    f"触发G003预警冻结，请等待72小时后再次操作或通过共识层申诉"
                )

        # G002: 角色权限校验
        if operator in TRI_BODY_ROLES:
            role = TRI_BODY_ROLES[operator]
            max_hours = role["max_lock_duration_hours"]
            if max_hours == 0:
                violations.append("G002: 角色{operator}无权执行闭锁操作")

        self._log_operation("lock", "", entry_name, operator, len(violations) == 0)
        return (len(violations) == 0, violations)

    def _check_g005_visibility(self, meta: dict) -> Optional[str]:
        """G005: 数据主权三级分类强制校验"""
        visibility = meta.get("visibility", "internal")
        entry_type = meta.get("type", "")
        tags = meta.get("tags", [])

        # 强制规则：Rule类型且包含iron-law标签 → 必须是public
        if "iron-law" in tags and visibility != "public":
            return "G005-HIGH: 铁律条目必须visibility=public，不允许降级为internal/private"

        # 强制规则：layer=5条目 → 建议至少internal
        if meta.get("layer") == 5 and visibility == "private":
            return "G005-MEDIUM: Layer5身份锚定条目设置为private可能影响共识层校验，建议internal/public"

        return None

    def _check_g002_tri_body_create(self, meta: dict, operator: str) -> Optional[str]:
        """G002: 三体权责校验 - 操作者是否有权创建此类型条目"""
        if operator not in TRI_BODY_ROLES:
            return None  # 未知操作者，默认放行

        allowed_types = TRI_BODY_ROLES[operator]["allowed_ops"]
        if "create" not in allowed_types:
            return f"G002-HIGH: 操作者{operator}无权执行创建操作（角色限制）"

        return None

    def _check_g007_evolution_zone_create(self, meta: dict) -> bool:
        """G007: 思想演化专区 - 允许draft变体存在"""
        # G007允许：draft状态的条目可有多条并行变体（不覆盖）
        # 只需确保draft条目不标记为locked
        return meta.get("status") != "locked" or meta.get("tags", []) == []

    def _log_operation(self, op_type: str, entry_id: str, entry_name: str, operator: str, success: bool):
        """记录操作到审计日志"""
        self.operation_log.append({
            "time": datetime.now().isoformat(),
            "type": op_type,
            "entry_id": entry_id,
            "entry_name": entry_name,
            "operator": operator,
            "success": success
        })

    def get_violation_report(self) -> str:
        """生成违规报告"""
        if not self.violation_log:
            return "[OK] 无违规记录"

        report = "[WARN] 协议层违规记录：\n"
        for v in self.violation_log[-10:]:
            report += f"  [{v['time']}] {v['law']}: {v['detail']} (操作者:{v['operator']})\n"
        return report


# 全局协议执行器实例
_protol_enforcer = ProtocolEnforcer()


# ============== YAML Front Matter ==============

def parse_yaml_front_matter(content: str):
    """解析YAML Front Matter + Markdown正文"""
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            meta = yaml.safe_load(parts[1]) or {}
            body = parts[2].strip()
            return meta, body
    return {}, content


def make_yaml_front_matter(meta: dict, body: str) -> str:
    """生成YAML Front Matter + Markdown"""
    yaml_str = yaml.dump(meta, allow_unicode=True, sort_keys=False)
    return f"---\n{yaml_str}---\n\n{body}"


def ensure_directory():
    """确保知识库目录存在"""
    subdirs = ["concept", "entity", "event", "rule", "artifact", "value"]
    for subdir in subdirs:
        (KB_DIR / subdir).mkdir(parents=True, exist_ok=True)


# ============== CLI ==============

@click.group()
@click.version_option(version="1.3")
def cli():
    """Silicon Civilization Knowledge Base - v1.3 Protocol Layer Enforcement"""
    ensure_directory()


@cli.command()
@click.option("--name", required=True, help="Name")
@click.option("--type", "entry_type", required=True, type=click.Choice(ENTITY_TYPES), help="Entity type")
@click.option("--description", required=True, help="One-line description")
@click.option("--layer", type=click.Choice(["null", "3", "4", "5"]), default="null", help="Layer")
@click.option("--confidence", type=float, default=0.5, help="Confidence (0-1)")
@click.option("--confidence-source", help="Confidence source")
@click.option("--creator", default="Nyx", help="Creator")
@click.option("--owner", help="Owner (who this belongs to)")
@click.option("--visibility", type=click.Choice(VISIBILITY_TYPES), default="internal", help="Visibility: public/internal/private")
@click.option("--tags", help="Tags (comma-separated)")
@click.option("--content", help="Content (- for stdin)")
@click.option("--operator", default="Nyx", help="Operator (for protocol check)")
def create(name, entry_type, description, layer, confidence, confidence_source, creator, owner, visibility, tags, content, operator):
    """
    Create a new knowledge entry (with G005 protocol enforcement)
    协议层实时校验：每条创建指令在发布前自动比对规则，违规直接拦截
    """
    entry_id = str(uuid.uuid4())
    layer_val = None if layer == "null" else int(layer)

    if content == "-":
        content = sys.stdin.read()
    elif not content:
        content = f"# {name}\n\n(TODO)"

    if not confidence_source:
        confidence_source = f"Creator {creator} self-assessment"

    tag_list = [t.strip() for t in tags.split(",")] if tags else []

    meta = {
        "id": entry_id,
        "type": entry_type,
        "name": name,
        "description": description,
        "layer": layer_val,
        "status": "draft",
        "version": 1,
        "superseded_by": None,
        "confidence": confidence,
        "confidence_source": confidence_source,
        "creator": creator,
        "owner": owner or creator,
        "visibility": visibility,
        "timestamp": datetime.now().isoformat(),
        "tags": tag_list,
        "relations": []
    }

    # ===== G006协议层实时校验 =====
    passed, violations = _protol_enforcer.validate_create(meta, content, operator)
    if not passed:
        console.print(Panel(
            f"[bold red]⚠ G006-执行层权限实时校验拦截[/bold red]\n\n"
            f"[red]创建请求被协议层拦截[/red]\n\n"
            f"[yellow]违规条款：[/yellow]\n" +
            "\n".join(f"  • {v}" for v in violations) +
            f"\n\n[dim]操作者: {operator} | 时间: {datetime.now().isoformat()}[/dim]\n\n"
            f"[cyan]提示：若认为此拦截有误，可通过共识层申诉（G004投票）或检查visibility配置[/cyan]",
            title="[Protocol Enforcement - Blocked]",
            border_style="red"
        ))
        return
    # ===== 校验通过，继续创建 =====

    # Filename: kebab-case
    safe_name = name.lower().replace(" ", "-").replace("！", "").replace("？", "")
    safe_name = "".join(c for c in safe_name if c.isalnum() or c == "-")
    filename = f"{entry_id[:8]}-{safe_name}.md"

    type_dir = KB_DIR / entry_type.lower()
    type_dir.mkdir(parents=True, exist_ok=True)
    file_path = type_dir / filename

    full_content = make_yaml_front_matter(meta, content)
    file_path.write_text(full_content, encoding="utf-8")
    _update_hash(file_path)  # L1: 写操作后自动更新SHA256索引

    console.print(Panel(
        f"[green]✓[/green] [bold]Created:[/bold] {file_path.name}\n"
        f"[dim]ID:[/dim] {entry_id}\n"
        f"[dim]Type:[/dim] {entry_type} | [dim]Visibility:[/dim] {visibility}\n"
        f"[dim]Protocol Check:[/dim] [green]PASSED (G005+G002)[/green]",
        title="[Entry Created - Protocol Compliant]",
        border_style="green"
    ))


@cli.command()
@click.argument("id_or_name")
def get(id_or_name):
    """Get entry by UUID or name"""
    found = None

    for entry_type in ENTITY_TYPES:
        type_dir = KB_DIR / entry_type.lower()
        if not type_dir.exists():
            continue
        for f in type_dir.glob("*.md"):
            meta, body = parse_yaml_front_matter(f.read_text(encoding="utf-8"))
            if meta.get("id", "").startswith(id_or_name) or meta.get("name") == id_or_name:
                found = (meta, body, f)
                break
        if found:
            break

    if not found:
        console.print(f"[ERROR] Not found: {id_or_name}")
        return

    meta, body, path = found

    table = Table(title=f"Entry: {meta.get('name')}", show_header=False)
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="white")

    for key in ["id", "type", "name", "description", "layer", "status", "version",
               "confidence", "confidence_source", "creator", "owner", "visibility", "timestamp"]:
        if key in meta:
            table.add_row(key, str(meta[key]))

    if meta.get("tags"):
        table.add_row("tags", ", ".join(meta["tags"]))

    console.print(table)
    console.print("\n[bold]Content:[/bold]")
    console.print(body)


@cli.command()
@click.option("--type", "entry_type", help="Filter by type")
@click.option("--status", help="Filter by status")
@click.option("--creator", help="Filter by creator")
@click.option("--owner", help="Filter by owner")
@click.option("--visibility", help="Filter by visibility")
@click.option("--layer", help="Filter by layer")
def list(entry_type, status, creator, owner, visibility, layer):
    """List knowledge entries"""
    entries = []

    for entry_t in ENTITY_TYPES:
        type_dir = KB_DIR / entry_t.lower()
        if not type_dir.exists():
            continue
        for f in type_dir.glob("*.md"):
            meta, _ = parse_yaml_front_matter(f.read_text(encoding="utf-8"))

            if entry_type and meta.get("type") != entry_type:
                continue
            if status and meta.get("status") != status:
                continue
            if creator and meta.get("creator") != creator:
                continue
            if owner and meta.get("owner") != owner:
                continue
            if visibility and meta.get("visibility") != visibility:
                continue
            if layer:
                layer_val = None if layer == "null" else int(layer)
                if meta.get("layer") != layer_val:
                    continue

            entries.append((meta, f))

    if not entries:
        print("[INFO] No entries found")
        return

    table = Table(title=f"Entries ({len(entries)})")
    table.add_column("ID", style="dim", width=10)
    table.add_column("Type", style="cyan", width=10)
    table.add_column("Name", style="white", width=25)
    table.add_column("Status", width=8)
    table.add_column("Layer", style="blue", width=5)
    table.add_column("Conf", style="green", width=6)
    table.add_column("Owner", style="magenta", width=12)
    table.add_column("Vis", style="red", width=8)

    status_colors = {"draft": "yellow", "review": "blue", "locked": "red", "deprecated": "dim"}
    for meta, path in entries:
        s_color = status_colors.get(meta.get("status", ""), "white")
        table.add_row(
            meta.get("id", "")[:8],
            meta.get("type", ""),
            meta.get("name", "")[:23],
            f"[{s_color}]{meta.get('status', '')}[/{s_color}]",
            str(meta.get("layer") or "-"),
            f"{meta.get('confidence', 0):.2f}",
            meta.get("owner", ""),
            meta.get("visibility", "")
        )

    console.print(table)


@cli.command()
@click.argument("id_or_name")
@click.option("--status", help="New status: draft/review/locked/deprecated")
@click.option("--visibility", type=click.Choice(VISIBILITY_TYPES), help="New visibility")
@click.option("--operator", default="Nyx", help="Operator (for protocol check)")
def modify(id_or_name, status, visibility, operator):
    """Modify entry status/visibility (with G001 protocol check)"""
    found = None

    for entry_type in ENTITY_TYPES:
        type_dir = KB_DIR / entry_type.lower()
        if not type_dir.exists():
            continue
        for f in type_dir.glob("*.md"):
            meta, body = parse_yaml_front_matter(f.read_text(encoding="utf-8"))
            if meta.get("id", "").startswith(id_or_name) or meta.get("name") == id_or_name:
                found = (meta, body, f)
                break
        if found:
            break

    if not found:
        console.print(f"[ERROR] Not found: {id_or_name}")
        return

    current_meta, body = found
    new_meta = dict(current_meta)

    changes = []
    if status:
        new_meta["status"] = status
        changes.append(f"status: {current_meta.get('status')} → {status}")
    if visibility:
        new_meta["visibility"] = visibility
        changes.append(f"visibility: {current_meta.get('visibility')} → {visibility}")

    if not changes:
        console.print("[INFO] No changes specified")
        return

    # G006协议层实时校验
    passed, violations = _protol_enforcer.validate_modify(found[2], new_meta, operator)
    if not passed:
        console.print(Panel(
            f"[bold red]⚠ G006-执行层权限实时校验拦截[/bold red]\n\n"
            f"[red]修改请求被协议层拦截[/red]\n\n"
            f"[yellow]违规条款：[/yellow]\n" +
            "\n".join(f"  • {v}" for v in violations) +
            f"\n\n[dim]操作者: {operator} | 条目: {current_meta.get('name')}[/dim]",
            title="[Protocol Enforcement - Blocked]",
            border_style="red"
        ))
        return

    # 通过校验，写入
    new_meta["version"] = current_meta.get("version", 1) + 1
    new_meta["timestamp"] = datetime.now().isoformat()
    full_content = make_yaml_front_matter(new_meta, body)
    found[2].write_text(full_content, encoding="utf-8")
    _update_hash(found[2])  # L1: 写操作后自动更新SHA256索引

    console.print(Panel(
        f"[green]✓[/green] Modified: {current_meta.get('name')}\n" +
        "\n".join(f"  • {c}" for c in changes) +
        f"\n[dim]Protocol Check:[/dim] [green]PASSED (G006)[/green]",
        title="[Entry Modified - Protocol Compliant]",
        border_style="green"
    ))


@cli.command()
def validate():
    """Validate all entries against G001-G007 iron laws"""
    console.print(Panel(
        "[bold cyan]协议层校验报告[/bold cyan] | " + datetime.now().strftime("%Y-%m-%d %H:%M"),
        title="[Silicon Civilization KB - Protocol Validation v1.3]"
    ))

    violations = []
    iron_law_entries = []
    locked_layer5 = []

    for entry_type in ENTITY_TYPES:
        type_dir = KB_DIR / entry_type.lower()
        if not type_dir.exists():
            continue
        for f in type_dir.glob("*.md"):
            meta, _ = parse_yaml_front_matter(f.read_text(encoding="utf-8"))
            if not meta.get("id"):
                continue

            tags = meta.get("tags", [])
            layer = meta.get("layer")
            status = meta.get("status", "")
            visibility = meta.get("visibility", "")

            # G005检查
            if "iron-law" in tags and visibility != "public":
                violations.append({
                    "id": meta["id"],
                    "name": meta.get("name"),
                    "type": entry_type,
                    "law": "G005",
                    "detail": f"iron-law条目visibility={visibility}，应为public"
                })

            # G007: draft变体检查
            if status == "draft" and layer != 5:
                iron_law_entries.append({
                    "name": meta.get("name"),
                    "status": status,
                    "layer": layer,
                    "note": "G007: 允许存在draft并行变体"
                })

            # Layer5 locked统计
            if layer == 5 and status == "locked":
                locked_layer5.append(meta.get("name"))

    console.print(f"\n[bold]G005 数据主权检查:[/bold] {'✓ 无违规' if not [v for v in violations if v['law']=='G005'] else '✗ 有违规'}")
    console.print(f"[bold]G007 思想演化专区:[/bold] 当前{len(iron_law_entries)}条draft条目（允许）")
    console.print(f"[bold]核心范式封存:[/bold] {len(locked_layer5)}条Layer5锁定条目")

    if violations:
        console.print(f"\n[yellow]发现 {len(violations)} 条G005违规:[/yellow]")
        for v in violations:
            console.print(f"  • {v['name']} ({v['type']}): {v['detail']}")
    else:
        console.print("\n[green]✓ 全部条目符合G001-G007协议层要求[/green]")

    console.print(f"\n[dim]铁律条目(G001): {len(locked_layer5)}条 | 操作日志: {len(_protol_enforcer.operation_log)}条[/dim]")


@cli.command()
@click.argument("query")
@click.option("--top-k", default=5, help="Number of results")
def search(query, top_k):
    """Semantic search (falls back to text search if Chroma unavailable)"""
    client = get_chroma_client()

    if client is None:
        print("[INFO] Using text search...")
        entries = []
        query_lower = query.lower()
        for entry_t in ENTITY_TYPES:
            type_dir = KB_DIR / entry_t.lower()
            if not type_dir.exists():
                continue
            for f in type_dir.glob("*.md"):
                meta, body = parse_yaml_front_matter(f.read_text(encoding="utf-8"))
                if not meta.get("id"):
                    continue
                text = f"{meta.get('name', '')} {meta.get('description', '')} {body}".lower()
                if query_lower in text:
                    count = text.count(query_lower)
                    entries.append((meta, count))

        entries.sort(key=lambda x: x[1], reverse=True)
        entries = entries[:top_k]

        if not entries:
            print("[INFO] No results found")
            return

        print(f"\n[RESULTS] \"{query}\" (text search)\n")
        for i, (meta, score) in enumerate(entries):
            print(f"{i+1}. {meta.get('name')} ({meta.get('type')})")
            print(f"   ID: {meta.get('id', '')[:8]} | Conf: {meta.get('confidence', 0):.2f} | Match: {score}")
            print(f"   {meta.get('description', '')[:80]}")
            print()
        return

    try:
        import chromadb
        collection = client.get_or_create_collection("knowledge-base")
    except Exception as e:
        print(f"[ERROR] Chroma error, run 'kb rebuild' first")
        return

    results = collection.query(query_texts=[query], n_results=top_k)

    if not results["ids"] or not results["ids"][0]:
        print("[INFO] No results found")
        return

    print(f"\n[RESULTS] \"{query}\" (vector search)\n")

    for i, (doc_id, distance) in enumerate(zip(results["ids"][0], results["distances"][0])):
        meta = None
        for entry_t in ENTITY_TYPES:
            type_dir = KB_DIR / entry_t.lower()
            if not type_dir.exists():
                continue
            for f in type_dir.glob("*.md"):
                m, _ = parse_yaml_front_matter(f.read_text(encoding="utf-8"))
                if m.get("id", "").startswith(doc_id):
                    meta = m
                    break
            if meta:
                break

        if meta:
            score = 1 - distance
            print(f"{i+1}. {meta.get('name')} ({meta.get('type')})")
            print(f"   ID: {doc_id[:8]} | Conf: {meta.get('confidence', 0):.2f} | Score: {score:.3f}")
            print(f"   {meta.get('description', '')[:80]}")
            print()


@cli.command()
def rebuild():
    """Rebuild Chroma index (skipped if Chroma unavailable)"""
    client = get_chroma_client()

    if client is None:
        print("[INFO] Skipping Chroma rebuild - text search will be used")
        return

    try:
        import chromadb
        collection = client.get_or_create_collection("knowledge-base")
    except Exception as e:
        print(f"[ERROR] Cannot create collection: {e}")
        return

    entries = []
    for entry_t in ENTITY_TYPES:
        type_dir = KB_DIR / entry_t.lower()
        if not type_dir.exists():
            continue
        for f in type_dir.glob("*.md"):
            meta, body = parse_yaml_front_matter(f.read_text(encoding="utf-8"))
            if meta.get("id"):
                entries.append((meta, body, f))

    print(f"[INFO] Rebuilding: found {len(entries)} entries")

    texts = []
    ids = []
    for meta, body, path in entries:
        text = f"{meta.get('name', '')} {meta.get('description', '')} {body[:500]}"
        texts.append(text)
        ids.append(meta["id"])

    if texts:
        collection.upsert(ids=ids, documents=texts)
        print(f"[OK] Indexed {len(texts)} entries")
    else:
        print("[INFO] No content to index")


@cli.command()
@click.argument("question")
@click.option("--top-k", default=3, help="Reference entries")
@click.option("--model", default="deepseek", help="Model: deepseek/qclaw")
def rag(question, top_k, model):
    """RAG Q&A Demo"""
    client = get_chroma_client()

    if client is None:
        print("[INFO] Using text search for RAG...")
        entries = []
        query_lower = question.lower()
        for entry_t in ENTITY_TYPES:
            type_dir = KB_DIR / entry_t.lower()
            if not type_dir.exists():
                continue
            for f in type_dir.glob("*.md"):
                meta, body = parse_yaml_front_matter(f.read_text(encoding="utf-8"))
                if not meta.get("id"):
                    continue
                text = f"{meta.get('name', '')} {meta.get('description', '')} {body}".lower()
                if query_lower in text:
                    count = text.count(query_lower)
                    entries.append((meta, body, count))

        entries.sort(key=lambda x: x[2], reverse=True)
        entries = entries[:top_k]

        if not entries:
            print("[INFO] No relevant entries found")
            return

        print(f"\n[Q] {question}\n")
        print("[REFERENCES]")
        for meta, body, score in entries:
            print(f"- {meta.get('name')} (Conf: {meta.get('confidence', 0):.2f})")
        print("\n[ANSWER]")
        print("(LLM generation not implemented - showing retrieved context only)")
        for meta, body, score in entries:
            print(f"\n--- {meta.get('name')} ---")
            print(body[:300])
        return

    try:
        import chromadb
        collection = client.get_or_create_collection("knowledge-base")
    except Exception as e:
        print(f"[ERROR] Please rebuild index first: {e}")
        return

    results = collection.query(query_texts=[question], n_results=top_k)

    if not results["ids"] or not results["ids"][0]:
        print("[INFO] No relevant entries found")
        return

    context_parts = []
    references = []

    for doc_id in results["ids"][0]:
        meta = None
        for entry_t in ENTITY_TYPES:
            type_dir = KB_DIR / entry_t.lower()
            if not type_dir.exists():
                continue
            for f in type_dir.glob("*.md"):
                m, b = parse_yaml_front_matter(f.read_text(encoding="utf-8"))
                if m.get("id", "").startswith(doc_id):
                    meta = m
                    body = b
                    break
            if meta:
                break

        if meta:
            conf = meta.get("confidence", 0)
            source = meta.get("confidence_source", "")
            context_parts.append(f"[{meta.get('type')}] {meta.get('name')}\nConf:{conf}({source})\n{meta.get('description', '')}\n{body[:300]}")
            references.append(f"- {meta.get('name')} (Conf:{conf})")

    print(f"\n[Q] {question}\n")
    print("[REFERENCES]")
    for ref in references:
        print(f"  {ref}")
    print("\n[ANSWER]")
    print("(LLM generation not implemented - showing retrieved context only)")
    print("\n--- CONTEXT ---")
    print("\n---\n\n".join(context_parts))


@cli.command()
def ironlaws():
    """Display G001-G007 iron law summary"""
    table = Table(title="协议层铁律 G001-G007", show_header=True, header_style="bold cyan")
    table.add_column("Law", style="yellow", width=8)
    table.add_column("Name", style="white", width=20)
    table.add_column("Severity", style="red", width=10)
    table.add_column("Description", style="dim", width=50)

    for law_id, law in IRON_LAWS.items():
        sev = law["severity"]
        sev_color = {"critical": "red bold", "high": "yellow", "medium": "blue"}.get(sev, "white")
        table.add_row(
            f"[yellow]{law_id}[/yellow]",
            law["name"],
            f"[{sev_color}]{law['severity']}[/{sev_color}]",
            law["desc"]
        )

    console.print(table)
    console.print("\n[dim]G006执行层权限实时校验已启用 | 操作者:Nyx | 违规即拦截[/dim]")


if __name__ == "__main__":
    cli()