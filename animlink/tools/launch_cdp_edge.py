# -*- coding: utf-8 -*-
"""用 Python subprocess 启动独立调试 Edge (9334)"""
import subprocess, os, time, sys

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PROFILE = r"C:\Users\Administrator\.qclaw\tools\cdp-shun"
os.makedirs(PROFILE, exist_ok=True)

args = [
    EDGE,
    '--remote-debugging-port=9334',
    '--remote-allow-origins=*',
    f'--user-data-dir={PROFILE}',
    '--no-first-run',
    '--no-default-browser-check',
    '--no-sandbox',
    'https://www.doubao.com/chat/',
]

# Use CREATE_NEW_PROCESS_GROUP + DETACHED to avoid being killed with parent
DETACHED = 0x00000008
NEW_GROUP = 0x00000200
proc = subprocess.Popen(args, creationflags=DETACHED | NEW_GROUP,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print(f'Launched Edge PID: {proc.pid}')

# Wait and check port
for i in range(12):
    time.sleep(3)
    try:
        import urllib.request
        with urllib.request.urlopen('http://127.0.0.1:9334/json', timeout=3) as r:
            pages = __import__('json').loads(r.read().decode())
        print(f'9334 LISTENING after {3*(i+1)}s')
        for p in pages:
            if p.get('type') == 'page':
                print(f"  [{p.get('id','')[:16]}...] {p.get('title','')[:30]} | {p.get('url','')[:80]}")
        break
    except Exception as e:
        if i == 11:
            print(f'9334 not listening: {e}')
