"""M5 REST API 路由测试"""
import sys, json, urllib.request

BASE = "http://127.0.0.1:5052/api/v1"
hdr = {"Content-Type": "application/json"}

# 登录
login = json.dumps({"email": "nyx-demo@wlmhan.local", "password": "demo123"}).encode("utf-8")
req = urllib.request.Request(f"{BASE}/auth/login", data=login, headers=hdr)
with urllib.request.urlopen(req) as resp:
    token = json.loads(resp.read().decode("utf-8"))["access_token"]
    print(f"Token: {token[:20]}...")

auth_hdr = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# 创建实例
inst_body = json.dumps({"name": "m5-route-test", "description": "M5 route test",
    "baselines": [{"question_id": "q1", "question_text": "Who?", "answer_text": "Nyx"}]}).encode("utf-8")
req2 = urllib.request.Request(f"{BASE}/instances", data=inst_body, headers=auth_hdr)
with urllib.request.urlopen(req2) as resp:
    inst = json.loads(resp.read().decode("utf-8"))
    iid = inst["id"]
    print(f"实例创建: id={iid}")

test_did = "did:key:z7QEhf3KCvlPo9OLiFdPv26cECayGsNa31DV5FpvOyYAMMw"

# 1. bind-did POST
bind = json.dumps({"did": test_did}).encode("utf-8")
req3 = urllib.request.Request(f"{BASE}/instances/{iid}/bind-did", data=bind, headers=auth_hdr)
with urllib.request.urlopen(req3) as resp:
    r = json.loads(resp.read().decode("utf-8"))
    print(f"1. 绑定结果: instances_under_did={r['instances_under_did']}")

# 2. did-status GET
req4 = urllib.request.Request(f"{BASE}/instances/{iid}/did-status", headers=auth_hdr)
with urllib.request.urlopen(req4) as resp:
    r = json.loads(resp.read().decode("utf-8"))
    print(f"2. DID状态: bound={r['bound']}")

# 3. bindings list
req5 = urllib.request.Request(f"{BASE}/bindings", headers=auth_hdr)
with urllib.request.urlopen(req5) as resp:
    r = json.loads(resp.read().decode("utf-8"))
    print(f"3. 绑定列表: {len(r)} 条")

# 4. unbind DELETE
req6 = urllib.request.Request(f"{BASE}/instances/{iid}/bind-did", data=b"", headers=auth_hdr, method="DELETE")
with urllib.request.urlopen(req6) as resp:
    r = json.loads(resp.read().decode("utf-8"))
    print(f"4. 解绑结果: {r['status']}")

print("\nM5 REST API 路由全部通过 ✅")
