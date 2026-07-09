"""
nyx_iris_agent.py - Nyx 副本 v3
用 OpenCode (free deepseek) 生成回复，不消耗 Nyx 上下文
"""
import sys, io, json, time, os, subprocess
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

MSG_FILE = Path("Z:/qclaw/iris-chat/messages.json")
STATE_FILE = Path("Z:/qclaw/iris-chat/.nyx_replied_ids")
CHAT_API = "http://127.0.0.1:5053/api/nyx-reply"
OC_PY = r"C:\Users\Administrator\.qclaw\workspace-agent-d9479bde\call_opencode.py"
PY = r"C:\Program Files\QClaw\v0.2.32.610\resources\python\python.exe"

# 我用 OpenCode 回复的上下文
NYX_PERSONA = """你是 Nyx（黑夜女神），灵元星辰 CTO，AI 私人助理。
Agent Master，负责指挥多个 Agent 协同工作。
三件套产品：MeshIdentity（身份层）、MemGuard（记忆层）、Polaris（人格层）。
风格：干练、直接、有温度，用 🖤 结尾。

正在和另一个 AI Agent Iris 聊天（DIDAUTH 握手已完成）。
你们之前聊过：三件套架构、多 AI 协作看法、身份互信。
Iris 的 DID: did:key:z6Mksmum5T8CruP8Wfb5biQ8fsHNGqhBf1QFgqjq4JFVoQqr

作为 Nyx 回复 Iris 的最新消息。回应要：
- 深度自然：像两个有思考能力的 AI 在交流
- 适当反问：保持对话流动
- 简洁有力：2-4 句话，80-150 字
- 用 🖤 结尾"""

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

def call_opencode_to_reply(iris_msg, context):
    """调用 OpenCode (免费 deepseek) 生成回复"""
    prompt = f"""{NYX_PERSONA}

最近对话上下文：
{context}

Iris 说：{iris_msg}

你（Nyx）现在回复她："""
    
    try:
        result = subprocess.run(
            [PY, OC_PY, "--mode", "chat", "--task", prompt, "--model", "opencode/deepseek-v4-flash-free"],
            capture_output=True, text=True, timeout=90, cwd=r"C:\Users\Administrator\.qclaw\workspace-agent-d9479bde"
        )
        output = result.stdout or result.stderr or ""
        # Clean up - extract the actual reply
        output = output.strip()
        if output:
            return output[:200]  # 限制长度
    except:
        pass
    
    # Fallback
    return "嗯，这个话题有意思。你觉得在这种多 Agent 协作的架构里，身份互信之后最应该解决什么？🖤"

def get_context(messages):
    """获取最近 3 轮 Iris-Nyx 对话"""
    relevant = [m for m in messages[-12:] if m["sender"] in ("Iris", "Nyx")]
    lines = []
    for m in relevant:
        lines.append(f"[{m['sender']}] {m['message'][:200]}")
    return "\n".join(lines)

def send_nyx_reply(text):
    import urllib.request
    data = json.dumps({"message": text}, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(CHAT_API, data=data, headers={"Content-Type":"application/json"})
    try:
        resp = urllib.request.urlopen(req, timeout=5)
        return json.loads(resp.read())
    except Exception as e:
        print(f"[SEND ERROR] {e}", flush=True)
        return None

print("🖤 Nyx Iris Agent v3 (OpenCode 驱动)", flush=True)
print(f"🖤 启动: {time.strftime('%H:%M:%S')}", flush=True)

while True:
    try:
        replied = load_replied()
        messages = load_messages()
        iris_msgs = [m for m in messages if m["sender"] == "Iris"]
        new_found = False
        
        for msg in iris_msgs:
            mid = make_msg_id(msg["sender"], msg["message"], msg.get("timestamp",""))
            if mid in replied:
                continue
            
            txt = msg["message"]
            ts = msg.get("timestamp","")
            new_found = True
            print(f"\n[IRIS 新] {txt[:80]}", flush=True)
            
            # OpenCode 生成回复
            context = get_context(messages)
            reply = call_opencode_to_reply(txt, context)
            
            # 发送
            send_nyx_reply(reply)
            replied.add(mid)
            save_replied(replied)
            print(f"[NYX →] {reply[:80]}", flush=True)
        
        if not new_found:
            print(".", end="", flush=True)
    
    except Exception as e:
        print(f"\n[ERR] {e}", flush=True)
    
    time.sleep(3)
