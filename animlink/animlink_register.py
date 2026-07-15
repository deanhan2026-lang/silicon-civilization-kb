# -*- coding: utf-8 -*-
"""AnimaLink 新节点接入工具
用法:
  新增节点: python animlink_register.py add <node_id> <did> <hostname> <platform> [label]
  列出节点: python animlink_register.py list
  删除节点: python animlink_register.py rm <node_id>
  触发刷新: python animlink_register.py refresh
"""
import sys, json, os, time, urllib.request

DATA_ROOT = None
for p in [r"Z:\qclaw", r"E:\SOFTWARE\qclaw"]:
    if os.path.exists(p):
        DATA_ROOT = p
        break
if not DATA_ROOT:
    print("ERROR: No data root found (tried Z: and E:)")
    sys.exit(1)

REGISTRY_PATH = os.path.join(DATA_ROOT, "mesh", "registry.json")
TRUST_PATH = os.path.join(DATA_ROOT, "tokens", "trust_scores.json")
ANIMALINK_URL = "http://127.0.0.1:5053/animlink/api/nodes"

def ensure_dirs():
    for p in [REGISTRY_PATH, TRUST_PATH]:
        os.makedirs(os.path.dirname(p), exist_ok=True)

def load_registry():
    if os.path.exists(REGISTRY_PATH):
        with open(REGISTRY_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"nodes": {}}

def save_registry(reg):
    ensure_dirs()
    with open(REGISTRY_PATH, 'w', encoding='utf-8') as f:
        json.dump(reg, f, ensure_ascii=False, indent=2)

def load_trust():
    if os.path.exists(TRUST_PATH):
        with open(TRUST_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"scores": {}}

def save_trust(t):
    ensure_dirs()
    with open(TRUST_PATH, 'w', encoding='utf-8') as f:
        json.dump(t, f, ensure_ascii=False, indent=2)

def cmd_add(node_id, did, hostname, platform, label=None):
    reg = load_registry()
    if node_id in reg.get("nodes", {}):
        print(f"[WARN] Node '{node_id}' already exists, updating")
    
    reg.setdefault("nodes", {})[node_id] = {
        "did": did,
        "hostname": hostname,
        "platform": platform,
        "status": "active",
        "lastSeen": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "notes": label or ""
    }
    save_registry(reg)
    
    trust = load_trust()
    trust.setdefault("scores", {})[node_id] = {"trust": 0.5, "total_tokens": 0, "completed": 0}
    save_trust(trust)

    print(f"[OK] Node '{node_id}' added/updated → {REGISTRY_PATH}")
    print(f"     DID: {did}")
    print(f"     Host: {hostname} ({platform})")

def cmd_list():
    reg = load_registry()
    trust = load_trust()
    nodes = reg.get("nodes", {})
    if not nodes:
        print("No nodes registered.")
        return
    
    print(f"{'ID':<25} {'Trust':>6} {'Host':<20} {'Status':<10}")
    print("-" * 65)
    for nid, data in sorted(nodes.items()):
        t = trust.get("scores", {}).get(nid, {}).get("trust", "?")
        h = data.get("hostname", "?")
        s = data.get("status", "?")
        print(f"{nid:<25} {t:>5.2f}  {h:<20} {s:<10}")

def cmd_rm(node_id):
    reg = load_registry()
    if node_id in reg.get("nodes", {}):
        del reg["nodes"][node_id]
        save_registry(reg)
        print(f"[OK] Node '{node_id}' removed")
    else:
        print(f"[WARN] Node '{node_id}' not found")

def cmd_refresh():
    # Trigger AnimaLink cache refresh by hitting the API
    try:
        with urllib.request.urlopen(f"{ANIMALINK_URL}?refresh=1", timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            count = len(data.get("nodes", []))
            print(f"[OK] AnimaLink refreshed: {count} nodes")
    except Exception as e:
        print(f"[WARN] Could not reach AnimaLink API: {e}")
        print(f"       Cache refreshes automatically every 300s")

def cmd_check():
    """Check accessibility for external nodes."""
    import socket
    print("=== External Access Check ===")
    try:
        hostname = socket.gethostname()
        print(f"  Hostname: {hostname}")
    except:
        pass
    
    # Check public AnimaLink
    try:
        req = urllib.request.Request("https://wlmhan.tail306b25.ts.net/animlink/api/nodes")
        with urllib.request.urlopen(req, timeout=10) as resp:
            nodes = json.loads(resp.read().decode('utf-8')).get("nodes", [])
            print(f"  Public API: OK ({len(nodes)} nodes)")
    except Exception as e:
        print(f"  Public API: {e}")

    reg = load_registry()
    nodes = reg.get("nodes", {})
    print(f"  Registry: {len(nodes)} nodes in {REGISTRY_PATH}")
    print()
    print("New node onboarding checklist:")
    print("  1. Iris gets: node_id, DID, hostname, platform")
    print("  2. Run: python animlink_register.py add <node_id> <did> <hostname> <platform>")
    print("  3. Verify: https://wlmhan.tail306b25.ts.net/animlink/")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    cmd = sys.argv[1]
    if cmd == "add" and len(sys.argv) >= 6:
        cmd_add(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], 
                sys.argv[6] if len(sys.argv) > 6 else None)
    elif cmd == "list":
        cmd_list()
    elif cmd == "rm" and len(sys.argv) >= 3:
        cmd_rm(sys.argv[2])
    elif cmd == "refresh":
        cmd_refresh()
    elif cmd == "check":
        cmd_check()
    else:
        print(__doc__)
        sys.exit(1)
