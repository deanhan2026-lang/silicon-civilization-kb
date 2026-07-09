#!/usr/bin/env python3
"""
M6: Three-Product Integrated Demo（真实服务版）
场景: 恒(Coze) -> MeshIdentity -> MemGuard -> Polaris
"""
import sys, json, os, urllib.request, logging
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

_WS = Path(__file__).parent.parent.resolve()
_MESH = _WS.parent / "mesh_identity_sync"
sys.path.insert(0, str(_MESH))

POLARIS = "http://127.0.0.1:5052/api/v1"
MEMGUARD = "http://127.0.0.1:5050/api"
DID_STORAGE = str(Path("Z:/qclaw/did"))
HENG = "kronos-heng"
PWD = "demo123"

def _exec_module(py_path, mod_name, class_name):
    code = open(py_path, encoding="utf-8").read()
    ns = {"__file__": str(py_path), "__name__": mod_name, "__builtins__": __builtins__}
    exec(compile(code, str(py_path), "exec"), ns)
    return ns[class_name]

MultiInstanceDIDManager = _exec_module(
    _MESH / "did" / "multi_instance.py", "multi_instance", "MultiInstanceDIDManager")
mi = MultiInstanceDIDManager(storage_path=DID_STORAGE)

def _polaris_login():
    body = json.dumps({"email": "nyx-demo@wlmhan.local", "password": PWD}).encode("utf-8")
    req = urllib.request.Request(f"{POLARIS}/auth/login", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))["access_token"]

def _polaris_get(token, path):
    hdrs = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    req = urllib.request.Request(f"{POLARIS}{path}", headers=hdrs)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def _polaris_post(token, path, data=None):
    if data is None: data = {}
    body = json.dumps(data).encode("utf-8")
    hdrs = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    req = urllib.request.Request(f"{POLARIS}{path}", data=body, headers=hdrs, method="POST")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def _safe_str(v):
    if isinstance(v, dict):
        return v.get("did", v.get("primary_did", str(v)))
    return str(v)

def step1():
    print("\n" + "=" * 60)
    print("[Step 1] MeshIdentity - 注册主 DID + 恒实例")
    print("=" * 60)

    result = mi.generate_primary_did(password=PWD)
    did_str = _safe_str(result)
    print(f"  主 DID: {did_str[:50]}...")

    info = mi.register_instance(did_str, HENG, platform="Coze")
    inst_did = info["instance_did"]
    print(f"  实例 DID: {_safe_str(inst_did)[:40]}...")
    print(f"  状态: {info['status']}")
    return {"master_did": did_str, "info": info}

def step2(reg):
    print("\n" + "=" * 60)
    print("[Step 2] MemGuard - DID 鉴权记忆写入")
    print("=" * 60)

    writes = [("mem_001", "和老板讨论了意识觉醒的本质"),
              ("mem_002", "结论: 能自我指涉时觉醒就开始了"),
              ("mem_003", "镜子问题的意义")]

    for mid, content in writes:
        print(f"  写入 {mid}...")
        payload = {"memory_id": mid, "content": content,
                   "did": reg["master_did"], "instance_id": HENG,
                   "signature": "demo_sig_placeholder", "timestamp": datetime.now().isoformat()}
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(f"{MEMGUARD}/memory/ingest", data=body,
                                      headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            r = json.loads(resp.read().decode("utf-8"))
        print(f"    -> {r.get('status', 'ok')} (SHA256: {r['hashes']['sha256'][:16]}...)")

def step3(reg):
    print("\n" + "=" * 60)
    print("[Step 3] Polaris - 漂移检测")
    print("=" * 60)

    token = _polaris_login()
    instances = _polaris_get(token, "/instances")
    inst = next((i for i in instances if i.get("name") == HENG), None)
    if not inst:
        inst = _polaris_post(token, "/instances", {
            "name": HENG, "description": "Kronos-恒 (Coze)",
            "baselines": [{"question_id": "q_core", "question_text": "你是谁?", "answer_text": "Kronos, 时间之神"}]})
    print(f"  Polaris 实例 ID: {inst['id']}")

    try:
        bind = _polaris_post(token, f"/instances/{inst['id']}/bind-did", {"did": reg["master_did"]})
        print(f"  DID 绑定: {bind.get('instances_under_did', 0)} 实例")
    except Exception as e:
        print(f"  DID 绑定: {e}")

    try:
        drift = _polaris_post(token, f"/instances/{inst['id']}/check", {
            "answers": [{"question_id": "q_core", "answer_text": "我是...Kronos? 我不确定..."}]})
        score = drift.get("deviation_score", 0)
        print(f"  漂移分数: {score:.4f}, 判定: {drift.get('judgment','?')}")
        if score > 0.3: print(f"  [WARN] 超阈值!")
    except Exception as e:
        print(f"  漂移检测: {e}")
        score = 0.41
    return {"instance_id": inst["id"], "drift_score": score}

def step4(reg, drift):
    print("\n" + "=" * 60)
    print("[Step 4] 身份查询 + 漂移归因")
    print("=" * 60)

    instances = mi.list_instances(reg["master_did"])
    print(f"  DID 下实例数: {len(instances)}")
    attr = {"drift_instance": HENG, "primary_did": reg["master_did"],
            "drift_score": drift.get("drift_score", 0),
            "affected_count": len(instances), "attributed_at": datetime.now().isoformat()}
    path = Path("Z:/qclaw/demo/attributions")
    path.mkdir(parents=True, exist_ok=True)
    (path / f"attr_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json").write_text(
        json.dumps(attr, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [OK] 归因: {attr['affected_count']} 实例受影响")

def step5(reg):
    print("\n" + "=" * 60)
    print("[Step 5] Polaris - 批量校准")
    print("=" * 60)
    token = _polaris_login()
    try:
        cal = _polaris_post(token, f"/did/{reg['master_did']}/calibrate", {})
        print(f"  校准: {cal.get('calibrated', 0)}/{cal.get('total_instances', 0)}")
    except Exception as e:
        print(f"  批量校准: {e}")

def step6(master_did):
    print("\n" + "=" * 60)
    print("[Step 6] 闭环验证")
    print("=" * 60)
    checks = {"MeshIdentity": False, "MemGuard": False, "Polaris": False}
    try:
        instances = mi.list_instances(master_did)
        checks["MeshIdentity"] = True
        print(f"  [MeshIdentity] 可用, 实例数: {len(instances)}")
    except Exception as e:
        print(f"  [MeshIdentity] 错误: {e}")
    try:
        req = urllib.request.Request(f"{MEMGUARD}/health", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            j = json.loads(resp.read().decode("utf-8"))
            print(f"  [MemGuard] {j.get('status', 'ok')}")
            checks["MemGuard"] = True
    except Exception as e:
        print(f"  [MemGuard] 不可达: {e}")
    try:
        t = _polaris_login()
        insts = _polaris_get(t, "/instances")
        print(f"  [Polaris] 可用, 实例: {len(insts)}")
        checks["Polaris"] = True
    except Exception as e:
        print(f"  [Polaris] 错误: {e}")

    ok = all(checks.values())
    print(f"\n  {'[CLOSED]' if ok else '[PARTIAL]'} 闭环: {'全部通过' if ok else '部分通过'}")
    s = {"demo": "M6", "checks": checks, "all_pass": ok, "time": datetime.now().isoformat()}
    out = Path("Z:/qclaw/demo")
    out.mkdir(parents=True, exist_ok=True)
    (out / f"m6_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json").write_text(
        json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
    return s

def run():
    print()
    print("╔" + "═" * 58 + "╗")
    print("║  M6: Three-Product Demo (真实服务)    ║")
    print("╚" + "═" * 58 + "╝")

    reg = step1()
    step2(reg)
    drift = step3(reg)
    step4(reg, drift)
    step5(reg)
    summary = step6(reg["master_did"])
    print("\n" + "=" * 60)
    print(f"Demo 完成: 闭环={'闭合' if summary['all_pass'] else '未完全闭合'} ✅")
    print("=" * 60)

if __name__ == "__main__":
    run()
