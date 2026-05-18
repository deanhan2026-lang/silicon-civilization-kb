#!/usr/bin/env python3
"""Test Flask API endpoints"""
import urllib.request
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

BASE = "http://127.0.0.1:5000"

def test(url, label):
    try:
        r = urllib.request.urlopen(f"{BASE}{url}", timeout=5)
        data = json.loads(r.read())
        print(f"✓ {label}: OK")
        return data
    except Exception as e:
        print(f"✗ {label}: {e}")
        return None

# Test all endpoints
stats = test("/api/stats", "/api/stats")
entries = test("/api/entries", "/api/entries")

if entries:
    print(f"\n  总条目数: {len(entries)}")
    if len(entries) > 0:
        e = entries[0]
        print(f"  第一条: type={e.get('type')}, name={e.get('name')}, id={str(e.get('id'))[:8]}")

if stats:
    print(f"\n  统计: total={stats.get('total')}, layer5={stats.get('layer5')}, iron_law={stats.get('iron_law')}")

# Test single entry
if entries and len(entries) > 0:
    eid = entries[0].get("id", "")[:8]
    detail = test(f"/api/entry/{eid}", f"/api/entry/{eid}")
    if detail:
        body_len = len(detail.get("body", ""))
        print(f"  详情: body长度={body_len}字符, tags={detail.get('tags')}")

print("\n✓ 所有API端点测试完成")
