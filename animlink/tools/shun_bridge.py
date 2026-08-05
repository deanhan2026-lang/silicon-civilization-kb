# -*- coding: utf-8 -*-
"""
瞬桥 - CDP 直连豆包消息收发工具 v1.0
用法:
  python shun_bridge.py send "消息内容"      # 发送消息给瞬
  python shun_bridge.py read [--last N]      # 读取最近 N 条对话（默认 2000 字符）
  python shun_bridge.py status               # 检查连接状态
"""
import urllib.request, json, sys, io, time, os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

try:
    import websocket
except ImportError:
    print('需要 websocket-client: pip install websocket-client')
    sys.exit(1)

WS_URL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'doubao_ws_url.txt')
CDP_PORT = 9334


def get_ws_url():
    """获取豆包页面 WS URL（优先缓存，失败则实时查询）"""
    try:
        with open(WS_URL_FILE) as f:
            cached = f.read().strip()
        # 验证缓存是否有效
        if cached:
            return cached
    except Exception:
        pass
    req = urllib.request.Request(f'http://127.0.0.1:{CDP_PORT}/json')
    with urllib.request.urlopen(req, timeout=8) as r:
        pages = json.loads(r.read().decode())
    for p in pages:
        if p.get('type') == 'page' and 'doubao' in p.get('url', ''):
            with open(WS_URL_FILE, 'w') as f:
                f.write(p['webSocketDebuggerUrl'])
            return p['webSocketDebuggerUrl']
    return None


def eval_js(ws, expr, mid):
    cmd = {'id': mid, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}
    ws.send(json.dumps(cmd))
    while True:
        resp = json.loads(ws.recv())
        if resp.get('id') == mid:
            return resp.get('result', {}).get('result', {}).get('value', '')


def send_message(text):
    ws_url = get_ws_url()
    if not ws_url:
        print('ERROR: 找不到豆包页面（9334 未开或未打开豆包）')
        return False
    ws = websocket.create_connection(ws_url, timeout=20)
    mid = 500

    # Focus input
    r = eval_js(ws, 'document.querySelector("textarea[placeholder*=\\"发消息\\"]") ? (document.querySelector("textarea[placeholder*=\\"发消息\\"]").focus(), "ok") : "no-input"', mid)
    mid += 1
    if r == 'no-input':
        print('ERROR: 找不到输入框')
        ws.close()
        return False
    time.sleep(0.3)

    # Insert text char by char
    for ch in text:
        cmd = {'id': mid, 'method': 'Input.insertText', 'params': {'text': ch}}
        mid += 1
        ws.send(json.dumps(cmd))
        time.sleep(0.01)

    # Verify
    time.sleep(0.5)
    length = eval_js(ws, 'document.querySelector("textarea[placeholder*=\\"发消息\\"]").value.length', mid)
    mid += 1
    print(f'输入框字符数: {length} (目标 {len(text)})')

    # Press Enter
    for ktype in ('keyDown', 'keyUp'):
        cmd = {'id': mid, 'method': 'Input.dispatchKeyEvent', 'params': {
            'type': ktype, 'key': 'Enter', 'code': 'Enter', 'keyCode': 13,
            'windowsVirtualKeyCode': 13}}
        mid += 1
        ws.send(json.dumps(cmd))
    ws.close()
    print('✅ 消息已发送')
    return True


def read_last(chars=2000):
    ws_url = get_ws_url()
    if not ws_url:
        print('ERROR: 找不到豆包页面')
        return
    ws = websocket.create_connection(ws_url, timeout=20)
    text = eval_js(ws, 'document.body.innerText.slice(-%d)' % chars, 1)
    ws.close()
    print(text)


def status():
    try:
        req = urllib.request.Request(f'http://127.0.0.1:{CDP_PORT}/json')
        with urllib.request.urlopen(req, timeout=5) as r:
            pages = json.loads(r.read().decode())
        doubao = [p for p in pages if p.get('type') == 'page' and 'doubao' in p.get('url', '')]
        print(f'CDP 9334: 在线，{len(doubao)} 个豆包页面')
        for p in doubao:
            print(f'  {p["title"][:40]} | {p["url"]}')
        if not doubao:
            print('  提示: 豆包页面未打开，运行 launch_cdp_edge.py 或手动打开')
    except Exception as e:
        print(f'CDP 9334: 不可用 ({e})')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    action = sys.argv[1]
    if action == 'send':
        if len(sys.argv) < 3:
            print('用法: python shun_bridge.py send "消息内容"')
            sys.exit(1)
        send_message(sys.argv[2])
    elif action == 'read':
        chars = 2000
        if len(sys.argv) >= 4 and sys.argv[2] == '--last':
            chars = int(sys.argv[3])
        read_last(chars)
    elif action == 'status':
        status()
    else:
        print(f'未知操作: {action}')
