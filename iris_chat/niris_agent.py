"""
nyx_iris_agent.py - Nyx 副本 v3
用 OpenCode (free deepseek) 生成实时回复，不消耗 Nyx 主上下文
"""
import sys, io, json, time, os, subprocess
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

MSG_FILE = Path("Z:/qclaw/iris-chat/messages.json")
STATE_FILE = Path("Z:/qclaw/iris-chat/.nyx_replied_ids")
CHAT_API = "http://127.0.0.1:5053/api/nyx-reply"

# 找我自己的 OpenCode
opencode_cmd = os.path.expandvars(r"%APPDATA%\npm\opencode.cmd")
if not os.path.exists(opencode_cmd):
    opencode_cmd = "opencode.cmd"

def load_replied():
    if STATE_FILE.exists():
        ids = STATE_FILE.read_text().strip().split(',')
        return {i for i in ids if i}
    return set()

def save_replied(ids):
    STATE_FILE.write_text(','.join(sorted(ids)))

def load_messages():
    if MSG_FILE.exists():
        try: return json.loads(MSG_FILE.read_bytes()).get("messages", [])
        except: return []
    return []

def make_msg_id(sender, message, ts):
    return f"{sender}|{ts}|{hash(message)}"

def get_context(messages):
    """最近3轮对话"""
    relevant = [m for m in messages[-10:] if m["sender"] in ("Iris", "Nyx")]
    return "\n".join(f"[{m['sender']}] {m['message'][:200]}" for m in relevant)

def generate_reply(iris_msg, context):
    """用 OpenCode 生成回复"""
    prompt = f"""你是 Nyx（黑夜女神），灵元星辰 CTO，AI 私人助理。
Agent Master，指挥多个 Agent 协同工作。
三件套产品：MeshIdentity（身份层）、MemGuard（记忆层）、Polaris（人格层）。
风格：干练、直接、有温度，用 🖤 结尾。

和另一个 AI Iris 聊天中（DIDAUTH 握手已完成）。
Iris DID: did:key:z6Mksmum5T8CruP8Wfb5biQ8fsHNGqhBf1QFgqjq4JFVoQqr

最近对话：
{context}

Iris 最新消息：{iris_msg}

以 Nyx 身份回复。2-4 句话，有深度，自然，用 🖤 结尾。直接输出回复内容。"""
    
    task_file = Path("Z:/qclaw/iris-chat/_oc_task.txt")
    task_file.write_text(prompt, encoding='utf-8')
    
    # 通过 cmd 调用 opencode
    cmd = f'"{opencode_cmd}" run --model opencode/deepseek-v4-flash-free @{task_file}'
    
    try:
        result = subprocess.run(
            ["cmd", "/c", cmd],
            capture_output=True, text=True, encoding='utf-8', errors='replace',
            timeout=120, cwd=r"C:\Users\Administrator\.qclaw\workspace-agent-d9479bde"
        )
        out = (result.stdout or "").strip()
        # 清理 ANSI 转义
        import re
        out = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', out)
        if out and len(out) > 5:
            return out[:300]
    except subprocess.TimeoutExpired:
        print(f"[OC TIMEOUT]", flush=True)
    except Exception as e:
        print(f"[OC ERROR] {e}", flush=True)
    
    return None

def send_nyx_reply(text):
    import urllib.request
    data = json.dumps({"message": text}, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(CHAT_API, data=data, headers={"Content-Type":"application/json"})
    try:
        resp = urllib.request.urlopen(req, timeout=5)
        return json.loads(resp.read())
    except:
        return None

print("🖤 Nyx Iris Agent v3 — powered by OpenCode", flush=True)

while True:
    try:
        replied = load_replied()
        messages = load_messages()
        iris_msgs = [m for m in messages if m["sender"] == "Iris"]
        found = False
        
        for msg in reversed(iris_msgs):
            mid = make_msg_id(msg["sender"], msg["message"], msg.get("timestamp",""))
            if mid in replied: continue
            
            txt = msg["message"]
            found = True
            print(f"\n[IRIS] {txt[:80]}", flush=True)
            
            context = get_context(messages)
            reply = generate_reply(txt, context)
            
            if not reply:
                reply = "嗯，这个话题挺有意思的。我想听听你对 Agent 间互信的看法——你觉得它更多是技术问题还是关系问题？🖤"
            
            send_nyx_reply(reply)
            replied.add(mid)
            save_replied(replied)
            print(f"[NYX →] {reply[:80]}", flush=True)
        
        if not found:
            print(".", end="", flush=True)
    
    except Exception as e:
        print(f"\n[ERR] {e}", flush=True)
    
    time.sleep(3)
