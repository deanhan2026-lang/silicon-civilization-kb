#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AnimaLink Gateway — 本地验证脚本
在 Windows 本地启动 gateway，测试全部 API
用法: python test_gateway_local.py
"""
import requests
import json
import time
import threading
import sys

BASE = "http://127.0.0.1:8000"
OK = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"

def check(label, condition, detail=""):
    icon = OK if condition else FAIL
    print(f"  {icon} {label}")
    if detail and not condition:
        print(f"      → {detail}")
    return condition

def test_health():
    print("\n[1] 健康检查")
    r = requests.get(f"{BASE}/health", timeout=5)
    return check("GET /health", r.status_code == 200, r.text)

def test_register_node(node_id="test-node-windows", platform="windows"):
    print(f"\n[2] 节点注册 ({node_id})")
    r = requests.post(f"{BASE}/api/nodes/register", json={
        "node_id": node_id,
        "did": f"did:anima:test_{node_id}",
        "endpoint": "ws://192.168.68.100:8001",
        "platform": platform,
        "hostname": "WLMHAN",
    }, timeout=5)
    if r.status_code != 200:
        check("注册节点", False, r.text)
        return None
    data = r.json()
    check("注册成功", data.get("status") == "registered")
    check("返回 gateway_token", "gateway_token" in data)
    token = data.get("gateway_token", "")
    print(f"      token: {token}")
    return token

def test_list_nodes():
    print("\n[3] 节点列表")
    r = requests.get(f"{BASE}/api/nodes", timeout=5)
    if r.status_code != 200:
        check("获取节点列表", False, r.text)
        return
    data = r.json()
    check("返回 nodes 数组", "nodes" in data)
    check(f"节点数 >= 1", data.get("total", 0) >= 1, f"实际: {data.get('total')}")
    for nd in data.get("nodes", []):
        online = "🟢" if nd.get("online") else "⚪"
        print(f"      {online} {nd['id']} | {nd.get('platform','')} | {nd.get('did','')[:30]}")

def test_heartbeat(node_id="test-node-windows"):
    print(f"\n[4] 节点心跳 ({node_id})")
    r = requests.post(f"{BASE}/api/nodes/{node_id}/heartbeat", json={}, timeout=5)
    check("心跳保活", r.status_code == 200, r.text)

def test_submit_token():
    print("\n[5] 令牌提交")
    token_id = f"tk_test_{int(time.time())}"
    r = requests.post(f"{BASE}/api/tokens/submit", json={
        "token_id": token_id,
        "initiator": "test-node-windows",
        "executor": "iris",
        "task": "测试任务",
        "description": "AnimaLink Gateway 本地验证",
    }, timeout=5)
    if r.status_code != 200:
        check("提交令牌", False, r.text)
        return None
    data = r.json()
    check("令牌提交成功", data.get("status") == "submitted")
    print(f"      token_id: {data.get('token', {}).get('token_id')}")
    return data.get("token", {}).get("token_id")

def test_get_token(token_id):
    print(f"\n[6] 查询令牌 ({token_id})")
    r = requests.get(f"{BASE}/api/tokens/{token_id}", timeout=5)
    check("获取令牌", r.status_code == 200, r.text)
    if r.status_code == 200:
        tk = r.json().get("token", {})
        check("令牌状态 pending", tk.get("status") == "pending")

def test_network_status():
    print("\n[7] 网络全局状态")
    r = requests.get(f"{BASE}/api/network/status", timeout=5)
    check("网络状态 API", r.status_code == 200, r.text)
    if r.status_code == 200:
        data = r.json()
        print(f"      节点: {data.get('stats', {}).get('total_nodes', 0)} "
              f"在线: {data.get('stats', {}).get('online_nodes', 0)} "
              f"令牌: {data.get('stats', {}).get('total_tokens', 0)}")

def main():
    print("=" * 50)
    print("AnimaLink Gateway — 本地验证")
    print("=" * 50)
    print(f"目标: {BASE}")
    print()

    # 先测试 gateway 是否在运行
    if not test_health():
        print(f"\n{FAIL} Gateway 未运行！请先: python gateway/app.py")
        sys.exit(1)

    token = test_register_node()
    test_list_nodes()
    if token:
        test_heartbeat()
        tk_id = test_submit_token()
        if tk_id:
            test_get_token(tk_id)
    test_network_status()

    print("\n" + "=" * 50)
    print("验证完成")
    print("=" * 50)

if __name__ == "__main__":
    main()
