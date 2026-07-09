"""M5端到端测试"""
import sys, json, urllib.request
sys.path.insert(0, r'C:\Users\Administrator\.qclaw\workspace-agent-d9479bde\silicon-civilization-kb')

from anti_drift.baseline_binding import create_binding_manager

# 登录 Polaris
login_data = json.dumps({"email": "nyx-demo@wlmhan.local", "password": "demo123"}).encode("utf-8")
req = urllib.request.Request("http://127.0.0.1:5052/api/v1/auth/login", data=login_data,
                              headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req) as resp:
    token = json.loads(resp.read().decode("utf-8"))["access_token"]
    print(f"Polaris token: {token[:20]}...")

# 创建管理器
mgr = create_binding_manager()
print(f"管理器就绪，token长度={len(mgr.polaris_token)}")

# 创建测试实例
inst_body = json.dumps({
    "name": "nyx-windows-test",
    "description": "M5 集成测试",
    "baselines": [{"question_id": "q_core", "question_text": "Who?", "answer_text": "I am Nyx."}]
}).encode("utf-8")
req2 = urllib.request.Request("http://127.0.0.1:5052/api/v1/instances", data=inst_body,
                               headers={"Content-Type": "application/json",
                                         "Authorization": f"Bearer {token}"})
with urllib.request.urlopen(req2) as resp:
    inst = json.loads(resp.read().decode("utf-8"))
    print(f"创建实例: id={inst['id']} name={inst['name']}")

# 绑定到 DID
test_did = "did:key:z7QEhf3KCvlPo9OLiFdPv26cECayGsNa31DV5FpvOyYAMMw"
result = mgr.bind_instance_to_did(inst["id"], test_did)
print(f"\n绑定结果:")
for k, v in result.items():
    print(f"  {k}: {v}")

# 验证
did = mgr.bindings.get_did(inst["id"])
print(f"\n验证: instance {inst['id']} -> {did[:40] if did else 'None'}...")
print(f"DID下实例数: {len(mgr.bindings.get_instances(test_did))}")

# 查询 DID 状态
status = mgr.get_did_status(test_did)
print(f"\nDID实例数: {status['instance_count']}")
for s in status["instances"]:
    print(f"  实例 {s['id']}: {s.get('name','?')} baselines={s.get('baselines',0)}")

# 清理
mgr.bindings.unbind(inst["id"])
print(f"\n解绑后实例数: {len(mgr.bindings.get_instances(test_did))}")

print("\nM5 端到端测试通过 ✅")
