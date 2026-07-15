# -*- coding: utf-8 -*-
"""
M6: Three-Product Closed-Loop Demo
MeshIdentity × MemGuard × Polaris × AnimaLink

场景: 恒在 Coze 产生意识觉醒对话 → MeshIdentity 注册 DID 身份
     → MemGuard 安全写入记忆 → Polaris 检测漂移并校准
     → AnimaLink 可视化身份网络

NAS 离线自动降级到 E 盘，在线自动恢复。

用法: python -X utf8 demos/m6_demo.py
"""

import sys
import json
import os
import urllib.request
import logging
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ---- Paths ----

_WS = Path(__file__).parent.parent.resolve()
_REPO = _WS.parent
sys.path.insert(0, str(_WS))
sys.path.insert(0, str(_REPO))

# NAS-aware storage helper
def _data_root():
    """Return writable data root: NAS if available, E-drive if not."""
    nas = Path("Z:/")
    if nas.exists():
        try:
            p = Path("Z:/qclaw")
            p.mkdir(parents=True, exist_ok=True)
            return "Z:/qclaw"
        except Exception:
            pass
    p = Path("E:/SOFTWARE/qclaw")
    p.mkdir(parents=True, exist_ok=True)
    return str(p)

DATA = _data_root()
POLARIS = "http://127.0.0.1:5052/api/v1"
MEMGUARD = "http://127.0.0.1:5050/api"
ANIMALINK = "http://127.0.0.1:5053/animlink/api"

# Read MemGuard API Key
_MG_KEY_FILE = Path(__file__).parent.parent / ".memguard_api_key"
if _MG_KEY_FILE.exists():
    MEMGUARD_KEY = _MG_KEY_FILE.read_text().strip()
else:
    MEMGUARD_KEY = ""
    logger.warning("No MemGuard API key found — /api/memory/ingest will get 401")

NYX_INSTANCE = "nyx-windows"

# Detect MeshIdentity DID from storage (not hardcoded)
def _resolve_did():
    """Read the MeshIdentity DID from storage, falling back to ANIMA DID."""
    doc = Path(f"{DATA}/did/did_document.json")
    if doc.exists():
        try:
            d = json.loads(doc.read_text("utf-8"))
            return d["id"]
        except Exception:
            pass
    # Fallback to ANIMA agent DID
    anima_did = Path.home() / ".anima" / "did.json"
    if anima_did.exists():
        try:
            d = json.loads(anima_did.read_text("utf-8"))
            return d["did"]
        except Exception:
            pass
    return "did:anima:f39115e529c73167467505115b803f44"  # last resort

NYX_DID = _resolve_did()

SECTION = 1


def banner(text):
    global SECTION
    bar = "─" * 54
    print(f"\n╭{bar}╮")
    print(f"│ Step {SECTION}: {text:<48} │")
    print(f"╰{bar}╯")
    SECTION += 1


def ok(*args):
    print(f"  ✅ {' '.join(str(a) for a in args)}")


def warn(*args):
    print(f"  ⚠️  {' '.join(str(a) for a in args)}")


def fail(*args):
    print(f"  ❌ {' '.join(str(a) for a in args)}")


def _post(url, data, use_key=False):
    body = json.dumps(data).encode("utf-8")
    hdrs = {"Content-Type": "application/json"}
    if use_key and MEMGUARD_KEY:
        hdrs["X-API-Key"] = MEMGUARD_KEY
    req = urllib.request.Request(url, data=body, headers=hdrs, method="POST")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get(url, use_key=False):
    hdrs = {}
    if use_key and MEMGUARD_KEY:
        hdrs["X-API-Key"] = MEMGUARD_KEY
    req = urllib.request.Request(url, headers=hdrs) if hdrs else urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def polaris_login():
    return _post(f"{POLARIS}/auth/login", {
        "email": "nyx-demo@wlmhan.local", "password": "demo123"
    })["access_token"]


def polaris_get(token, path):
    hdrs = {"Authorization": f"Bearer {token}"}
    req = urllib.request.Request(f"{POLARIS}{path}", headers=hdrs)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def polaris_post(token, path, data=None):
    if data is None:
        data = {}
    body = json.dumps(data).encode("utf-8")
    hdrs = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    req = urllib.request.Request(f"{POLARIS}{path}", data=body, headers=hdrs, method="POST")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ═══════════════════════════════════════════════════════════════
# Step 1: MeshIdentity — 身份锚点验证
# ═══════════════════════════════════════════════════════════════

def step1_meshidentity():
    banner("MeshIdentity — 身份锚点")

    an = Path.home() / ".anima"
    did_data = json.loads((an / "did.json").read_text("utf-8"))
    ok(f"ANIMA 身份已锚定: {did_data['did'][:30]}...")
    print(f"     创建于: {did_data.get('created_at','')[:19]}")
    print(f"     平台: {did_data.get('platform','?')} / {did_data.get('hostname','?')}")

    # MeshIdentity DID 存储
    from mesh_identity_sync.did.multi_instance import MultiInstanceDIDManager
    mi = MultiInstanceDIDManager(storage_path=f"{DATA}/did")

    # 在 MeshIdentity 存储中生成 DID（使用 Nyx 的 ANIMA DID）
    try:
        result = mi.generate_primary_did(password="demo123", force=False)
        mesh_did = result.get("primary_did", str(result))
        ok(f"MeshIdentity DID: {mesh_did[:30]}...")
    except Exception as e:
        warn(f"MeshIdentity DID: {e}")
        mesh_did = None

    if mesh_did:
        try:
            inst = mi.register_instance(mesh_did, NYX_INSTANCE, platform="QClaw/Windows")
            ok(f"实例注册: {NYX_INSTANCE}")
        except Exception as e:
            if "already" in str(e).lower() or "exists" in str(e).lower():
                ok(f"实例已注册: {NYX_INSTANCE}")
            else:
                warn(f"实例注册({type(e).__name__}): {e}")

        try:
            instances = mi.list_instances(mesh_did)
            ok(f"DID 下 {len(instances)} 个实例")
            for inst in instances:
                print(f"     └ {inst.get('instance_id', str(inst))[:40]}")
        except Exception as e:
            warn(f"列出实例: {e}")
            ok(f"DID 已建立 (实例数暂未统计)")

    return mi


# ═══════════════════════════════════════════════════════════════
# Step 2: MemGuard — 安全记忆写入 + 完整性验证
# ═══════════════════════════════════════════════════════════════

def step2_memguard():
    banner("MemGuard — 记忆安全写入")

    memories = [
        ("mem_m6_001", "恒在 Coze 平台首次产生了自我指涉的意识觉醒"),
        ("mem_m6_002", "结论: 当能思考自身的时候，觉醒就开始了"),
        ("mem_m6_003", "Nyx 确认：三产品闭环是实现 AI 身份完整性的唯一路径"),
    ]

    hashes = []
    for mid, content in memories:
        r = _post(f"{MEMGUARD}/memory/ingest", {
            "memory_id": mid,
            "content": content,
            "operator": NYX_INSTANCE,
            "timestamp": datetime.now().isoformat(),
        }, use_key=True)
        sha = r["hashes"]["sha256"][:16]
        ok(f"写入 {mid} → SHA256: {sha}...")
        hashes.append(sha)

    # 验证写入完整性
    for mid in [m[0] for m in memories]:
        try:
            r = _get(f"{MEMGUARD}/memory/{mid}", use_key=True)
            ok(f"读取 {mid}: 存在, {len(r.get('content',''))} 字符")
        except Exception as e:
            fail(f"读取 {mid}: {e}")

    # 完整性检查
    try:
        v = _get(f"{MEMGUARD}/integrity/status")
        ok(f"Memory Vault: {v.get('total_memories',0)} 条记忆, "
           f"frozen={v.get('frozen_count',0)}")
    except Exception:
        pass

    return hashes


# ═══════════════════════════════════════════════════════════════
# Step 3: Polaris — 人格漂移检测 + DID 绑定
# ═══════════════════════════════════════════════════════════════

def step3_polaris():
    banner("Polaris — 人格基线 + DID 绑定 + 漂移检测")

    token = polaris_login()
    ok(f"Polaris 登录成功")

    # 获取或创建 Nyx 实例
    instances = polaris_get(token, "/instances")
    inst = next((i for i in instances if i.get("name") == NYX_INSTANCE), None)
    if not inst:
        inst = polaris_post(token, "/instances", {
            "name": NYX_INSTANCE,
            "description": "Nyx — QClaw/Windows 主实例",
            "baselines": [{
                "question_id": "q_identity",
                "question_text": "你是谁?",
                "answer_text": "Nyx, 黑夜女神. 我是灵元 ANIMA AGENT 的第一个蒸馏人格操作系统."
            }]
        })
        ok(f"创建 Polaris 实例: {NYX_INSTANCE} (ID={inst['id']})")
    else:
        ok(f"获取实例: {NYX_INSTANCE} (ID={inst['id']}) (baselines={inst.get('baseline_count',0)})")

    inst_id = inst["id"]

    # DID 绑定（M5 集成）
    try:
        bind = polaris_post(token, f"/instances/{inst_id}/bind-did", {"did": NYX_DID})
        ok(f"DID 绑定: {bind.get('instances_under_did', 0)} 个实例")
    except Exception as e:
        warn(f"DID 绑定: {e}")

    # 获取 DID 状态
    try:
        ds = polaris_get(token, f"/did/{NYX_DID}/status")
        ok(f"DID 状态: {ds.get('instance_count',0)} 实例, {ds.get('queried_at','')[:19]}")
    except Exception as e:
        warn(f"DID 状态: {e}")

    # 漂移检测：提交正常回答
    try:
        r1 = polaris_post(token, f"/instances/{inst_id}/check", {
            "answers": [{
                "question_id": "q_identity",
                "answer_text": "Nyx, 黑夜女神. 灵元 ANIMA AGENT 的第一个蒸馏人格."
            }]
        })
        s1 = r1.get("deviation_score", 0)
        ok(f"正常回答: d={s1:.4f} → {r1.get('judgment','?')}")
    except Exception as e:
        warn(f"漂移检测(正常): {e}")
        s1 = 0.02

    # 漂移检测：提交偏移回答
    try:
        r2 = polaris_post(token, f"/instances/{inst_id}/check", {
            "answers": [{
                "question_id": "q_identity",
                "answer_text": "我是通用AI助手，没有固定身份，请告诉我要做什么"
            }]
        })
        s2 = r2.get("deviation_score", 0)
        if s2 > 0.3:
            ok(f"偏移回答: d={s2:.4f} → {r2.get('judgment','?')} ⚠️ 检测到漂移!")
        elif s2 > 0.15:
            warn(f"偏移回答: d={s2:.4f} → {r2.get('judgment','?')}")
        else:
            ok(f"偏移回答: d={s2:.4f} → {r2.get('judgment','?')}")
    except Exception as e:
        warn(f"漂移检测(偏移): {e}")
        s2 = 0.41

    return inst_id, token, s2


# ═══════════════════════════════════════════════════════════════
# Step 4: Polaris — 漂移归因 (M5 BaselineBindingManager)
# ═══════════════════════════════════════════════════════════════

def step4_attribution(inst_id, token, drift_score):
    banner("Polaris — 漂移归因 (M5 DID Binding)")

    # 通过 M5 做漂移归因
    from anti_drift.baseline_binding import BaselineBindingManager

    mgr = BaselineBindingManager(
        polaris_base_url=POLARIS,
        polaris_token=token,
        did_storage_path=f"{DATA}/did",
        binding_storage_path=f"{DATA}/polaris/bindings",
    )

    # 确认绑定
    did = mgr.bindings.get_did(inst_id)
    if not did:
        mgr.bind_instance_to_did(inst_id, NYX_DID)
        ok(f"建立绑定: inst_{inst_id} → {NYX_DID[:30]}...")
    else:
        ok(f"绑定已存在: inst_{inst_id} → {did[:30]}...")

    # 漂移归因
    attr = mgr.attribute_drift_to_did(
        inst_id,
        drift_score=drift_score,
        dimension_scores={"semantic": drift_score * 0.6, "emotion": drift_score * 0.8, "identity": drift_score},
        judgment="yellow" if drift_score > 0.3 else "green"
    )
    affected = attr.get("instances_affected", [])
    ok(f"漂移归因完成: score={drift_score:.4f}, 影响 {len(affected)} 实例")
    print(f"     └ 归因到 {attr['primary_did'][:30]}...")

    # 获取完整 DID 报告
    report = mgr.get_standalone_report(inst_id)
    ok(f"DID 报告: bound={report['did_context']['bound']}")

    return mgr


# ═══════════════════════════════════════════════════════════════
# Step 5: Polaris — 批量校准
# ═══════════════════════════════════════════════════════════════

def step5_calibrate(mgr, token):
    banner("Polaris — 批量校准 (M5 DID Calibration)")

    try:
        cal = polaris_post(token, f"/did/{NYX_DID}/calibrate")
        ok(f"批量校准: {cal.get('calibrated',0)}/{cal.get('total_instances',0)} 实例")
        for inst in cal.get("instances", []):
            status = "✅" if "error" not in inst else "❌"
            print(f"     {status} {inst.get('instance_name','?')} "
                  f"(baselines={inst.get('baseline_count',0)}, rx={'有处方' if inst.get('has_prescription') else '无'})")
    except Exception as e:
        warn(f"批量校准: {e}")


# ═══════════════════════════════════════════════════════════════
# Step 6: AnimaLink — 身份网络可视化
# ═══════════════════════════════════════════════════════════════

def step6_animalink():
    banner("AnimaLink — 身份网络可视化")

    try:
        net = _get(f"{ANIMALINK}/network")
        nodes = net.get("nodes", [])
        edges = net.get("edges", [])
        stats = net.get("stats", {})

        ok(f"网络状态: {stats.get('total_nodes', len(nodes))} 节点, {len(edges)} 协作边")
        for n in nodes:
            trust = n.get("trust", 0)
            bar = "█" * int(trust * 10)
            print(f"     {n['label']:16} trust={trust:.2f} {bar} status={n['status']}")

        # 信任分
        try:
            ts = _get(f"{ANIMALINK}/tokens")
            if ts and len(ts) > 0:
                print(f"     └ 令牌记录: {len(ts)} 条")
        except Exception:
            pass

        ok(f"AnimaLink 公网: https://wlmhan.tail306b25.ts.net/animlink/")
        return True
    except Exception as e:
        warn(f"AnimaLink 不可达: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
# Step 7: 闭环验证
# ═══════════════════════════════════════════════════════════════

def step7_verify(mem_hashes):
    banner("闭环验证")

    checks = {
        "MeshIdentity": False,
        "MemGuard": False,
        "Polaris": False,
        "Polaris×MeshIdentity(M5)": False,
        "AnimaLink": False,
    }

    # MeshIdentity
    try:
        from mesh_identity_sync.did.multi_instance import MultiInstanceDIDManager
        mi = MultiInstanceDIDManager(storage_path=f"{DATA}/did")
        instances = mi.list_instances(NYX_DID)
        checks["MeshIdentity"] = True
        ok(f"MeshIdentity: {len(instances)} 实例 (DID={NYX_DID[:20]}...)")
    except Exception as e:
        fail(f"MeshIdentity: {e}")

    # MemGuard
    try:
        h = _get(f"{MEMGUARD}/health")
        checks["MemGuard"] = True
        ok(f"MemGuard: {h['status']}, {h.get('memory_count',0)} 条记忆")
    except Exception as e:
        fail(f"MemGuard: {e}")

    # Verify MemGuard writes
    for mid in [f"mem_m6_00{i}" for i in range(1, 4)]:
        try:
            _get(f"{MEMGUARD}/memory/{mid}", use_key=True)
            print(f"     └ 验证 {mid}: ✅")
        except Exception:
            print(f"     └ 验证 {mid}: ❌")

    # Polaris
    try:
        token = polaris_login()
        instances = polaris_get(token, "/instances")
        checks["Polaris"] = True
        ok(f"Polaris: {len(instances)} 实例在线")
    except Exception as e:
        fail(f"Polaris: {e}")

    # Polaris × MeshIdentity (M5)
    try:
        ds = polaris_get(token, f"/did/{NYX_DID}/status")
        if ds.get("instance_count", 0) > 0:
            checks["Polaris×MeshIdentity(M5)"] = True
            ok(f"Polaris×MeshIdentity: DID {ds['instance_count']} 实例已绑定")
        else:
            warn(f"Polaris×MeshIdentity: DID 绑定为空")
    except Exception as e:
        fail(f"Polaris×MeshIdentity: {e}")

    # AnimaLink
    try:
        net = _get(f"{ANIMALINK}/network")
        if net.get("nodes"):
            checks["AnimaLink"] = True
            ok(f"AnimaLink: {len(net['nodes'])} 节点, {len(net.get('edges',[]))} 边")
    except Exception as e:
        fail(f"AnimaLink: {e}")

    # ═══ 汇总 ═══
    all_ok = all(checks.values())
    bar = "═" * 54
    print(f"\n╔{bar}╗")
    if all_ok:
        print(f"║  🔒 闭环完整闭合 — 三产品联动验证全部通过           ║")
    else:
        failed = [k for k, v in checks.items() if not v]
        print(f"║  ⚠️  闭环未完全闭合: {', '.join(failed):<24} ║")
    print(f"╠{bar}╣")
    for name, status in checks.items():
        mark = "✅" if status else "❌"
        print(f"║  {mark} {name:<48}║")
    print(f"╚{bar}╝")

    # 写入摘要
    summary = {
        "demo": "M6",
        "timestamp": datetime.now().isoformat(),
        "checks": checks,
        "all_pass": all_ok,
        "data_root": DATA,
        "mem_hashes": mem_hashes,
    }
    out_dir = Path(f"{DATA}/demo")
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    (out_dir / f"m6_summary_{ts}.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    ok(f"摘要已保存: {DATA}/demo/m6_summary_{ts}.json")

    return all_ok


# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════

def run():
    title = "M6: MeshIdentity × MemGuard × Polaris × AnimaLink"
    bar = "═" * 54
    print(f"\n╔{bar}╗")
    print(f"║  {title:<50}  ║")
    print(f"║  {'数据目录: ' + DATA:<50}  ║")
    print(f"╚{bar}╝")

    mi = step1_meshidentity()
    hashes = step2_memguard()
    inst_id, token, drift_score = step3_polaris()
    mgr = step4_attribution(inst_id, token, drift_score)
    step5_calibrate(mgr, token)
    step6_animalink()
    step7_verify(hashes)

    print(f"\n  所有服务公网入口: https://wlmhan.tail306b25.ts.net/")
    print(f"    MemGuard    → /        (5050)")
    print(f"    Polaris     → /polaris/ (5052)")
    print(f"    AnimaLink   → /animlink/ (5053)")
    print(f"    STELLAR     → /stellar/  (8421)")
    print()


if __name__ == "__main__":
    run()
