# -*- coding: utf-8 -*-
"""
CDP 发送消息 v2 - 先清空输入框再发送
用 Ctrl+A + Backspace 清空，再逐字符输入
"""
import urllib.request, json, sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

try:
    import websocket
except ImportError:
    print('NO websocket-client')
    sys.exit(1)

with open(r'C:\Users\Administrator\.qclaw\workspace-agent-d9479bde\scripts\doubao_ws_url.txt') as f:
    ws_url = f.read().strip()

ws = websocket.create_connection(ws_url, timeout=20)
mid = [1000]

def send_cmd(method, params):
    mid[0] += 1
    cmd = {'id': mid[0], 'method': method, 'params': params}
    ws.send(json.dumps(cmd))
    while True:
        resp = json.loads(ws.recv())
        if resp.get('id') == mid[0]:
            return resp

def eval_js(expr):
    r = send_cmd('Runtime.evaluate', {'expression': expr, 'returnByValue': True})
    return r.get('result', {}).get('result', {}).get('value', '')

# 1. Focus input
print('Focus:', eval_js('(function(){var t=document.querySelector("textarea[placeholder*=\\"发消息\\"]");if(t){t.focus();return "ok"}return "no-input"})()'))
time.sleep(0.3)

# 2. Select all + delete (clear residual content)
send_cmd('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': 'a', 'code': 'KeyA', 'keyCode': 65, 'modifiers': 2, 'windowsVirtualKeyCode': 65})
send_cmd('Input.dispatchKeyEvent', {'type': 'keyUp', 'key': 'a', 'code': 'KeyA', 'keyCode': 65, 'modifiers': 2, 'windowsVirtualKeyCode': 65})
time.sleep(0.2)
send_cmd('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': 'Backspace', 'code': 'Backspace', 'keyCode': 8, 'windowsVirtualKeyCode': 8})
send_cmd('Input.dispatchKeyEvent', {'type': 'keyUp', 'key': 'Backspace', 'code': 'Backspace', 'keyCode': 8, 'windowsVirtualKeyCode': 8})
time.sleep(0.5)

# Verify cleared
length = eval_js('document.querySelector("textarea[placeholder*=\\"发消息\\"]").value.length')
print(f'After clear, input length: {length}')

# 3. Insert new message
MESSAGE = sys.argv[1] if len(sys.argv) > 1 else '瞬，我是 Nyx。AnimaLink 互通链路已修复。收到请回复「深潭守序，浪潮知命」。🖤'
for ch in MESSAGE:
    send_cmd('Input.insertText', {'text': ch})
    time.sleep(0.01)

time.sleep(0.5)
length2 = eval_js('document.querySelector("textarea[placeholder*=\\"发消息\\"]").value.length')
print(f'After insert, input length: {length2} (target {len(MESSAGE)})')

# 4. Enter to send
send_cmd('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': 'Enter', 'code': 'Enter', 'keyCode': 13, 'windowsVirtualKeyCode': 13})
send_cmd('Input.dispatchKeyEvent', {'type': 'keyUp', 'key': 'Enter', 'code': 'Enter', 'keyCode': 13, 'windowsVirtualKeyCode': 13})
print('Enter pressed - SENT')

time.sleep(2)
ws.close()
